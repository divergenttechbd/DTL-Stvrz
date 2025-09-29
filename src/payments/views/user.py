from datetime import timedelta, date

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db import IntegrityError
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.generics import CreateAPIView, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import UserSerializer

from accounts.tasks.users import send_sms
from base.helpers.decorators import exception_handler
from base.helpers.utils import identifier_builder
from base.type_choices import (
    BookingStatusOption,
    OnlinePaymentMethodOption,
    OnlinePaymentStatusOption,
    PaymentStatusOption, NotificationTypeOption, NotificationEventTypeOption,
)
from bookings.models import Booking
from bookings.serializers import BookingSerializer
from listings.models import Listing, ListingCalendar
from listings.views.service import ListingCalendarDataProcess
from notifications.models import Notification
from notifications.utils import create_notification, send_notification
from payments.models import OnlinePayment
from payments.serializers import OnlinePaymentSerializer
from payments.tasks.booking import booking_confirmed_process
from payments.views.service import (
    sslcommerz_payment_create,
    sslcommerz_payment_validation,
)


@method_decorator(csrf_exempt, name='dispatch')
class UserSSLCommerzOrderPaymentView(CreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = OnlinePaymentSerializer
    swagger_tags = ["Payments"]

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        invoice_no = request.data.get("booking")
        if not invoice_no:
            return Response({"message": "Booking invoice number is required."}, status=status.HTTP_400_BAD_REQUEST)

        # --- FIX: Define variables in the outer scope ---
        booking = None
        transaction_number = None

        try:
            with transaction.atomic():
                try:
                    # Assign to the booking variable defined in the outer scope
                    booking = Booking.objects.select_for_update().get(
                        invoice_no=invoice_no,
                        guest=request.user
                    )
                except Booking.DoesNotExist:
                    # Return immediately if booking not found
                    return Response({"message": "Booking not found or does not belong to you."},
                                    status=status.HTTP_404_NOT_FOUND)

                # --- Validation Checks ---
                if booking.guest_payment_status == PaymentStatusOption.PAID:
                    return Response({"message": "Payment already done for this booking."},
                                    status=status.HTTP_400_BAD_REQUEST)

                allowed_statuses = [BookingStatusOption.ACCEPTED, BookingStatusOption.INITIATED]
                if booking.status not in allowed_statuses:
                    return Response({
                                        "message": f"Payment can only be made for accepted/ initialed bookings. Current status is '{booking.get_status_display()}'."},
                                    status=status.HTTP_400_BAD_REQUEST)

                today = date.today()
                if booking.check_in < today:
                    booking.status = BookingStatusOption.DECLINED
                    booking.cancellation_reason = "System cancelled: Payment was not completed before the check-in date."
                    booking.save()
                    return Response(
                        {"message": "Cannot initiate payment for a booking with a past check-in date."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # --- Final Availability Check ---
                listing = booking.listing
                calendar_check_end_date = booking.check_out - timedelta(days=1)
                calendar_data_process = ListingCalendarDataProcess()
                availability_data = calendar_data_process(
                    data={"from_date": booking.check_in, "to_date": calendar_check_end_date},
                    listing_id=listing.id
                )

                for date_str, data in availability_data.items():
                    if data.get("is_blocked") or data.get("is_booked"):
                        booking.status = BookingStatusOption.DECLINED
                        booking.cancellation_reason = "System cancelled: Dates unavailable before payment."
                        booking.save()
                        return Response(
                            {
                                "message": f"Sorry, the date {date_str} is no longer available. Your booking has been cancelled."},
                            status=status.HTTP_409_CONFLICT
                        )

                # --- Find or Create OnlinePayment Record ---
                online_payment, created = OnlinePayment.objects.get_or_create(
                    booking=booking,
                    defaults={
                        'payment_method': OnlinePaymentMethodOption.SSL_COMMERZ,
                        'user': booking.guest,
                        'amount': booking.total_price,
                        'status': OnlinePaymentStatusOption.INITIATED,
                        'transaction_number': identifier_builder(table_name="payments_onlinepayment", prefix="PGDBK"),
                    }
                )

                if not created:
                    if online_payment.status == OnlinePaymentStatusOption.COMPLETED:
                        return Response({"message": "Payment has already been completed."},
                                        status=status.HTTP_400_BAD_REQUEST)

                    online_payment.transaction_number = identifier_builder(table_name="payments_onlinepayment",
                                                                           prefix="PGDBK")
                    online_payment.status = OnlinePaymentStatusOption.INITIATED
                    online_payment.save()

                # Assign the final transaction_number to the outer scope variable
                transaction_number = online_payment.transaction_number

                # Update booking with the latest codes
                booking.pgw_transaction_number = transaction_number
                booking.reservation_code = booking.reservation_code or identifier_builder(table_name="bookings_booking",
                                                                                          prefix="RES")
                booking.save()

        except IntegrityError:
            return Response({"message": "A database error occurred. Please try again."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- After the transaction, booking and transaction_number are now accessible ---

        # Prepare data for the external API call
        sslcommerz_data = {
            "total_amount": booking.total_price,
            "tran_id": transaction_number,
            "value_a": booking.invoice_no,
            "success_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/success/{booking.invoice_no}/",
            "fail_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/fail/{booking.invoice_no}/",
            "cancel_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/cancel/{booking.invoice_no}/",
            "ipn_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/sslcommerz/ipn/",
            "cus_name": request.user.get_full_name() or "Guest",
            "cus_email": request.user.email or "guest@example.com",
            "cus_phone": request.user.phone_number,
            "value_b": request.user.username,
            "num_of_item": 1,
            "product_name": "Assistance Booking",
            "product_category": "Service",
            "product_profile": "non-physical-goods",
        }

        # Make the external call
        response = sslcommerz_payment_create(data=sslcommerz_data, customer=request.user)

        if not response or response.get("status") != 'SUCCESS':
            return Response(
                {"message": "Failed to connect to the payment gateway. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # This code is now reachable
        res_data = {
            "payment_gateway_url": response["GatewayPageURL"],
            "success_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/success/{booking.invoice_no}/",
            "fail_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/fail/{booking.invoice_no}/",
            "cancel_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/cancel/{booking.invoice_no}/",
            "logo": response["storeLogo"],
        }

        return Response(res_data, status=status.HTTP_201_CREATED)


class CustomerSSLCommerzIPNView(views.APIView):
    permission_classes = (AllowAny,)


    def post(self, request):

        print("=== IPN VIEW HIT ===")
        print("Request Headers:", request.headers)
        print("Request Body:", request.body.decode('utf-8'))

        try:
            if (
                not request.data.get("tran_id")
                or not request.data.get("value_a")
                or not request.data.get("value_b")
            ):
                return Response(
                    {"message": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST
                )
            online_payment = OnlinePayment.objects.get(
                transaction_number=request.data["tran_id"],
                status=OnlinePaymentStatusOption.INITIATED,
            )
            online_payment.has_hit_ipn = True
            booking = online_payment.booking

            print(" --------------- ipn -------------------")
            if not request.data.get("status") == "VALID":
                online_payment.status = OnlinePaymentStatusOption.CANCELLED
                online_payment.meta = self.request.data
                online_payment.save()
                return Response(
                    {"message": "Payment is invalid"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            params = {
                "val_id": request.data.get("val_id"),
            }
            response = sslcommerz_payment_validation(query_params=params)
            if not response:
                return Response(
                    {"message": "No response from SSLCommerz validation API"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            online_payment.meta = {
                "ipn_response": self.request.data,
                "validation_response": response,
            }

            with transaction.atomic():
                if response.get("risk_level") == "0":
                    online_payment.status = OnlinePaymentStatusOption.COMPLETED

                    booking.guest_payment_status = PaymentStatusOption.PAID
                    booking.status = BookingStatusOption.CONFIRMED
                    booking.paid_amount = online_payment.amount

                    Listing.objects.filter(id=booking.listing_id).update(
                        total_booking_count=F("total_booking_count") + 1
                    )


                    # ------
                    event_type = NotificationEventTypeOption.BOOKING_CONFIRMED
                    guest_notification = create_notification(
                        event_type=event_type,
                        data={
                            "identifier": booking.invoice_no,
                            "message": "Congratulations! You’ve successfully completed your booking.",
                            # This link is crucial for mobile deep-linking
                            "link": f"/my-bookings/{booking.invoice_no}",
                        },
                        n_type=NotificationTypeOption.USER_NOTIFICATION,
                        user_id=booking.guest_id,
                    )

                    # 2. Create notification for the Host
                    host_notification = create_notification(
                        event_type=event_type,
                        data={
                            "identifier": booking.invoice_no,
                            "message": ( f"📢 Great news! "
                                            f"Your property '{booking.listing.title}' has just been booked "
                                            f"from {booking.check_in} to {booking.check_out} "
                                            f"({booking.night_count} nights, {booking.guest_count} guests)."
                                        ),
                            # This link takes the host to their dashboard
                            "link": f"/host-dashboard/bookings/{booking.invoice_no}",
                        },
                        n_type=NotificationTypeOption.USER_NOTIFICATION,
                        user_id=booking.host_id,
                    )

                    # This list will be used twice: once to save, once to send.
                    notification_data = [guest_notification, host_notification]

                    # 3. Save notifications to the DB within the transaction
                    Notification.objects.bulk_create(
                        [Notification(**item) for item in notification_data]
                    )
                    # =====



                    booking_data = {
                        "user": UserSerializer(
                            booking.guest,
                            fields=[
                                "id",
                                "full_name",
                                "image",
                                "u_type",
                                "phone_number",
                                "email",
                            ],
                        ).data,
                        "booking": BookingSerializer(
                            booking, fields=["id", "invoice_no", "reservation_code"]
                        ).data,
                    }

                    for entry in booking.calendar_info:
                        start_date = entry["start_date"]
                        end_date = entry["end_date"]

                        defaults = {
                            "base_price": entry["base_price"],
                            "custom_price": entry["price"],
                            "is_blocked": entry["is_blocked"],
                            "is_booked": entry["is_booked"],
                            "booking_data": booking_data,
                        }

                        obj, created = ListingCalendar.objects.update_or_create(
                            listing_id=entry["listing_id"],
                            start_date=start_date,
                            end_date=end_date,
                            defaults=defaults,
                        )

                        # if not created:
                        #     for key, value in defaults.items():
                        #         setattr(obj, key, value)
                        #     obj.save()

                        entry["id"] = obj.id

                    booking.save()

                    host = booking.host
                    host.total_sell_amount = (
                        host.total_sell_amount + booking.paid_amount
                    )
                    host.save()
                    online_payment.save()

                send_notification(notification_data=notification_data)

                send_sms(
                    username=booking.guest.phone_number,
                    message=(
                                f"🎉 Booking Confirmed! '{booking.listing.title}' "
                                f"from {booking.check_in} to {booking.check_out}, "
                                f"{booking.night_count} nights. Invoice: {booking.invoice_no}."
                            ),
                )
                send_sms(
                    username=host.phone_number,
                    message=(
                                f"📢 New Booking! '{booking.listing.title}' "
                                f"from {booking.check_in} to {booking.check_out}, "
                                f"{booking.guest_count} guests. Invoice: {booking.invoice_no}."
                            ),
                )
                booking_confirmed_process.delay(booking_id=booking.id)

            return Response(
                {"message": "Payment request received"}, status=status.HTTP_201_CREATED
            )
        except OnlinePayment.DoesNotExist:
            return Response(
                {"message": "Invalid payment attempted", "data": request.data},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentRedirectAPIView(views.APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        return HttpResponsePermanentRedirect(
            f"{settings.FRONTEND_BASE_URL}/checkout/{kwargs.get('status')}/{kwargs.get('invoice_no')}"
        )


class DevelopmentPaymentBypassView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """
        Bypass payment system for development environment.
        Mark a booking as paid without going through payment gateway.

        Required parameters:
        - booking_invoice_no: The invoice number of the booking to mark as paid
        """
        # Check if we're in development environment
        if not settings.DEBUG:
            return Response(
                {"message": "This endpoint is only available in development environment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get booking invoice number from request
        booking_invoice_no = request.data.get("booking_invoice_no")
        if not booking_invoice_no:
            return Response(
                {"message": "booking_invoice_no is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get booking object
        booking = get_object_or_404(Booking, invoice_no=booking_invoice_no)

        # Check if payment is already done
        if booking.guest_payment_status == PaymentStatusOption.PAID:
            return Response(
                {"message": "Payment already done for this booking"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate transaction and reservation codes
        transaction_number = identifier_builder(
            table_name="payments_onlinepayment", prefix="DEV_PGDBK"
        )
        reservation_code = identifier_builder(
            table_name="bookings_booking", prefix="DEV_RES"
        )

        # Create payment record
        payment_data = {
            "payment_method": OnlinePaymentMethodOption.SSL_COMMERZ,
            "user": booking.guest,  # Pass the user object instead of just the ID
            "amount": booking.total_price,
            "status": OnlinePaymentStatusOption.COMPLETED,
            "transaction_number": transaction_number,
            "booking": booking,  # Pass the booking object instead of just the ID
            "meta": {
                "dev_payment_bypass": True,
                "bypassed_by": request.user.username,
                "bypassed_at": str(timezone.now()),
            },
            "has_hit_ipn": True,
        }

        try:
            with transaction.atomic():
                # Create payment record
                # Fix: Pass the booking object instead of just the ID
                payment_data["booking"] = booking
                online_payment = OnlinePayment.objects.create(**payment_data)

                # Update booking details
                booking.pgw_transaction_number = transaction_number
                booking.reservation_code = reservation_code
                booking.guest_payment_status = PaymentStatusOption.PAID
                booking.status = BookingStatusOption.CONFIRMED
                booking.paid_amount = online_payment.amount

                # Prepare booking data for calendar
                booking_data = {
                    "user": UserSerializer(
                        booking.guest,
                        fields=[
                            "id",
                            "full_name",
                            "image",
                            "u_type",
                            "phone_number",
                            "email",
                        ],
                    ).data,
                    "booking": BookingSerializer(
                        booking, fields=["id", "invoice_no", "reservation_code"]
                    ).data,
                }

                # Update listing calendar
                for entry in booking.calendar_info:
                    start_date = entry["start_date"]
                    end_date = entry["end_date"]

                    defaults = {
                        "base_price": entry["base_price"],
                        "custom_price": entry["price"],
                        "is_blocked": entry["is_blocked"],
                        "is_booked": entry["is_booked"],
                        "booking_data": booking_data,
                    }

                    obj, created = ListingCalendar.objects.update_or_create(
                        listing_id=entry["listing_id"],
                        start_date=start_date,
                        end_date=end_date,
                        defaults=defaults,
                    )

                    entry["id"] = obj.id

                # Update listing booking count
                Listing.objects.filter(id=booking.listing_id).update(
                    total_booking_count=F("total_booking_count") + 1
                )

                # Update host stats
                host = booking.host
                host.total_sell_amount = host.total_sell_amount + booking.paid_amount
                host.save()

                # Save booking changes
                booking.save()

                # Trigger booking confirmation process
                booking_confirmed_process.delay(booking_id=booking.id)

                # Send SMS notifications (optional for dev environment)
                # if settings.:
                #     send_sms(
                #         username=booking.guest.phone_number,
                #         message="Congratulations! You've successfully completed your booking",
                #     )
                #     send_sms(
                #         username=host.phone_number,
                #         message="Congratulations! A guest booked your property just now",
                #     )

                return Response(
                    {
                        "message": "Payment bypassed successfully in development environment",
                        "booking_id": booking.id,
                        "invoice_no": booking.invoice_no,
                        "reservation_code": booking.reservation_code,
                        "transaction_number": transaction_number,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            return Response(
                {"message": f"Error bypassing payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
