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

class ListingCalendarDataProcessCal:
    def __call__(self, data: dict, listing_id: str) -> dict:
        from_date = data.get("from_date")
        to_date = data.get("to_date")

        # 1. Get all relevant rules, with the NEWEST ones FIRST.
        listings = list(
            ListingCalendar.objects.filter(
                Q(end_date__isnull=True) | Q(start_date__lte=to_date, end_date__gte=from_date),
                listing_id=listing_id,
            ).order_by('-created_at').values(
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

        formatted_data = {}

        # If there are no rules, you may want to handle it (e.g., use listing base price)
        if not listings:
            # This part is optional but good practice
            # listing = Listing.objects.get(id=listing_id)
            # base_price = listing.price
            # for date_obj in date_range(from_date, to_date):
            #     formatted_data[str(date_obj)] = {"price": base_price, ...}
            return formatted_data

        # 2. Iterate over each day you need to generate data for.
        for date_obj in date_range(from_date, to_date):
            date_str = str(date_obj)

            # 3. Find the FIRST matching rule for that day.
            # Since the list is sorted by newest first, this will be the correct one.
            for item in listings:
                start_date = item["start_date"]
                end_date = item["end_date"]

                # Check if the current day falls within the rule's date range
                rule_applies = False
                if end_date is None and date_obj >= start_date:
                    # This is a rule with no end date (e.g., "price is 10 from now on")
                    rule_applies = True
                elif end_date is not None and start_date <= date_obj <= end_date:
                    # This is a rule for a specific date range
                    rule_applies = True

                if rule_applies:
                    # Found the newest rule that applies. Use it.
                    formatted_data[date_str] = {
                        "id": item["id"],
                        "price": item["custom_price"],
                        "is_blocked": item["is_blocked"],
                        "is_booked": item["is_booked"],
                        "booking_data": item["booking_data"],
                        "note": item["note"],
                    }
                    # 4. IMPORTANT: Stop searching for this day and move to the next.
                    break

        return formatted_data


class ListingCalendarDataProcessPublic:
    def __call__(self, data: dict, listing_id: int) -> dict:
        from_date = data.get("from_date")
        to_date = data.get("to_date")

        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return {}

        # --- THE FIX: Separate the queries for bounded and unbounded rules ---

        # 1. Fetch all specific, BOUNDED rules that overlap with our date range.
        # Order by most recent so if two bounded rules overlap, the newer one wins.
        bounded_rules = list(
            ListingCalendar.objects.filter(
                listing_id=listing_id,
                start_date__lte=to_date,
                end_date__gte=from_date,
                end_date__isnull=False  # Explicitly get only bounded rules
            ).order_by('-created_at').values(
                "id", "start_date", "end_date", "custom_price",
                "is_blocked", "is_booked", "booking_data", "note"
            )
        )

        # 2. Fetch the SINGLE most recent UNBOUNDED (default price) rule.
        unbounded_rule = ListingCalendar.objects.filter(
            listing_id=listing_id,
            end_date__isnull=True
        ).order_by('-created_at').values(
            "id", "start_date", "end_date", "custom_price",
            "is_blocked", "is_booked", "booking_data", "note"
        ).first()  # Use .first() to get only one

        # --- END OF FIX ---

        formatted_data = {}

        # 3. Iterate through every day in the requested date range
        for date_obj in date_range(from_date, to_date):
            date_str = str(date_obj)
            applicable_rule = None

            # 4. Phase 1: Check against specific, bounded rules first.
            for rule in bounded_rules:
                if rule["start_date"] <= date_obj <= rule["end_date"]:
                    applicable_rule = rule
                    break  # Found the most specific rule, stop looking

            # 5. Phase 2: If no bounded rule was found, check the general unbounded rule.
            if not applicable_rule and unbounded_rule:
                if unbounded_rule["start_date"] <= date_obj:
                    applicable_rule = unbounded_rule

            # 6. Build the data for the day
            if applicable_rule:
                # A rule (either bounded or unbounded) was found
                formatted_data[date_str] = {
                    "id": applicable_rule["id"],
                    "price": applicable_rule["custom_price"],
                    "is_blocked": applicable_rule["is_blocked"],
                    "is_booked": applicable_rule["is_booked"],
                    "booking_data": applicable_rule["booking_data"],
                    "note": applicable_rule["note"],
                }
            else:
                # If no rules were found at all, fall back to the listing's master price
                formatted_data[date_str] = {
                    "id": None,
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
