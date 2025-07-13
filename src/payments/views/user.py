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
        booking = get_object_or_404(Booking, invoice_no=request.data["booking"])

        print(booking)
        if booking.guest_payment_status == PaymentStatusOption.PAID:
            return Response(
                {"message": "Payment already done for the booking"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_number = identifier_builder(
            table_name="payments_onlinepayment", prefix="PGDBK"
        )
        reservation_code = identifier_builder(
            table_name="bookings_booking", prefix="RES"
        )
        request.data["payment_method"] = OnlinePaymentMethodOption.SSL_COMMERZ
        request.data["user"] = booking.guest_id
        request.data["amount"] = booking.total_price
        request.data["status"] = OnlinePaymentStatusOption.INITIATED
        request.data["transaction_number"] = transaction_number
        request.data["created_by"] = request.user.id
        request.data["booking"] = booking.id

        sslcommerz_data = {
            "ipn_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/sslcommerz/ipn/",
            "value_a": booking.id,
            "value_b": request.user.username,
            "num_of_item": 1,
            "product_name": "a,b",
            "product_category": "Deliverable",
            "product_profile": "physical-goods",
            "total_amount": booking.total_price,
            "tran_id": transaction_number,
            "success_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/success/{booking.invoice_no}/",
            "fail_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/fail/{booking.invoice_no}/",
            "cancel_url": f"{settings.BACKEND_BASE_URL}/payments/user/booking/cancel/{booking.invoice_no}/",
        }


        print(sslcommerz_data, " -----------sslz ")

        response = sslcommerz_payment_create(
            data=sslcommerz_data, customer=request.user
        )
        if not response:
            return Response(
                {"message": "Error response from SSlCommerz"},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )
        res_data = {
            "payment_gateway_url": response["GatewayPageURL"],
            "logo": response["storeLogo"],
            # "store_name": response["store_name"],
        }
        try:
            # super(UserSSLCommerzOrderPaymentView, self).create(request, *args, **kwargs)
            serializer = OnlinePaymentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            with transaction.atomic():
                serializer.save()
                booking.pgw_transaction_number = transaction_number
                booking.reservation_code = reservation_code
                booking.save()
            return Response(res_data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {"message": "Error initializing SSLCommerz payment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
                            "message": "Congratulations! A guest booked your property just now.",
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
                    message="Congratulations ! You’ve successfully completed your booking",
                )
                send_sms(
                    username=host.phone_number,
                    message="Congratulations ! A guest booked your property just now",
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
