import os
from datetime import datetime, timedelta
from decimal import InvalidOperation, Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from django.db.models import F
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListCreateAPIView, views, ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tasks.users import send_sms
from base.helpers.decorators import exception_handler
from base.permissions import (
    HostUserHasObjectAccess,
    IsGuestUser, IsStaff, IsSuperUser,
)
from base.type_choices import (
    BookingStatusOption,
    NotificationEventTypeOption,
    NotificationTypeOption,
    ServiceChargeTypeOption,
    UserTypeOption,
)
from base.mongo.connection import connect_mongo
from bookings.coupon_service import validate_and_get_coupon_discount_info
from bookings.filters import UserBookingFilter
from bookings.models import Booking, ListingBookingReview
from bookings.serializers import BookingReviewSerializer, BookingSerializer, CouponCheckResponseSerializer
from bookings.tasks.booking_cancel import booking_cancelled_process
from bookings.views.service import BookingReviewProcess, GuestBookingProcess
from configurations.models import ServiceCharge
from listings.models import Listing, ListingCalendar
from notifications.models import Notification
from notifications.utils import create_notification, send_notification

User = get_user_model()

from coupons.serializers import CouponValidateSerializer # Request serializer
class GuestBookingListCreateAPIView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsGuestUser)
    serializer_class = BookingSerializer
    filterset_class = UserBookingFilter
    http_method_names = ["get", "post"]
    swagger_tags = ["Gust Bookings"]

    def get_queryset(self):
        return (
            Booking.objects.exclude(status=BookingStatusOption.INITIATED)
            .filter(
                guest_id=self.request.user.id,
            )
            .select_related("listing", "host")
            .order_by("-created_at")
        )

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["rw_method_fields"] = ["listing"]
        kwargs["r_method_fields"] = ["host"]
        return self.serializer_class(*args, **kwargs)

    @method_decorator(exception_handler)
    def create(self, request, *args, **kwargs):
        print(request.user)
        processed_data = GuestBookingProcess()(request.data, request.user)

        if processed_data["status"] != 200:
            return Response(
                {"message": processed_data["message"]}, status=processed_data["status"]
            )

        extra_fields = ['original_price_before_discount', 'total_discount_amount',
                        'accommodation_charge', 'subtotal_before_generic_coupon',
                        'length_of_stay_discount_percent', 'length_of_stay_discount_amount']

        extra_data = {field: processed_data["data"].get(field) for field in extra_fields if
                      field in processed_data["data"]}

        # Create serializer with extra context
        context = self.get_serializer_context()
        context['extra_data'] = extra_data

        serializer = self.serializer_class(data=processed_data["data"], context=context)
        if serializer.is_valid(raise_exception=True):
            serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)




class GuestPendingReviewsAPIView(ListAPIView):
    """
    Retrieves a list of bookings for the authenticated guest that have been
    completed but for which the guest has not yet submitted a review.
    A booking is considered eligible for review if its check-out date has passed.
    """
    permission_classes = (IsAuthenticated, IsGuestUser)
    serializer_class = BookingSerializer
    swagger_tags = ["Gust Bookings"]
    http_method_names = ["get"]



    def get_queryset(self):
        """
        Returns bookings where:
        - The booking belongs to the current guest.
        - The booking status is 'CONFIRMED'.
        - The guest has not yet submitted a review ('guest_review_done' is False).
        - The check-out date is in the past, meaning the stay is complete.
        """
        print(" reviews --- ")
        today = datetime.now().date()
        return (
            Booking.objects.filter(
                guest_id=self.request.user.id,
                status=BookingStatusOption.CONFIRMED,
                guest_review_done=False,
                check_out__lt=today,
            )
            .select_related("listing")
            .order_by("-check_out")
        )

    def get_serializer(self, *args, **kwargs):
        """
        Customize the serializer to return only the fields necessary for a user
        to identify the booking they need to review.
        """
        kwargs["context"] = self.get_serializer_context()
        kwargs["fields"] = [
            "invoice_no",
            "listing",
            "check_in",
            "check_out",
        ]
        kwargs["r_method_fields"] = ["listing"]
        return self.serializer_class(*args, **kwargs)

class ValidateCouponAPIView(APIView):
    permission_classes = [IsAuthenticated]  # User must be logged in to check a coupon, typically
    swagger_tags = ["Coupons", "Bookings"]  # Add to relevant swagger tags

    @swagger_auto_schema(
        request_body=CouponValidateSerializer,
        operation_summary="Validate a coupon code",
        operation_description="Checks if a given coupon code is valid for an optional order total and returns discount information.",
        responses={
            200: CouponCheckResponseSerializer(),
            400: openapi.Response("Bad Request (e.g., invalid input format)"),
            # 404: openapi.Response("Coupon not found - handled by the service's message")
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = CouponValidateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        coupon_code_input = validated_data.get('code')
        order_total_input = validated_data.get('order_total')  # This is optional in serializer

        # The service expects a Decimal order_total. Default to 0 if not provided for validation context.
        # Some coupons might not require an order_total for basic validity check (e.g. existence, expiry).
        order_total_decimal = order_total_input if order_total_input is not None else Decimal('0.00')

        # Ensure order_total_decimal is indeed a Decimal for the service
        if not isinstance(order_total_decimal, Decimal):
            try:
                order_total_decimal = Decimal(str(order_total_decimal))
            except InvalidOperation:
                return Response({"order_total": ["Invalid amount for order total."]},
                                status=status.HTTP_400_BAD_REQUEST)

        coupon_info = validate_and_get_coupon_discount_info(
            coupon_code_input=coupon_code_input,
            order_total=order_total_decimal,
            booking_user=request.user  # Pass the authenticated user
        )


        print(" ---------- ", coupon_info, " ------------ ")

        response_data = {
            "is_valid": coupon_info['is_valid'],
            "message": coupon_info['message'],
            "coupon_code": (coupon_info.get('coupon_code_matched', coupon_code_input) if coupon_info.get('is_valid') else coupon_code_input),
            "coupon_type": coupon_info['coupon_type'] if coupon_info['is_valid'] else None,
            "discount_amount": coupon_info['discount_amount'] if coupon_info['is_valid'] else None,
            "original_price_for_discount_calc": order_total_input if order_total_input is not None else None,
            "price_after_discount": coupon_info['final_price'] if coupon_info['is_valid'] else None,
            "discount_display": None
        }

        if coupon_info['is_valid'] and coupon_info['coupon_object']:
            coupon_obj = coupon_info['coupon_object']
            if coupon_info['coupon_type'] == 'admin':
                # coupon_obj is an AdminConfiguredCoupon instance
                if coupon_obj.discount_type == 'PERCENT':
                    response_data['discount_display'] = f"{coupon_obj.discount_value}%"
                elif coupon_obj.discount_type == 'FIXED':
                    response_data['discount_display'] = f"{coupon_obj.discount_value} Taka"  # Or your currency
            elif coupon_info['coupon_type'] == 'referral':
                # coupon_obj is a ReferralGeneratedCoupon instance
                response_data['discount_display'] = f"{coupon_obj.amount} Taka"  # Or your currency

        response_serializer = CouponCheckResponseSerializer(data=response_data)
        if response_serializer.is_valid():  # Should be valid as we constructed it
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            # This case is unlikely if response_data is constructed correctly
            # but good to have for debugging serializer issues.
            print("Error in CouponCheckResponseSerializer:", response_serializer.errors)
            return Response(response_data, status=status.HTTP_200_OK)
class GuestBookingRetrieveAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsGuestUser)
    swagger_tags = ["Gust Bookings"]

    def _get_extra_booking_data(self, booking):
        """
        Calculate the missing fields that aren't stored in the model.
        This mimics the calculation logic from GuestBookingProcess.
        """
        extra_data = {}

        # Get the original prices from price_info
        original_total = 0.0
        los_discount_total = 0.0

        if hasattr(booking, 'price_info') and booking.price_info:
            for date_str, price_data in booking.price_info.items():
                original_calendar_price = price_data.get('original_calendar_price', price_data.get('price', 0))
                current_price = price_data.get('price', 0)

                original_total += float(original_calendar_price)
                los_discount_total += float(original_calendar_price) - float(current_price)

        # Calculate fields
        extra_data['original_price_before_discount'] = original_total
        extra_data['accommodation_charge'] = float(booking.price) if booking.price else 0.0

        # Calculate total discount (LoS + coupon)
        coupon_discount = float(booking.discount_amount_applied) if booking.discount_amount_applied else 0.0
        extra_data['total_discount_amount'] = los_discount_total + coupon_discount

        # Calculate subtotal before coupon (accommodation + service charges)
        guest_service_charge = float(booking.guest_service_charge) if booking.guest_service_charge else 0.0
        extra_data['subtotal_before_generic_coupon'] = extra_data['accommodation_charge'] + guest_service_charge

        # LoS discount details
        extra_data['length_of_stay_discount_amount'] = los_discount_total

        # Calculate LoS discount percentage (approximate)
        if original_total > 0:
            extra_data['length_of_stay_discount_percent'] = (los_discount_total / original_total) * 100
        else:
            extra_data['length_of_stay_discount_percent'] = 0.0

        return extra_data

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        booking = Booking.objects.select_related("listing", "host").get(
            invoice_no=kwargs.get("invoice_no"),
            guest_id=request.user.id,
            # status=BookingStatusOption.CONFIRMED,
        )

        # Calculate extra data for the missing fields
        extra_data = self._get_extra_booking_data(booking)

        result = {}

        # Create serializer context with extra data
        context = {
            'request': request,
            'extra_data': extra_data
        }

        data = BookingSerializer(
            booking,
            many=False,
            r_method_fields=["listing", "host"],
            context=context,
            fields=[
                "id",
                "invoice_no",
                "reservation_code",
                "check_in",
                "check_out",
                "night_count",
                "guest_service_charge",
                "price",
                "total_price",
                "paid_amount",
                "price_info",
                "guest_review_done",
                "status",
                "guest_count",
                "adult_count",
                "children_count",
                "infant_count",
                'applied_coupon_code',
                'applied_coupon_type',
                'discount_amount_applied',
                'price_after_discount',
                'applied_admin_coupon',
                'applied_referral_coupon',
                # Add the missing fields
                'original_price_before_discount',
                'total_discount_amount',
                'accommodation_charge',
                'subtotal_before_generic_coupon',
                'length_of_stay_discount_percent',
                'length_of_stay_discount_amount',
            ],
        ).data

        result["booking_data"] = data
        result["review_data"] = None

        if booking.guest_review_done and request.GET.get("is_review"):
            guest_booking_review = ListingBookingReview.objects.filter(
                booking_id=booking.id, review_by_id=request.user.id
            ).first()
            if guest_booking_review:
                result["review_data"] = {
                    "review": guest_booking_review.review,
                    "rating": guest_booking_review.rating,
                    "image": request.user.image,
                    "full_name": request.user.get_full_name(),
                    "created_at": str(guest_booking_review.created_at),
                }

        with connect_mongo() as collections:
            guest = booking.guest
            listing = booking.listing
            main_host = listing.host

            # 1. Gather all hosts (main + co-hosts) for the listing
            active_co_hosts = User.objects.filter(cohosting_gigs__listing=listing, cohosting_gigs__is_active=True)
            all_recipients = list(set([main_host] + list(active_co_hosts)))

            # 2. Create the canonical room name, same as in your other tasks/views
            host_usernames = [user.username for user in all_recipients]
            sorted_host_usernames = sorted(host_usernames)
            room_name = f"{guest.username}:{':'.join(sorted_host_usernames)}"

            # 3. Find the chat room using the correct canonical name
            chat_room = collections["ChatRoom"].find_one({"name": room_name})

            # 4. Add the chat room ID to the result if found
            result["chat_room"] = str(chat_room.get("_id")) if chat_room else None

        return Response(result, status=status.HTTP_200_OK)


class GuestBookingReviewAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsGuestUser)
    swagger_tags = ["Gust Bookings"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):
        rating = request.data["rating"]
        review = request.data["review"]
        booking_review_process = BookingReviewProcess()
        booking_review_data = booking_review_process.validate_booking_review_data(
            data=request.data.copy(),
            invoice_no=kwargs.get("invoice_no"),
            user=request.user,
        )

        if booking_review_data.get("status") != 200:
            return Response(
                {"message": booking_review_data.get("message")},
                status=booking_review_data.get("status"),
            )

        booking_obj = booking_review_data.get("booking_obj")

        event_type = NotificationEventTypeOption.REVIEW
        host_notification = create_notification(
            event_type=event_type,
            data={
                # "identifier": str(booking_review.id),
                "message": f"Surprise ! You’ve got a new review from {booking_obj.host.get_full_name()}",
                "link": f"/profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking_obj.host.id,
        )
        guest_notification = create_notification(
            event_type=event_type,
            data={
                # "identifier": str(booking_review.id),
                "message": f"Congratulation! Your review has been placed successfully.",
                "link": f"/profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=request.user.id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                # "identifier": str(booking_review.id),
                "message": f"A new review has been placed from {request.user.get_full_name()}",
                "link": f"/reviews",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )

        notification_data = [
            host_notification,
            guest_notification,
            admin_notification,
        ]

        with transaction.atomic():
            booking_review = ListingBookingReview.objects.create(
                **booking_review_data.get("review_data")
            )
            booking_review_process.update_ratings(booking_review.listing, rating)
            booking_review_process.update_ratings(booking_obj.host, rating)

            for i in range(0, 3):
                notification_data[i]["data"]["identifier"] = str(booking_review.id)

            if request.user.u_type == UserTypeOption.GUEST:
                booking_obj.guest_review_done = True
            else:
                booking_obj.host_review_done = True
            booking_obj.save()

            Notification.objects.bulk_create(
                [Notification(**item) for item in notification_data]
            )

        send_notification(notification_data=notification_data)

        return Response({"message": "Review created"}, status=status.HTTP_201_CREATED)


class GuestBookingReviewRetrieveAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsGuestUser)
    swagger_tags = ["Gust Bookings"]

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        booking_review = ListingBookingReview.objects.get(
            id=kwargs.get("pk"), review_by_id=request.user.id
        )

        if not booking_review.is_host_review or not booking_review.is_guest_review:
            return Response(
                {"message": "You can not see the review yet"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = BookingReviewSerializer(booking_review, many=False)
        return Response(data, status=status.HTTP_200_OK)


class GuestBookingCancelAPIView(views.APIView):
    permission_classes = (IsAuthenticated,IsGuestUser)
    swagger_tags = ["Gust Bookings"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):

        invoice_no = kwargs.get("invoice_no")
        cancellation_reason = request.data["cancellation_reason"]

        current_date = datetime.now().date()
        booking = Booking.objects.get(
            invoice_no=invoice_no,
            guest_id=request.user.id,
            status=BookingStatusOption.CONFIRMED,
        )

        if booking.check_in < current_date:
            return Response(
                {"message": "Booking can only be cancelled before check in date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listing = booking.listing

        listing_calendar_ids = [
            d.get("id") for d in booking.calendar_info if d.get("id")
        ]

        cancellation_policy = listing.cancellation_policy
        cancellation_deadline = cancellation_policy.get("cancellation_deadline")
        refund_percentage = cancellation_policy.get("refund_percentage")
        days_before_check_in = booking.check_in - timedelta(days=cancellation_deadline)

        if refund_percentage != 0 and current_date <= days_before_check_in:
            host_service_charge = ServiceCharge.objects.filter(
                sc_type=ServiceChargeTypeOption.HOST_CHARGE
            ).first()
            host_service_charge_value = (
                host_service_charge.value / 100
                if host_service_charge.calculation_type == "percentage"
                else host_service_charge.value
            )

            refund_amount = (refund_percentage / 100) * booking.price
            host_service_charge_amount = round(
                host_service_charge_value * refund_amount
            )

            host_pay_out = refund_amount - host_service_charge_amount
            booking.host_pay_out = host_pay_out
            booking.host_service_charge = host_service_charge_amount
            booking.refund_amount = refund_amount
            booking.is_refunded = True

        booking.status = BookingStatusOption.CANCELLED
        booking.cancellation_reason = cancellation_reason

        with transaction.atomic():
            booking.save()
            if len(listing_calendar_ids) > 0:
                ListingCalendar.objects.filter(id__in=listing_calendar_ids).delete()

        send_sms(
            username=booking.guest.phone_number,
            message="You’ve successfully cancelled your booking",
        )
        send_sms(
            username=booking.host.phone_number,
            message="A guest cancelled booking just now",
        )

        booking_cancelled_process.delay(booking_id=booking.id)  # delay

        return Response(
            {"message": "Booking cancellation done"}, status=status.HTTP_200_OK
        )

class GuestBookingCancelAdminAPIView(views.APIView):
    permission_classes = (IsAuthenticated,)
    swagger_tags = ["Gust Bookings"]

    @method_decorator(exception_handler)
    def post(self, request, *args, **kwargs):

        invoice_no = kwargs.get("invoice_no")
        cancellation_reason = request.data["cancellation_reason"]

        current_date = datetime.now().date()
        booking = Booking.objects.get(
            invoice_no=invoice_no,
            guest_id=kwargs.get("guest_id"),
            status=BookingStatusOption.CONFIRMED,
        )

        if booking.check_in < current_date:
            return Response(
                {"message": "Booking can only be cancelled before check in date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listing = booking.listing

        listing_calendar_ids = [
            d.get("id") for d in booking.calendar_info if d.get("id")
        ]

        cancellation_policy = listing.cancellation_policy
        cancellation_deadline = cancellation_policy.get("cancellation_deadline")
        refund_percentage = cancellation_policy.get("refund_percentage")
        days_before_check_in = booking.check_in - timedelta(days=cancellation_deadline)

        if refund_percentage != 0 and current_date <= days_before_check_in:
            host_service_charge = ServiceCharge.objects.filter(
                sc_type=ServiceChargeTypeOption.HOST_CHARGE
            ).first()
            host_service_charge_value = (
                host_service_charge.value / 100
                if host_service_charge.calculation_type == "percentage"
                else host_service_charge.value
            )

            refund_amount = (refund_percentage / 100) * booking.price
            host_service_charge_amount = round(
                host_service_charge_value * refund_amount
            )

            host_pay_out = refund_amount - host_service_charge_amount
            booking.host_pay_out = host_pay_out
            booking.host_service_charge = host_service_charge_amount
            booking.refund_amount = refund_amount
            booking.is_refunded = True

        booking.status = BookingStatusOption.CANCELLED
        booking.cancellation_reason = cancellation_reason

        with transaction.atomic():
            booking.save()
            if len(listing_calendar_ids) > 0:
                ListingCalendar.objects.filter(id__in=listing_calendar_ids).delete()

        send_sms(
            username=booking.guest.phone_number,
            message="You’ve successfully cancelled your booking",
        )
        send_sms(
            username=booking.host.phone_number,
            message="A guest cancelled booking just now",
        )

        booking_cancelled_process.delay(booking_id=booking.id)  # delay

        return Response(
            {"message": "Booking cancellation done"}, status=status.HTTP_200_OK
        )


class DownloadInvoiceAPIView(APIView):
    permission_classes = [IsAuthenticated]
    swagger_tags = ["Bookings", "Invoices"]

    def get(self, request, invoice_no, *args, **kwargs):
        try:
            booking = Booking.objects.get(invoice_no=invoice_no)
            if not (request.user == booking.guest or request.user == booking.host or request.user.is_staff):
                return Response({"message": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

            if booking.invoice_pdf and booking.invoice_pdf.name:

                response = HttpResponse(booking.invoice_pdf, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(booking.invoice_pdf.name)}"'

                return response
            else:
                return Response({"message": "Invoice not yet generated or available."}, status=status.HTTP_404_NOT_FOUND)
        except Booking.DoesNotExist:
            return Response({"message": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error serving invoice {invoice_no}: {e}")
            return Response({"message": "Error serving invoice."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
