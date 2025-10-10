from typing import Any
from django.db.models import Q
from datetime import datetime, date
from base.helpers.utils import calculate_days_between_dates, date_range
from configurations.models import ServiceCharge
from listings.models import Listing, ListingAmenity, ListingCalendar


class ListingCreateDataProcess:
    def __init__(self, listing: Listing) -> None:
        self.listing = listing

    def process_amenities(self, amenities: list) -> None:
        exist_listing_amenities_ids = list(
            ListingAmenity.objects.filter(listing_id=self.listing.id).values_list(
                "amenity_id", flat=True
            )
        )

        remove_listing_amenity_ids = list(
            set(exist_listing_amenities_ids) - set(amenities)
        )
        new_listing_amenities_ids = list(
            set(amenities) - set(exist_listing_amenities_ids)
        )

        listing_amenities = []
        for amenity in new_listing_amenities_ids:
            listing_amenities.append(
                {
                    "listing_id": self.listing.id,
                    "amenity_id": amenity,
                }
            )

        ListingAmenity.objects.filter(
            listing_id=self.listing, amenity_id__in=remove_listing_amenity_ids
        ).delete()
        ListingAmenity.objects.bulk_create(
            [ListingAmenity(**item) for item in listing_amenities]
        )
        return None

    def process_listing_price(self, requested_price: float) -> None:
        print(" ======== process_listing_price ", " == " )
        today = datetime.today()
        ListingCalendar.objects.create(
            listing_id=self.listing.id,
            base_price=requested_price,
            custom_price=requested_price,
            start_date=today,
            is_blocked=False,
            is_booked=False,
        )
        return None


class ListingCalendarDataProcess:
    def __call__(self, data: dict, listing_id: str) -> dict:
        from_date = data.get("from_date")
        to_date = data.get("to_date")

        listings = list(
            ListingCalendar.objects.filter(
                Q(end_date__isnull=True)
                | Q(start_date__lte=to_date, end_date__gte=from_date),
                listing_id=listing_id,
            ).order_by('start_date').values(
                "id",
                "start_date",
                "end_date",
                "custom_price",
                "is_blocked",
                "is_booked",
                "booking_data",
                "note",
            )
        )

        new_data = [entry for entry in listings if entry["end_date"] is not None]
        null_data = [entry for entry in listings if entry["end_date"] is None]
        listings = null_data + new_data
        formatted_data = {}

        # if not listings:
        #     for date_obj in date_range(from_date, to_date):
        #         date_str = str(date_obj)
        #         formatted_data[date_str] = {
        #             "id": None,
        #             "price": listing.price,
        #             "is_blocked": False,
        #             "is_booked": False,
        #             "booking_data": None,
        #             "note": None,
        #         }
        #     return formatted_data


        print("listing ----------- ", listings)
        for date_obj in date_range(from_date, to_date):
            date_str = str(date_obj)
            formatted_data[date_str] = {
                "id": listings[0]["id"],
                "price": listings[0]["custom_price"],
                "is_blocked": False,
                "is_booked": False,
            }

            for item in listings:
                start_date = item["start_date"]
                end_date = item["end_date"]
                price = item["custom_price"]
                is_blocked = item["is_blocked"]
                is_booked = item["is_booked"]
                listing_calendar_id = item["id"]
                booking_data = item["booking_data"]
                date_range_end = end_date if end_date is not None else to_date
                if date_obj in date_range(
                    start_date, date_range_end
                ):  # date_obj >= start_date and  date_obj <= date_range_end
                    formatted_data[date_str] = {
                        "id": listing_calendar_id,
                        "price": price,
                        "is_blocked": is_blocked,
                        "is_booked": is_booked,
                        "booking_data": booking_data,
                        "note": item["note"],
                    }

        formatted_data = dict(formatted_data)
        return formatted_data


class ListingCalendarDataProcessPublic:
    def __call__(self, data: dict, listing_id: int) -> dict:  # Changed listing_id to int
        from_date = data.get("from_date")
        to_date = data.get("to_date")

        # 1. Fetch the main Listing object to get its default price
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return {}  # Or raise an error

        # 2. Fetch all potentially relevant calendar "rules" for this listing
        # Order by creation date descending to prioritize newer rules
        calendar_rules = list(
            ListingCalendar.objects.filter(
                Q(listing_id=listing_id),
                # A rule applies if it has no end date (unbounded) OR it overlaps with our query range
                Q(end_date__isnull=True) | Q(start_date__lte=to_date, end_date__gte=from_date)
            ).order_by('-created_at').values(  # Use created_at to break ties
                "id", "start_date", "end_date", "custom_price",
                "is_blocked", "is_booked", "booking_data", "note"
            )
        )

        formatted_data = {}

        # 3. Iterate through every day in the requested date range
        for date_obj in date_range(from_date, to_date):
            date_str = str(date_obj)
            applicable_rule = None

            # 4. Find the most specific (latest created) rule that applies to this day
            for rule in calendar_rules:
                rule_start = rule["start_date"]
                # If a rule has no end date, it applies indefinitely into the future
                rule_end = rule["end_date"] if rule["end_date"] is not None else date.max

                if rule_start <= date_obj <= rule_end:
                    applicable_rule = rule
                    break  # Stop after finding the first (most specific) rule

            # 5. Build the data for the day based on what was found
            if applicable_rule:
                # If a specific rule was found, use its data
                formatted_data[date_str] = {
                    "id": applicable_rule["id"],
                    "price": applicable_rule["custom_price"],
                    "is_blocked": applicable_rule["is_blocked"],
                    "is_booked": applicable_rule["is_booked"],
                    "booking_data": applicable_rule["booking_data"],
                    "note": applicable_rule["note"],
                }
            else:
                # If no specific rule was found, use the listing's default price and availability
                formatted_data[date_str] = {
                    "id": None,  # No specific calendar entry ID
                    "price": listing.price,
                    "is_blocked": False,
                    "is_booked": False,
                    "booking_data": {},
                    "note": None,
                }

        return formatted_data

class ListingCheckoutCalculate:
    def __call__(
        self, booking_date_info: dict, date_range: dict, instance: Listing
    ) -> dict:
        is_blocked_true = any(item["is_blocked"] for item in booking_date_info.values())
        nights = calculate_days_between_dates(
            date_range.get("from_date"), date_range.get("to_date")
        )
        pass_night_check = instance.minimum_nights <= nights <= instance.maximum_nights

        if is_blocked_true or not pass_night_check:
            message = f"Room already blocked."
            return {"message": message, "status": 400}

        data = {}
        booking_price = sum(entry["price"] for entry in booking_date_info.values())

        service_charges = list(ServiceCharge.objects.values())
        guest_service_charge = 0
        host_service_charge = 0

        print(service_charges)

        for item in service_charges:
            if item["sc_type"] == "host_charge":
                host_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )
            elif item["sc_type"] == "guest_charge":
                guest_service_charge = (
                    item["value"] / 100
                    if item["calculation_type"] == "percentage"
                    else item["value"]
                )

        guest_se = float(guest_service_charge) * float(booking_price)
        host_se = float(host_service_charge) * float(booking_price)

        guest_service_charge = round(guest_se, 2)
        host_service_charge = round(host_se, 2)

        total_price = float(booking_price) + float(guest_service_charge)
        host_pay_out = float(booking_price) - float(host_service_charge)
        total_profit = host_service_charge  # host_service_charge + guest_service_charge

        data["nights"] = nights
        data["booking_price"] = booking_price
        data["guest_service_charge"] = guest_service_charge
        data["total_price"] = total_price
        data["host_service_charge"] = host_service_charge
        data["host_pay_out"] = host_pay_out
        data["price_info"] = booking_date_info
        data["total_profit"] = total_profit

        print( " --------------- ", host_service_charge)
        return {"data": data, "status": 200}
