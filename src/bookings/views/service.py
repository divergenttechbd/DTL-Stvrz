from datetime import datetime, date as Date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from django.db.models import Q
from django.contrib.auth import get_user_model
from accounts.serializers import UserSerializer
from base.helpers.utils import identifier_builder
from base.type_choices import BookingStatusOption, UserTypeOption
from bookings.models import Booking, ListingBookingReview
from listings.models import Listing, ListingCalendar
from django.shortcuts import get_object_or_404

from listings.views.service import ListingCalendarDataProcess, ListingCheckoutCalculate
from ..coupon_service import validate_and_get_coupon_discount_info
from typing import Dict

from datetime import datetime, date as Date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP  # Added ROUND_HALF_UP
from typing import Any, Dict

from django.contrib.auth import get_user_model
from base.helpers.utils import identifier_builder
# from base.type_choices import BookingStatusOption, UserTypeOption # Already in your file
from listings.models import Listing
from listings.views.service import ListingCalendarDataProcess, ListingCheckoutCalculate
# Assuming coupon_service.py is in the same app 'bookings'
from bookings.coupon_service import validate_and_get_coupon_discount_info



User = get_user_model()


# class GuestBookingProcess:
#     def __call__(self, request_data: Dict[str, Any], user: User) -> Dict[str, Any]:
#         current_date = Date.today()
#
#         listing_id = request_data.get("listing")
#         if not listing_id:
#             return {"status": 400, "message": "Listing ID is required.", "data": None}
#         try:
#             listing_obj = Listing.objects.get(id=listing_id)
#         except Listing.DoesNotExist:
#             return {"status": 404, "message": "Listing not found.", "data": None}
#
#         try:
#             from_date_str = request_data.get("check_in")
#             to_date_str = request_data.get("check_out")
#             if not from_date_str or not to_date_str:
#                 return {"status": 400, "message": "Check-in and Check-out dates are required.", "data": None}
#             from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
#             to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
#         except ValueError:
#             return {"status": 400, "message": "Invalid date format. Please use YYYY-MM-DD.", "data": None}
#
#         if not (from_date >= current_date and to_date > from_date):
#             return {"status": 400, "message": "Invalid booking date range.", "data": None}
#
#         date_filter = {"from_date": from_date, "to_date": to_date}
#         calendar_data_process = ListingCalendarDataProcess()
#         raw_calendar_data_for_period = calendar_data_process(date_filter, listing_id)
#         if not raw_calendar_data_for_period:
#             return {"status": 400, "message": "No availability/pricing for selected dates.", "data": None}
#
#         checkout_calculator = ListingCheckoutCalculate()
#         checkout_data_result = checkout_calculator(
#             booking_date_info=raw_calendar_data_for_period.copy(),
#             date_range=date_filter,
#             instance=listing_obj,
#         )
#         if checkout_data_result["status"] != 200:
#             return checkout_data_result
#         checkout_data = checkout_data_result["data"]
#
#         try:
#             current_total_price_before_discount = Decimal(str(checkout_data.get("total_price", "0.00")))
#         except (TypeError, InvalidOperation, KeyError) as e:
#             return {"status": 500, "message": f"Error processing initial booking price: {e}", "data": None}
#
#         final_price_after_discount = current_total_price_before_discount
#         applied_discount_amount = Decimal('0.00')
#         coupon_validation_message = None
#
#         # Initialize with default values to prevent field_errors
#         booking_applied_coupon_code_value = None
#         booking_applied_coupon_type_value = None
#         booking_applied_referral_coupon_pk = None
#         booking_applied_admin_coupon_pk = None
#
#         coupon_code_from_request = request_data.get('coupon_code')
#         if coupon_code_from_request:
#             coupon_info = validate_and_get_coupon_discount_info(
#                 coupon_code_input=coupon_code_from_request,
#                 order_total=current_total_price_before_discount,
#                 booking_user=user
#             )
#
#             # Always include a valid coupon_code_matched, even if invalid
#             coupon_validation_message = coupon_info.get('message', 'Coupon processing completed.')
#
#             # Set coupon_code_matched regardless of validity (user's input or default)
#             booking_applied_coupon_code_value = coupon_info.get('coupon_code_matched', coupon_code_from_request)
#
#             if coupon_info.get('is_valid', False):
#                 final_price_after_discount = coupon_info.get('final_price', current_total_price_before_discount)
#                 applied_discount_amount = coupon_info.get('discount_amount', Decimal('0.00'))
#                 booking_applied_coupon_type_value = coupon_info.get('coupon_type')
#
#                 if booking_applied_coupon_type_value == 'referral' and coupon_info.get('coupon_object'):
#                     booking_applied_referral_coupon_pk = coupon_info['coupon_object'].pk
#                 elif booking_applied_coupon_type_value == 'admin' and coupon_info.get('coupon_object'):
#                     booking_applied_admin_coupon_pk = coupon_info['coupon_object'].pk
#             else:
#                 print(f"GuestBookingProcess: Coupon validation failed: {coupon_validation_message}")
#                 # Proceed without discount, but keep the invalid coupon code for reference
#
#         # --- Prepare data_for_serializer ---
#         data_for_serializer = {
#             "invoice_no": identifier_builder(table_name="bookings_booking", prefix="BK"),
#             "guest": user.id,
#             "host": listing_obj.host_id,
#             "listing": listing_obj.id,
#             "check_in": from_date_str,
#             "check_out": to_date_str,
#             "night_count": checkout_data.get("nights", 0),
#             "children_count": int(request_data.get("children_count", 0)),
#             "adult_count": int(request_data.get("adult_count", 1)),
#             "infant_count": int(request_data.get("infant_count", 0)),
#             "price": float(checkout_data.get("booking_price", 0.00)),
#             "guest_service_charge": float(checkout_data.get("guest_service_charge", 0.00)),
#             "total_price": float(final_price_after_discount),  # Final price user pays
#             "paid_amount": 0.00,  # Will be updated after payment
#             "host_service_charge": float(checkout_data.get("host_service_charge", 0.00)),
#             "host_pay_out": float(Decimal(str(checkout_data.get("host_pay_out", 0.00)))),
#             "total_profit": float(checkout_data.get("total_profit", 0.00)),
#             "price_info": {},  # To be populated below
#             "calendar_info": [],  # To be populated below
#             "is_test_booking": request_data.get("test_booking", False),
#
#             # Coupon related fields - ensure all required fields have at least default values
#             "applied_coupon_code": booking_applied_coupon_code_value,  # Important: This was missing or inconsistent
#             "applied_coupon_type": booking_applied_coupon_type_value,
#             "applied_referral_coupon": booking_applied_referral_coupon_pk,
#             "applied_admin_coupon": booking_applied_admin_coupon_pk,
#             "discount_amount_applied": float(applied_discount_amount),  # Convert Decimal to float
#             "price_after_discount": float(final_price_after_discount),  # Convert Decimal to float
#
#             # Add the coupon_code_matched field explicitly to avoid the field_error
#             "coupon_code_matched": booking_applied_coupon_code_value,
#         }
#         # Calculate guest_count after individual counts are set
#         data_for_serializer["guest_count"] = data_for_serializer["children_count"] + data_for_serializer["adult_count"]
#
#         # Price info processing
#         raw_price_info_from_checkout = checkout_data.get("price_info", {})
#         cleaned_price_info_for_booking = {}
#         for key, entry_info in raw_price_info_from_checkout.items():
#             cleaned_entry = entry_info.copy()
#             cleaned_entry.pop("is_booked", None)
#             cleaned_entry.pop("is_blocked", None)
#             cleaned_entry.pop("id", None)
#             cleaned_price_info_for_booking[key] = cleaned_entry
#         data_for_serializer["price_info"] = cleaned_price_info_for_booking
#
#         # Calendar info processing
#         processed_calendar_info_for_booking = []
#         current_group = None
#         for date_key_str, entry_details in raw_calendar_data_for_period.items():
#             current_price_for_day = entry_details.get("price")
#             if current_price_for_day is None: continue
#             current_day_date_obj = datetime.strptime(date_key_str, "%Y-%m-%d").date()
#             if current_group is None:
#                 current_group = {
#                     "start_date": current_day_date_obj.isoformat(), "end_date": current_day_date_obj.isoformat(),
#                     "price": current_price_for_day, "base_price": listing_obj.price,
#                     "listing_id": listing_id, "is_blocked": True, "is_booked": True,
#                 }
#             elif current_price_for_day == current_group["price"] and \
#                 current_day_date_obj == (Date.fromisoformat(current_group["end_date"]) + timedelta(days=1)):
#                 current_group["end_date"] = current_day_date_obj.isoformat()
#             else:
#                 processed_calendar_info_for_booking.append(current_group)
#                 current_group = {
#                     "start_date": current_day_date_obj.isoformat(), "end_date": current_day_date_obj.isoformat(),
#                     "price": current_price_for_day, "base_price": listing_obj.price,
#                     "listing_id": listing_id, "is_blocked": True, "is_booked": True,
#                 }
#         if current_group is not None:
#             processed_calendar_info_for_booking.append(current_group)
#         data_for_serializer["calendar_info"] = processed_calendar_info_for_booking
#
#         final_api_message = "Booking data processed successfully."
#         if coupon_validation_message:
#             final_api_message = coupon_validation_message
#
#         return {"status": 200, "message": final_api_message, "data": data_for_serializer}


# bookings/views/service.py




# class GuestBookingProcess:
#
#     def _get_applicable_length_of_stay_discount_percent(self, listing: Listing, num_nights: int) -> Decimal:
#         if not listing.enable_length_of_stay_discount or not listing.length_of_stay_discounts or num_nights == 0:
#             return Decimal('0.00')
#         applicable_discount_percent = Decimal('0.00')
#         try:
#             valid_tiers = []
#             for days_str, perc_str in listing.length_of_stay_discounts.items():
#                 try:
#                     days_int = int(days_str)
#                     perc_decimal = Decimal(str(perc_str))
#                     if days_int > 0 and 0 < perc_decimal <= 100:
#                         valid_tiers.append((days_int, perc_decimal))
#                 except (ValueError, TypeError, InvalidOperation):
#                     print(
#                         f"Warning: Invalid LoS discount tier for listing {listing.id}: days='{days_str}', perc='{perc_str}'")
#                     continue
#             sorted_discount_tiers = sorted(valid_tiers, key=lambda item: item[0], reverse=True)
#             for min_days, discount_percent_val in sorted_discount_tiers:
#                 if num_nights >= min_days:
#                     applicable_discount_percent = discount_percent_val
#                     break
#         except Exception as e:
#             print(f"Error processing LoS discounts for listing {listing.id}: {e}")
#             return Decimal('0.00')
#         return applicable_discount_percent
#
#     def __call__(self, request_data: Dict[str, Any], user: User) -> Dict[str, Any]:
#         # --- 1. Basic Validations & Initial Data Fetch ---
#         current_date = Date.today()
#         listing_id = request_data.get("listing")
#         # ... (listing_id, listing_obj, from_date, to_date, date_filter validation as before) ...
#         if not listing_id: return {"status": 400, "message": "Listing ID is required.", "data": None}
#         try:
#             listing_obj = Listing.objects.get(id=listing_id)
#         except Listing.DoesNotExist:
#             return {"status": 404, "message": "Listing not found.", "data": None}
#
#         try:
#             from_date_str = request_data.get("check_in");
#             to_date_str = request_data.get("check_out")
#             if not from_date_str or not to_date_str: return {"status": 400,
#                                                              "message": "Check-in and Check-out dates are required.",
#                                                              "data": None}
#             from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
#             to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
#         except ValueError:
#             return {"status": 400, "message": "Invalid date format. Please use YYYY-MM-DD.", "data": None}
#
#         if not (from_date >= current_date and to_date > from_date):
#             return {"status": 400, "message": "Invalid booking date range.", "data": None}
#
#         number_of_nights = (to_date - from_date).days
#         if number_of_nights <= 0:  # Should be caught by to_date > from_date but good to be explicit
#             return {"status": 400, "message": "Booking must be for at least one night.", "data": None}
#
#         # --- 2. Length-of-Stay (LoS) Discount Calculation ---
#         host_base_nightly_price = Decimal(str(listing_obj.price))  # Host's defined base per-night price
#         effective_nightly_price_after_los = host_base_nightly_price
#         total_los_discount_amount = Decimal('0.00')
#         applied_los_discount_percent = Decimal('0.00')
#
#         applied_los_discount_percent = self._get_applicable_length_of_stay_discount_percent(listing_obj,
#                                                                                             number_of_nights)
#         if applied_los_discount_percent > 0:
#             discount_factor = applied_los_discount_percent / Decimal('100')
#             discount_amount_per_night = (host_base_nightly_price * discount_factor)
#             effective_nightly_price_after_los = (host_base_nightly_price - discount_amount_per_night)
#             total_los_discount_amount = (discount_amount_per_night * Decimal(number_of_nights))
#             print(
#                 f"LoS discount: {applied_los_discount_percent}%. Original nightly: {host_base_nightly_price}, New nightly: {effective_nightly_price_after_los}. Total LoS discount: {total_los_discount_amount}")
#
#         # Total cost of accommodation for all nights, after LoS discount
#         accommodation_charge_after_los = (effective_nightly_price_after_los * Decimal(number_of_nights)).quantize(
#             Decimal('0.01'), rounding=ROUND_HALF_UP)
#
#         # --- 3. Get Other Price Components (Service Fee, etc.) ---
#         # We need to get these *before* applying generic coupon, as they might be based on the accommodation charge.
#         # This assumes ListingCheckoutCalculate can provide these components, or you have another way.
#         # For now, let's assume checkout_data from your original code provides them based on original prices.
#         # We will use the service charge from it and apply it to accommodation_charge_after_los.
#
#         date_filter = {"from_date": from_date, "to_date": to_date}
#         calendar_data_process = ListingCalendarDataProcess()  # Assuming this is needed by CheckoutCalculator
#         raw_calendar_data_for_period = calendar_data_process(date_filter, listing_id)
#         if not raw_calendar_data_for_period:  # Should have been caught earlier if no availability
#             return {"status": 400, "message": "No pricing information for selected dates.", "data": None}
#
#         checkout_calculator = ListingCheckoutCalculate()
#         checkout_data_result = checkout_calculator(
#             booking_date_info=raw_calendar_data_for_period.copy(),
#             date_range=date_filter, instance=listing_obj,
#             # Pass the effective_nightly_price if your calculator can use it
#             # custom_nightly_rate_after_los=effective_nightly_price_after_los
#         )
#         if checkout_data_result["status"] != 200: return checkout_data_result
#         checkout_data = checkout_data_result["data"]
#
#         # Extract service charge. IMPORTANT: If guest_service_charge is a percentage,
#         # it should be calculated on `accommodation_charge_after_los`.
#         # If ListingCheckoutCalculate doesn't do this, you must adjust here.
#         guest_service_charge = Decimal(str(checkout_data.get("guest_service_charge", "0.00")))
#         # Example: If service charge is 10% of accommodation:
#         # GUEST_SERVICE_CHARGE_PERCENT = Decimal('0.10') # From settings
#         # guest_service_charge = (accommodation_charge_after_los * GUEST_SERVICE_CHARGE_PERCENT).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
#
#         # Subtotal before generic coupon
#         subtotal_before_generic_coupon = (accommodation_charge_after_los + guest_service_charge).quantize(
#             Decimal('0.01'), rounding=ROUND_HALF_UP)
#
#         # --- 4. Apply Generic Coupon ---
#         price_after_generic_coupon = subtotal_before_generic_coupon
#         generic_coupon_discount_amount = Decimal('0.00')
#         coupon_validation_message = "No coupon applied."
#
#         booking_applied_coupon_code_value = None
#         booking_applied_coupon_type_value = None
#         booking_applied_referral_coupon_pk = None
#         booking_applied_admin_coupon_pk = None
#
#         coupon_code_from_request = request_data.get('coupon_code')
#         if coupon_code_from_request:
#             coupon_info = validate_and_get_coupon_discount_info(
#                 coupon_code_input=coupon_code_from_request,
#                 order_total=subtotal_before_generic_coupon,  # Base for generic coupon
#                 booking_user=user
#             )
#             coupon_validation_message = coupon_info.get('message', 'Coupon processing failed.')
#             booking_applied_coupon_code_value = coupon_info.get('coupon_code_matched', coupon_code_from_request)
#
#             if coupon_info.get('is_valid', False):
#                 price_after_generic_coupon = coupon_info['final_price']
#                 generic_coupon_discount_amount = coupon_info['discount_amount']
#                 booking_applied_coupon_type_value = coupon_info['coupon_type']
#                 if booking_applied_coupon_type_value == 'referral' and coupon_info.get('coupon_object'):
#                     booking_applied_referral_coupon_pk = coupon_info['coupon_object'].pk
#                 elif booking_applied_coupon_type_value == 'admin' and coupon_info.get('coupon_object'):
#                     booking_applied_admin_coupon_pk = coupon_info['coupon_object'].pk
#             else:
#                 # Coupon invalid, price_after_generic_coupon remains subtotal_before_generic_coupon
#                 print(f"GuestBookingProcess: Generic coupon validation failed: {coupon_validation_message}")
#
#         # --- 5. Add Gateway Fee & Calculate Final Total Price ---
#         # Assuming gateway_fee might also be a percentage of `price_after_generic_coupon` or fixed.
#         # For now, let's assume it's a fixed value from checkout_data or calculated based on price_after_generic_coupon.
#         # This example assumes gateway_fee is fixed or already calculated appropriately by ListingCheckoutCalculate initially.
#         # If it needs recalculation (e.g., % of price_after_generic_coupon), do it here.
#         gateway_fee = Decimal(str(checkout_data.get("gateway_fee", "0.00")))
#
#         final_total_price_payable = (price_after_generic_coupon + gateway_fee).quantize(Decimal('0.01'),
#                                                                                         rounding=ROUND_HALF_UP)
#
#         # --- 6. Prepare Data for BookingSerializer ---
#         data_for_serializer = {
#             "invoice_no": identifier_builder(table_name="bookings_booking", prefix="BK"),
#             "guest": user.id, "host": listing_obj.host_id, "listing": listing_obj.id,
#             "check_in": from_date_str, "check_out": to_date_str,
#             "night_count": number_of_nights,
#             "children_count": int(request_data.get("children_count", 0)),
#             "adult_count": int(request_data.get("adult_count", 1)),
#             "infant_count": int(request_data.get("infant_count", 0)),
#
#             "price": float(effective_nightly_price_after_los),  # Avg per-night rate after LoS discount
#             # NEW/CLARIFIED Fields:
#             "accommodation_charge": float(accommodation_charge_after_los),  # Total for nights after LoS
#             "guest_service_charge": float(guest_service_charge),
#             "subtotal_before_generic_coupon": float(subtotal_before_generic_coupon),
#             # For clarity if needed on Booking model
#
#             "discount_amount_applied": float(generic_coupon_discount_amount),  # ONLY generic coupon discount
#             "price_after_discount": float(price_after_generic_coupon),  # Price before gateway fee
#
#             "gateway_fee": float(gateway_fee),
#             "total_price": float(final_total_price_payable),  # FINAL amount guest pays
#             "paid_amount": 0.00,
#
#             "host_service_charge": float(checkout_data.get("host_service_charge", 0.00)),  # Needs careful re-evaluation
#             "host_pay_out": float(checkout_data.get("host_pay_out", 0.00)),  # Needs careful re-evaluation
#             "total_profit": float(checkout_data.get("total_profit", 0.00)),  # Needs careful re-evaluation
#
#             "is_test_booking": request_data.get("test_booking", False),
#
#             "applied_coupon_code": booking_applied_coupon_code_value,
#             "applied_coupon_type": booking_applied_coupon_type_value,
#             "applied_referral_coupon": booking_applied_referral_coupon_pk,
#             "applied_admin_coupon": booking_applied_admin_coupon_pk,
#
#             # Optional: Store LoS discount details if needed on Booking model
#             # "length_of_stay_discount_percent_applied": float(applied_los_discount_percent),
#             # "total_length_of_stay_discount": float(total_los_discount_amount),
#         }
#         data_for_serializer["guest_count"] = data_for_serializer["children_count"] + data_for_serializer["adult_count"]
#
#         # Price info and calendar info: These should reflect the `effective_nightly_price_after_los`
#         # This logic needs to ensure the daily prices in price_info and calendar_info are correct.
#         # If ListingCheckoutCalculate's raw_calendar_data_for_period already has complex daily prices,
#         # applying a flat LoS discount might be an oversimplification.
#         # For true accuracy, LoS discount should be applied to each day's base rate before summing.
#
#         updated_price_info_for_booking = {}  # Rebuild based on effective_nightly_price_after_los
#         for date_key_str, _ in raw_calendar_data_for_period.items():
#             updated_price_info_for_booking[date_key_str] = {
#                 "price": float(effective_nightly_price_after_los),
#                 "base_price": float(host_base_nightly_price),
#             }
#         data_for_serializer["price_info"] = updated_price_info_for_booking
#
#         processed_calendar_info_for_booking = []  # Rebuild based on effective_nightly_price_after_los
#         current_group = None
#         for date_key_str, _ in raw_calendar_data_for_period.items():
#             current_day_date_obj = datetime.strptime(date_key_str, "%Y-%m-%d").date()
#             price_for_this_day_group = effective_nightly_price_after_los  # Simplification
#             if current_group is None:
#                 current_group = {"start_date": current_day_date_obj.isoformat(),
#                                  "end_date": current_day_date_obj.isoformat(),
#                                  "price": float(price_for_this_day_group), "base_price": float(host_base_nightly_price),
#                                  "listing_id": listing_id, "is_blocked": True, "is_booked": True}
#             elif Decimal(str(current_group["price"])) == price_for_this_day_group and \
#                 current_day_date_obj == (Date.fromisoformat(current_group["end_date"]) + timedelta(days=1)):
#                 current_group["end_date"] = current_day_date_obj.isoformat()
#             else:
#                 processed_calendar_info_for_booking.append(current_group)
#                 current_group = {"start_date": current_day_date_obj.isoformat(),
#                                  "end_date": current_day_date_obj.isoformat(),
#                                  "price": float(price_for_this_day_group), "base_price": float(host_base_nightly_price),
#                                  "listing_id": listing_id, "is_blocked": True, "is_booked": True}
#         if current_group is not None: processed_calendar_info_for_booking.append(current_group)
#         data_for_serializer["calendar_info"] = processed_calendar_info_for_booking
#
#         return {"status": 200, "message": coupon_validation_message, "data": data_for_serializer}

GUEST_GOOD_TRACK_RECORD_MIN_RATING = Decimal('5')

class GuestBookingProcess:

    def _get_applicable_length_of_stay_discount_percent(self, listing: Listing, num_nights: int) -> Decimal:
        if not listing.enable_length_of_stay_discount or not listing.length_of_stay_discounts or num_nights == 0:
            return Decimal('0.00')
        applicable_discount_percent = Decimal('0.00')
        try:
            valid_tiers = []
            for days_str, perc_str in listing.length_of_stay_discounts.items():
                try:
                    days_int = int(days_str)
                    perc_decimal = Decimal(str(perc_str))
                    if days_int > 0 and 0 < perc_decimal <= 100:
                        valid_tiers.append((days_int, perc_decimal))
                except (ValueError, TypeError, InvalidOperation):
                    print(
                        f"Warning: Invalid LoS discount tier for listing {listing.id}: days='{days_str}', perc='{perc_str}'")
                    continue
            sorted_discount_tiers = sorted(valid_tiers, key=lambda item: item[0], reverse=True)
            for min_days, discount_percent_val in sorted_discount_tiers:
                if num_nights >= min_days:
                    applicable_discount_percent = discount_percent_val
                    break
        except Exception as e:
            print(f"Error processing LoS discounts for listing {listing.id}: {e}")
            return Decimal('0.00')
        return applicable_discount_percent

    def __call__(self, request_data: Dict[str, Any], user: User) -> Dict[str, Any]:
        # --- 1. Basic Validations & Initial Data Fetch ---
        current_date = Date.today()
        listing_id = request_data.get("listing")
        if not listing_id: return {"status": 400, "message": "Listing ID is required.", "data": None}
        try:
            listing_obj = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return {"status": 404, "message": "Listing not found.", "data": None}

        if listing_obj.require_guest_good_track_record:

            guest_avg_rating_str = str(getattr(user, 'avg_rating', '0.0'))
            try:
                guest_avg_rating = Decimal(guest_avg_rating_str)
            except InvalidOperation:
                guest_avg_rating = Decimal('0.0')

            if guest_avg_rating < GUEST_GOOD_TRACK_RECORD_MIN_RATING:
                return {
                    "status": 403,
                    "message": f"This listing requires guests to have a good track record (average rating of at least {GUEST_GOOD_TRACK_RECORD_MIN_RATING} stars). Your current average rating is {guest_avg_rating:.2f}.",
                    "data": None
                }
            print(f"Guest {user.username} meets good track record requirement for listing {listing_obj.id}.")

        try:
            from_date_str = request_data.get("check_in")
            to_date_str = request_data.get("check_out")
            if not from_date_str or not to_date_str: return {"status": 400,
                                                             "message": "Check-in and Check-out dates are required.",
                                                             "data": None}
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"status": 400, "message": "Invalid date format. Please use YYYY-MM-DD.", "data": None}

        if not (from_date >= current_date and to_date > from_date):
            return {"status": 400, "message": "Invalid booking date range.", "data": None}

        number_of_nights = (to_date - from_date).days
        if number_of_nights <= 0: return {"status": 400, "message": "Booking must be for at least one night.",
                                          "data": None}

        pricing_end_date = to_date - timedelta(days=1)
        pricing_date_filter = {"from_date": from_date, "to_date": pricing_end_date}
        original_date_range_for_validation = {"from_date": from_date, "to_date": to_date}

        # date_filter = {"from_date": from_date, "to_date": to_date}

        # --- 2. Get Raw Calendar Data & Apply Length-of-Stay (LoS) Discount to Daily Rates ---
        calendar_data_process = ListingCalendarDataProcess()
        raw_calendar_data_for_period = calendar_data_process(pricing_date_filter, listing_id)
        if not raw_calendar_data_for_period:
            return {"status": 400, "message": "No availability or pricing information for selected dates.",
                    "data": None}

        # This is the host's defined base per-night price from the Listing model
        host_base_nightly_price_from_listing = Decimal(str(listing_obj.price))

        applied_los_discount_percent = self._get_applicable_length_of_stay_discount_percent(listing_obj,
                                                                                            number_of_nights)

        los_discounted_calendar_data = {}  # This will store daily prices AFTER LoS discount
        total_accommodation_cost_before_los = Decimal('0.00')  # Sum of original daily prices from calendar
        total_los_discount_value = Decimal('0.00')  # Total LoS discount amount

        for date_str, entry_details in raw_calendar_data_for_period.items():
            # original_daily_price from the calendar might be different from listing_obj.price due to custom pricing
            original_daily_price_from_calendar = Decimal(str(entry_details.get("price", "0.00")))
            total_accommodation_cost_before_los += original_daily_price_from_calendar

            effective_daily_price_after_los = original_daily_price_from_calendar
            if applied_los_discount_percent > 0:
                # Apply LoS discount to the specific daily price from the calendar
                daily_los_discount_amount = (
                        original_daily_price_from_calendar * (applied_los_discount_percent / Decimal('100'))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                effective_daily_price_after_los = (
                        original_daily_price_from_calendar - daily_los_discount_amount).quantize(Decimal('0.01'),
                                                                                                 rounding=ROUND_HALF_UP)
                total_los_discount_value += daily_los_discount_amount

            los_discounted_calendar_data[date_str] = {
                **entry_details,
                "price": effective_daily_price_after_los,
                "original_calendar_price": original_daily_price_from_calendar  # Store the calendar's price for this day
            }

        accommodation_charge_after_los = (total_accommodation_cost_before_los - total_los_discount_value).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        average_effective_nightly_price_after_los = (
            accommodation_charge_after_los / Decimal(number_of_nights+1) if number_of_nights > 0 else Decimal(
                '0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        print(" accommodation_charge_after_los, -------------------- ", accommodation_charge_after_los)
        if applied_los_discount_percent > 0:
            print(
                f"Applied LoS discount: {applied_los_discount_percent}%. Total LoS discount: {total_los_discount_value}. Accomm. charge after LoS: {accommodation_charge_after_los}")

        # --- 3. Calculate Checkout Data (Service Fees etc.) using LoS-Discounted Daily Rates ---
        checkout_calculator = ListingCheckoutCalculate()
        # IMPORTANT: ListingCheckoutCalculate's `booking_date_info` parameter expects daily prices.
        # We pass `los_discounted_calendar_data` where each day's "price" is already LoS discounted.
        checkout_data_result = checkout_calculator(
            booking_date_info=los_discounted_calendar_data.copy(),
            date_range=original_date_range_for_validation,
            instance=listing_obj,
        )
        if checkout_data_result["status"] != 200: return checkout_data_result
        checkout_data_after_los = checkout_data_result["data"]
        # Now:
        # checkout_data_after_los['booking_price'] = sum of LoS discounted daily rates (same as accommodation_charge_after_los)
        # checkout_data_after_los['guest_service_charge'] = calculated on this new 'booking_price'
        # checkout_data_after_los['total_price'] = new 'booking_price' + new 'guest_service_charge'

        subtotal_before_generic_coupon = Decimal(str(checkout_data_after_los.get("total_price", "0.00")))

        # --- 4. Apply Generic Coupon ---
        final_price_to_pay = subtotal_before_generic_coupon  # Initialize with price after LoS and service fees
        generic_coupon_discount_amount = Decimal('0.00')
        coupon_validation_message = "No coupon applied."
        booking_applied_coupon_code_value = None
        booking_applied_coupon_type_value = None
        booking_applied_referral_coupon_pk = None
        booking_applied_admin_coupon_pk = None

        coupon_code_from_request = request_data.get('coupon_code')
        if coupon_code_from_request:
            # ... (generic coupon logic remains the same, using subtotal_before_generic_coupon as order_total) ...
            coupon_info = validate_and_get_coupon_discount_info(
                coupon_code_input=coupon_code_from_request,
                order_total=subtotal_before_generic_coupon,
                booking_user=user
            )
            coupon_validation_message = coupon_info.get('message', 'Coupon processing failed.')
            booking_applied_coupon_code_value = coupon_info.get('coupon_code_matched', coupon_code_from_request)
            if coupon_info.get('is_valid', False):
                final_price_to_pay = coupon_info['final_price']
                generic_coupon_discount_amount = coupon_info['discount_amount']
                booking_applied_coupon_type_value = coupon_info['coupon_type']
                if booking_applied_coupon_type_value == 'referral' and coupon_info.get('coupon_object'):
                    booking_applied_referral_coupon_pk = coupon_info['coupon_object'].pk
                elif booking_applied_coupon_type_value == 'admin' and coupon_info.get('coupon_object'):
                    booking_applied_admin_coupon_pk = coupon_info['coupon_object'].pk
            else:
                print(f"GuestBookingProcess: Generic coupon validation failed: {coupon_validation_message}")

        # --- 5. Add Gateway Fee (if applicable and not already in final_price_to_pay) ---
        # Assuming gateway_fee is either fixed or calculated by ListingCheckoutCalculate based on its inputs
        gateway_fee = Decimal(
            str(checkout_data_after_los.get("gateway_fee", "0.00")))  # Get gateway_fee from the latest checkout_data
        grand_total_payable = (final_price_to_pay + gateway_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        original_total_before_discounts = float(total_accommodation_cost_before_los)
        # --- 6. Prepare Data for BookingSerializer ---
        data_for_serializer = {
            "invoice_no": identifier_builder(table_name="bookings_booking", prefix="BK"),
            "guest": user.id, "host": listing_obj.host_id, "listing": listing_obj.id,
            "check_in": from_date_str, "check_out": to_date_str,
            "night_count": number_of_nights,
            "children_count": int(request_data.get("children_count", 0)),
            "adult_count": int(request_data.get("adult_count", 1)),
            "infant_count": int(request_data.get("infant_count", 0)),

            "original_price_before_discount": original_total_before_discounts,
            "total_discount_amount": float(total_los_discount_value + generic_coupon_discount_amount),

            # `price` on Booking model stores the average effective nightly rate after LoS discount
            "price": float((float(average_effective_nightly_price_after_los) * float(number_of_nights+1))),
            # `accommodation_charge` stores total for nights after LoS discount (NEW Booking model field)
            "accommodation_charge": float(accommodation_charge_after_los),

            "guest_service_charge": float(checkout_data_after_los.get("guest_service_charge", 0.00)),
            # `subtotal_before_generic_coupon` (NEW Booking model field)
            "subtotal_before_generic_coupon": float(subtotal_before_generic_coupon),

            "discount_amount_applied": float(generic_coupon_discount_amount),  # Generic coupon's discount
            # `price_after_discount` is after LoS AND generic coupon, before gateway fee
            "price_after_discount": float(final_price_to_pay),

            "gateway_fee": float(gateway_fee),
            "total_price": float(grand_total_payable),  # FINAL amount guest pays
            "paid_amount": 0.00,  # Initial value

            "host_service_charge": float(checkout_data_after_los.get("host_service_charge", 0.00)),
            "host_pay_out": float(checkout_data_after_los.get("host_pay_out", 0.00)),
            "total_profit": float(checkout_data_after_los.get("total_profit", 0.00)),

            "is_test_booking": request_data.get("test_booking", False),

            "applied_coupon_code": booking_applied_coupon_code_value,
            "applied_coupon_type": booking_applied_coupon_type_value,
            "applied_referral_coupon": booking_applied_referral_coupon_pk,
            "applied_admin_coupon": booking_applied_admin_coupon_pk,

            # Optional: Store LoS discount details if new fields on Booking model
            # "length_of_stay_discount_percent_applied": float(applied_los_discount_percent),
            # "total_length_of_stay_discount_value": float(total_los_discount_value),

            "length_of_stay_discount_percent": float(applied_los_discount_percent),
            "length_of_stay_discount_amount": float(total_los_discount_value),

        }
        data_for_serializer["guest_count"] = data_for_serializer["children_count"] + data_for_serializer["adult_count"]



        # `price_info` should reflect the daily breakdown *after* LoS discount
        data_for_serializer["price_info"] = {
            date_str: {
                "id": details.get("id"),
                "price": float(details["price"]),  # This is the LoS discounted daily price
                "is_blocked": details.get("is_blocked", False),
                "is_booked": details.get("is_booked", False),
                "booking_data": details.get("booking_data"),
                "note": details.get("note"),
                "original_calendar_price": float(details.get("original_calendar_price", details["price"]))
            } for date_str, details in los_discounted_calendar_data.items()
        }

        # `calendar_info` for storing booking ranges
        # This grouping logic uses the *average* LoS discounted price.
        # If daily prices vary wildly even after LoS, this grouping might simplify too much.
        # The `price_info` above provides the true daily breakdown.
        processed_calendar_info_for_booking = []
        current_group = None
        for date_key_str, daily_detail in los_discounted_calendar_data.items():
            current_day_date_obj = datetime.strptime(date_key_str, "%Y-%m-%d").date()
            # Use the actual LoS discounted price for this day for grouping
            price_for_this_day_in_group = daily_detail["price"]

            if current_group is None:
                current_group = {"start_date": current_day_date_obj.isoformat(),
                                 "end_date": current_day_date_obj.isoformat(),
                                 "price": float(price_for_this_day_in_group),
                                 "base_price": float(
                                     daily_detail.get("original_calendar_price", host_base_nightly_price_from_listing)),
                                 # Original daily price before LoS
                                 "listing_id": listing_id, "is_blocked": True, "is_booked": True}
            elif Decimal(str(current_group["price"])) == price_for_this_day_in_group and \
                current_day_date_obj == (Date.fromisoformat(current_group["end_date"]) + timedelta(days=1)):
                current_group["end_date"] = current_day_date_obj.isoformat()
            else:
                processed_calendar_info_for_booking.append(current_group)
                current_group = {"start_date": current_day_date_obj.isoformat(),
                                 "end_date": current_day_date_obj.isoformat(),
                                 "price": float(price_for_this_day_in_group),
                                 "base_price": float(
                                     daily_detail.get("original_calendar_price", host_base_nightly_price_from_listing)),
                                 "listing_id": listing_id, "is_blocked": True, "is_booked": True}
        if current_group is not None: processed_calendar_info_for_booking.append(current_group)
        data_for_serializer["calendar_info"] = processed_calendar_info_for_booking

        print(" === ", data_for_serializer, " ===")

        return {"status": 200, "message": coupon_validation_message, "data": data_for_serializer}


class BookingReviewProcess:
    def update_ratings(self, obj: Listing | User, rating: int) -> None:
        updated_total_rating_count = obj.total_rating_count + 1
        updated_total_rating_sum = obj.total_rating_sum + float(rating)
        update_avg_rating = updated_total_rating_sum / updated_total_rating_count

        obj.total_rating_count = updated_total_rating_count
        obj.total_rating_sum = updated_total_rating_sum
        obj.avg_rating = update_avg_rating
        obj.save()

    def validate_booking_review_data(
        self,
        data: dict,
        invoice_no: str,
        user: User,
    ) -> dict:
        current_date = Date.today()

        filter_param = {
            "invoice_no": invoice_no,
            "status": BookingStatusOption.CONFIRMED,
            # "check_out__lt": current_date,
        }

        booking_obj = Booking.objects.get(**filter_param)

        if user.u_type == UserTypeOption.GUEST:
            filter_param["guest_id"] = user.id
            review_for_id = booking_obj.host_id
        else:
            filter_param["host_id"] = user.id
            review_for_id = booking_obj.guest_id

        if booking_obj.check_out > current_date:
            return {
                "message": "Invalid booking or you can add review after checkout date",
                "status": 400,
            }

        if ListingBookingReview.objects.filter(
            booking_id=booking_obj.id, review_by_id=user.id
        ).exists():
            return {
                "message": "You have already add review for this booking",
                "status": 400,
            }

        booking_review_data = {
            "status": 200,
            "review_data": {
                "listing_id": booking_obj.listing_id,
                "booking_id": booking_obj.id,
                "review_by_id": user.id,
                "review_for_id": review_for_id,
                "is_guest_review": user.u_type == UserTypeOption.GUEST,
                "is_host_review": user.u_type == UserTypeOption.HOST,
                "rating": data.get("rating"),
                "review": data.get("review"),
            },
            "booking_obj": booking_obj,
        }

        return booking_review_data


class BookingDataFilterProcess:
    def __call__(self, query_param, current_user):
        current_date = Date.today()
        if query_param == "currently_hosting":
            qs = Booking.objects.filter(
                Q(check_in__lte=current_date) & Q(check_out__gte=current_date),
                host_id=current_user.id,
                status=BookingStatusOption.CONFIRMED,
            )
        elif query_param == "completed":
            qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                check_out__lt=current_date,
                host_id=current_user.id,
            )
        elif query_param == "upcoming":
            qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                check_in__gt=current_date,
                host_id=current_user.id,
            )
        elif query_param == "pending_review":
            qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_review_done=False,
                host_id=current_user.id,
                check_out__lt=current_date,
            )
        elif query_param == "checking_out":
            qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_id=current_user.id,
                check_out=current_date,
            )
        elif query_param == "arriving_soon":
            qs = Booking.objects.filter(
                status=BookingStatusOption.CONFIRMED,
                host_id=current_user.id,
                # check_in__gte=current_date + timedelta(days=3),
                check_in__gte=current_date + timedelta(days=1),
                check_in__lte=current_date + timedelta(days=7),
            )
        else:
            qs = Booking.objects.filter(
                host_id=current_user.id,
                status=BookingStatusOption.CONFIRMED,
            )

        return qs
