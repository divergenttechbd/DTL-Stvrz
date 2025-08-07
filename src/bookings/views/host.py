from datetime import date, timedelta
import json
from django.conf import settings
from django.db.models import Q, F, Value
from django.db.models.functions import Concat
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView, views
from rest_framework.response import Response
from rest_framework import status
from base.permissions import HostUserHasObjectAccess, IsHostUser, IsPrimaryHostOrActiveCoHost

from base.helpers.classes import DTEncoder
from base.helpers.decorators import exception_handler
from base.permissions import HostUserHasObjectAccess, IsHostUser
from base.type_choices import (
    BookingStatusOption,
    NotificationEventTypeOption,
    NotificationTypeOption,
    UserTypeOption,
)
from bookings.filters import UserBookingFilter
from bookings.models import Booking, ListingBookingReview
from bookings.serializers import BookingReviewSerializer, BookingSerializer
from bookings.views.service import BookingDataFilterProcess, BookingReviewProcess
from listings.utils import get_user_with_profile
from notifications.models import Notification
from notifications.utils import create_notification, send_notification


User = get_user_model()


class HostReservationListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    serializer_class = BookingSerializer
    filterset_class = UserBookingFilter
    http_method_names = ["get"]
    swagger_tags = ["Host Bookings"]

    def get_serializer(self, *args, **kwargs):
        kwargs["context"] = self.get_serializer_context()
        kwargs["r_method_fields"] = ["listing", "guest"]
        return self.serializer_class(*args, **kwargs)

    def get_queryset(self):
        query_param = self.request.GET.get("event_type")
        qs = BookingDataFilterProcess()(
            query_param=query_param, current_user=self.request.user
        )
        return qs.select_related("listing", "guest").order_by("-created_at")


class HostReservationRetrieveAPIView(views.APIView):
    permission_classes = (IsAuthenticated,)
    swagger_tags = ["Host Bookings"]

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

    def get(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")
        booking_obj = Booking.objects.select_related(
            "guest__userprofile", "listing"
        ).get(invoice_no=invoice_no)

        self.check_object_permissions(request, booking_obj)

        # Calculate extra data for the missing fields
        extra_data = self._get_extra_booking_data(booking_obj)

        # Create serializer context with extra data
        context = {
            'request': request,
            'extra_data': extra_data
        }

        data = BookingSerializer(
            booking_obj,
            r_method_fields=["listing"],
            context=context
        ).data

        guest = booking_obj.guest

        data["guest"] = get_user_with_profile(guest)
        data["guest"]["is_host"] = User.objects.filter(
            username=f"{guest.phone_number}_host"
        ).exists()

        return Response(data, status=status.HTTP_200_OK)


class HostBookingReviewAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)
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
        guest_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": "",
                "message": f"Surprise ! You’ve got a new review from {booking_obj.host.get_full_name()}",
                "link": f"/profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking_review_data.get("review_data").get("review_for_id"),
        )

        host_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": "",
                "message": "Congratulation! Your review has been placed successfully",
                "link": f"/profile",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=request.user.id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": "",
                "message": f"A new review has been placed from {request.user.get_full_name()}",
                "link": f"/reviews",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )

        notification_data = [
            guest_notification,
            admin_notification,
            host_notification,
        ]

        with transaction.atomic():
            booking_review = ListingBookingReview.objects.create(
                **booking_review_data.get("review_data")
            )
            # booking_review_process.update_ratings(booking_review.listing, rating)
            booking_review_process.update_ratings(booking_obj.guest, rating)

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


class HostBookingReviewRetrieveAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    swagger_tags = ["Host Bookings"]

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

        data = BookingReviewSerializer(booking_review, many=False),
        return Response(data, status=status.HTTP_200_OK)


class HostReservationStatsApiView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    swagger_tags = ["Host Bookings"]

    @method_decorator(exception_handler)
    def get(self, request, *args, **kwargs):
        current_date = date.today()
        query_param = self.request.GET["event_type"]

        currently_hosting_count = Booking.objects.filter(
            Q(check_in__lte=current_date) & Q(check_out__gte=current_date),
            host_id=self.request.user.id,
            status=BookingStatusOption.CONFIRMED,
        ).count()

        upcoming_count = Booking.objects.filter(
            status=BookingStatusOption.CONFIRMED,
            check_in__gt=current_date,
            host_id=self.request.user.id,
        ).count()

        pending_review_count = Booking.objects.filter(
            status=BookingStatusOption.CONFIRMED,
            host_review_done=False,
            host_id=self.request.user.id,
            check_out__lt=current_date,
        ).count()

        checking_out_count = Booking.objects.filter(
            status=BookingStatusOption.CONFIRMED,
            host_id=self.request.user.id,
            check_out=current_date,
        ).count()

        arriving_soon_count = Booking.objects.filter(
            status=BookingStatusOption.CONFIRMED,
            host_id=self.request.user.id,
            check_in__gte=current_date + timedelta(days=1),
            check_in__lte=current_date + timedelta(days=7),
        ).count()

        stats = {
            "currently_hosting_count": currently_hosting_count,
            "upcoming_count": upcoming_count,
            "pending_review_count": pending_review_count,
            "checking_out_count": checking_out_count,
            "arriving_soon_count": arriving_soon_count,
        }

        qs = BookingDataFilterProcess()(
            query_param=query_param, current_user=request.user
        )

        data = list(
            qs.values(
                "id",
                "check_in",
                "check_out",
                "invoice_no",
                "chat_room_id",
                guest_image=F("guest__image"),
                guest_name=Concat("guest__first_name", Value(" "), "guest__last_name"),
                listing_title=F("listing__title"),
                listing_uid=F("listing__unique_id"),
            ).order_by("check_in")
        )

        return Response(
            {
                "stats": stats,
                "data": json.loads(json.dumps(data, cls=DTEncoder)),
            },
            status=status.HTTP_200_OK,
        )
