from datetime import date, timedelta
import json
from decimal import Decimal

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

from accounts.tasks.users import send_sms
from base.mongo.connection import connect_mongo
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
from listings.views.service import ListingCalendarDataProcess
from notifications.models import Notification
from notifications.utils import create_notification, send_notification
from bson import DBRef
from datetime import datetime


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
        print(qs, " -------")
        return qs.select_related("listing", "guest").order_by("-created_at")


class HostReservationListAPIViewCONF(ListAPIView):
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
        query_param = self.request.GET.get("status")
        qs = BookingDataFilterProcess()(
            query_param=query_param, current_user=self.request.user
        )
        print(qs, " -------")
        return qs.select_related("listing", "guest").order_by("-created_at")


def send_booking_status_chat_message(booking: Booking, message_content: str, status: str, ins_status:str):
    """
    Sends a system message with a detailed meta payload regarding a booking status change.
    """
    try:
        guest_user = booking.guest
        listing = booking.listing

        # --- 1. Reconstruct the detailed meta payload ---

        def convert_decimals_to_floats(data):
            # Helper to ensure data is MongoDB compatible
            if isinstance(data, dict):
                return {k: convert_decimals_to_floats(v) for k, v in data.items()}
            if isinstance(data, list):
                return [convert_decimals_to_floats(i) for i in data]
            if isinstance(data, Decimal):
                return float(data)
            return data

        # Rebuild the 'booking_date' part
        booking_date_meta = {
            "check_in": booking.check_in.strftime("%Y-%m-%d"),
            "check_out": booking.check_out.strftime("%Y-%m-%d"),
            "adult": booking.adult_count,
            "children": booking.children_count,
            "infant": booking.infant_count,
            "pets": 0,
            "total_guest_count": booking.guest_count
        }

        # Rebuild the 'checkout_data' part from saved Booking fields
        # Note: 'total_price' here represents the subtotal before gateway fees, matching the original context.
        subtotal = booking.total_price
        checkout_data_meta = {
            "nights": booking.night_count,
            "booking_price": booking.price,
            "guest_service_charge": booking.guest_service_charge,
            "total_price": subtotal,
            "host_service_charge": booking.host_service_charge,
            "host_pay_out": booking.host_pay_out,
            "price_info": booking.price_info,
            "total_profit": booking.total_profit,
        }

        # Combine into the final meta object
        meta_payload = {
            "instant_book":True,
            "instant_book_status": ins_status,
            "listing": str(listing.unique_id),
            "booking": {
                "booking_date": booking_date_meta,
                "checkout_data": convert_decimals_to_floats(checkout_data_meta)
            },
            "user": guest_user.id
        }

        # --- 2. Standard Chat Room and Message Sending Logic ---

        primary_host = listing.host
        active_co_hosts = User.objects.filter(cohosting_gigs__listing=listing, cohosting_gigs__is_active=True)
        all_hosts = list(set([primary_host] + list(active_co_hosts)))
        host_usernames = sorted([user.username for user in all_hosts])
        room_name = f"{guest_user.username}:{':'.join(host_usernames)}"

        with connect_mongo() as collections:
            chat_room_doc = collections["ChatRoom"].find_one({"name": room_name})
            if not chat_room_doc:
                print(f"Chat Error: Chat room '{room_name}' not found. Cannot send status update.")
                return

            room_id = chat_room_doc["_id"]
            mongo_guest_user_doc = collections["User"].find_one({"username": guest_user.username})

            if not mongo_guest_user_doc:
                print(f"Chat Error: Guest user '{guest_user.username}' not found in chat service.")
                return

            collections["Message"].insert_one({
                "chat_room": DBRef("ChatRoom", room_id),
                "user": DBRef("User", mongo_guest_user_doc["_id"]),
                "m_type": "system",
                "is_read": False,
                "content": message_content,
                "meta": meta_payload,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            })

            collections["ChatRoom"].update_one(
                {"_id": room_id},
                {"$set": {
                    "latest_message": {"content": message_content, "created_at": datetime.now(),
                                       "user": {
                                           "username": mongo_guest_user_doc["username"],
                                           "full_name": mongo_guest_user_doc["full_name"],
                                           "image": mongo_guest_user_doc["image"],
                                           "user_id": mongo_guest_user_doc["user_id"]
                                       },
                                       "m_type": "system",
                                       "is_read": False},

                    "status": status,
                    "booking_data": booking_date_meta,
                    "updated_at": datetime.now(),
                }}
            )
            print(f"Successfully sent chat message with DETAILED meta to room_id: {room_id}")

    except Exception as e:
        print(f"CRITICAL: Failed to send booking status chat message. Invoice: {booking.invoice_no}. Error: {e}")

class HostAcceptBookingRequestAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)  # Assuming IsHostUser permission
    swagger_tags = ["Host Bookings"]

    @transaction.atomic  # Ensure all database operations are atomic for data integrity
    def post(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")
        try:

            booking_to_accept = Booking.objects.select_related('listing', 'guest').select_for_update().get(
                invoice_no=invoice_no,
                host=request.user,
                status=BookingStatusOption.PENDING_CONFIRMATION
            )
        except Booking.DoesNotExist:
            return Response({"message": "Pending booking request not found."}, status=status.HTTP_404_NOT_FOUND)

        today = date.today()
        if booking_to_accept.check_in < today:

            booking_to_accept.status = BookingStatusOption.DECLINED
            booking_to_accept.cancellation_reason = 'Declined by system: Request expired as check-in date has passed.'
            booking_to_accept.save()

            return Response(
                {"message": "Cannot accept a booking request for a past check-in date. The request has been declined."},
                status=status.HTTP_400_BAD_REQUEST
            )


        listing = booking_to_accept.listing

        # --- 1. FINAL AVAILABILITY CHECK ---
        # Check if another booking was confirmed (paid for) while this one was pending.
        calendar_check_end_date = booking_to_accept.check_out - timedelta(days=1)
        calendar_data_process = ListingCalendarDataProcess()
        availability_data = calendar_data_process(
            data={"from_date": booking_to_accept.check_in, "to_date": calendar_check_end_date},
            listing_id=listing.id
        )

        # Loop through the dates to see if any have become blocked or booked by someone else
        for date_str, data in availability_data.items():
            if data.get("is_blocked") or data.get("is_booked"):
                # A confirmed booking took the slot. This request must be declined.
                booking_to_accept.status = BookingStatusOption.DECLINED
                booking_to_accept.cancellation_reason = 'Declined by system: Dates became unavailable before host could accept.'
                booking_to_accept.save()

                # Notify the guest that their request was auto-declined
                # (This is important for user experience)
                guest_notification = create_notification(
                    event_type=NotificationEventTypeOption.BOOKING_REQUEST_DECLINED,
                    data={
                        "identifier": booking_to_accept.invoice_no,
                        "message": f"Unfortunately, the dates for your request for '{listing.title}' became unavailable before the host could accept.",
                        "link": f"/bookings/{booking_to_accept.invoice_no}",
                    },
                    n_type=NotificationTypeOption.USER_NOTIFICATION,
                    user_id=booking_to_accept.guest.id,
                )
                send_notification(notification_data=[guest_notification])

                return Response(
                    {
                        "message": f"Cannot accept. The date {date_str} is no longer available. The booking request has been automatically declined."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # --- 2. ACCEPT THE CURRENT BOOKING ---
        # This code only runs if the availability check passes.
        booking_to_accept.status = BookingStatusOption.ACCEPTED
        booking_to_accept.save()

        # --- 3. AUTO-DECLINE OTHER CONFLICTING PENDING BOOKINGS ---
        # Find all *other* pending requests for the same listing that overlap with the accepted dates.
        conflicting_pending_bookings = Booking.objects.filter(
            listing=listing,
            status=BookingStatusOption.PENDING_CONFIRMATION,
            check_in__lt=booking_to_accept.check_out,  # Starts before our booking ends
            check_out__gt=booking_to_accept.check_in  # Ends after our booking starts
        ).exclude(pk=booking_to_accept.pk)  # Exclude the one we just accepted

        declined_notifications = []
        for conflicting_booking in conflicting_pending_bookings:
            conflicting_booking.status = BookingStatusOption.DECLINED
            conflicting_booking.cancellation_reason = "Declined by system: Host accepted another booking for these dates."
            conflicting_booking.save()

            # Prepare notifications for the guests of the auto-declined bookings
            declined_notifications.append(create_notification(
                event_type=NotificationEventTypeOption.BOOKING_REQUEST_DECLINED,
                data={
                    "identifier": conflicting_booking.invoice_no,
                    "message": f"Unfortunately, your request for '{listing.title}' was declined as the host accepted another booking for the requested dates.",
                    "link": f"/bookings/{conflicting_booking.invoice_no}",
                },
                n_type=NotificationTypeOption.USER_NOTIFICATION,
                user_id=conflicting_booking.guest_id,
            ))
            if conflicting_booking.guest.phone_number:
                send_sms(
                    username=conflicting_booking.guest.phone_number,
                    message=f"Your request for '{listing.title}' was declined as the dates are no longer available."
                )
            send_booking_status_chat_message(
                booking=conflicting_booking,
                message_content=f"Unfortunately, your request for '{conflicting_booking.listing.title}' was automatically declined as the host accepted another booking for the requested dates.",
                status="inquiry",
                ins_status="decline"
            )

        # Send all "declined" notifications in one batch if any exist
        if declined_notifications:
            send_notification(notification_data=declined_notifications)

        # --- 4. NOTIFY THE ACCEPTED GUEST ---
        accepted_guest_notification = create_notification(
            event_type=NotificationEventTypeOption.BOOKING_REQUEST_ACCEPTED,
            data={
                "identifier": booking_to_accept.invoice_no,
                "message": f"Good news! Your request for '{booking_to_accept.listing.title}' has been accepted. Please complete your payment.",
                "link": f"/bookings/{booking_to_accept.invoice_no}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking_to_accept.guest.id,
        )
        send_notification(notification_data=[accepted_guest_notification])

        if booking_to_accept.guest.phone_number:
            send_sms(
                username=booking_to_accept.guest.phone_number,
                message=f"Your booking for '{booking_to_accept.listing.title}' was accepted! Please complete payment. Invoice: {booking_to_accept.invoice_no}"
            )

        send_booking_status_chat_message(
            booking=booking_to_accept,
            message_content=f"Your request for '{booking_to_accept.listing.title}' has been accepted. Please complete your payment to confirm the booking.",
            status="inquiry",
            ins_status="accepted"
        )

        return Response(
            {"message": "Booking request accepted. Conflicting pending requests have been declined."},
            status=status.HTTP_200_OK
        )


class HostDeclineBookingRequestAPIView(views.APIView):
    permission_classes = (IsAuthenticated, IsHostUser)
    swagger_tags = ["Host Bookings"]

    def post(self, request, *args, **kwargs):
        invoice_no = kwargs.get("invoice_no")
        reason = request.data.get("reason")
        if not reason:
            return Response({"message": "A reason is required to decline a booking."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = Booking.objects.get(
                invoice_no=invoice_no,
                host=request.user,
                status=BookingStatusOption.PENDING_CONFIRMATION
            )
        except Booking.DoesNotExist:
            return Response({"message": "Pending booking request not found."}, status=status.HTTP_404_NOT_FOUND)

        booking.status = BookingStatusOption.DECLINED
        booking.cancellation_reason = f"Declined by host: {reason}"
        booking.save()

        # TODO: Send notification to guest that their request was declined

        guest_notification = create_notification(
            event_type=NotificationEventTypeOption.BOOKING_REQUEST_DECLINED,  # Use a specific event type
            data={
                "identifier": booking.invoice_no,
                "message": f"Unfortunately, your booking request for '{booking.listing.title}' was declined by the host.",
                "link": f"/bookings/{booking.invoice_no}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking.guest.id,
        )

        notification_data = [guest_notification]
        send_notification(notification_data=notification_data)

        if booking.guest.phone_number:
            send_sms(
                username=booking.guest.phone_number,
                message=f"Your booking request for '{booking.listing.title}' was declined by the host."
            )

        send_booking_status_chat_message(
            booking=booking,
            message_content=f"Unfortunately, your request for '{booking.listing.title}' was declined by the host. Reason: {reason}",
            status="inquiry",
            ins_status="decline"
        )

        return Response({"message": "Booking request has been declined."}, status=status.HTTP_200_OK)

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
