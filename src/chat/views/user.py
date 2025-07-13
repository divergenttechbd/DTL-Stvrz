from datetime import datetime, date
from bson import DBRef
from django.conf import settings
from base.cache.redis_cache import get_cache
from rest_framework.generics import views
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework import status
from accounts.tasks.users import send_sms
from base.helpers.utils import format_date
from base.mongo.connection import connect_mongo

from base.type_choices import NotificationEventTypeOption, NotificationTypeOption
from listings.models import Listing
from listings.views.service import ListingCalendarDataProcess, ListingCheckoutCalculate
from notifications.models import FCMToken, Notification
from notifications.tasks.notification import send_fcm_notification
from notifications.utils import create_notification, send_notification

User = get_user_model()


class UserChatApiView(views.APIView):
    permission_classes = (IsAuthenticated,)
    swagger_tags = ["User Chat"]

    def post(self, request, *args, **kwargs):
        print(request)
        current_date = date.today()
        listing_id = request.data["listing"]
        to_user_id = request.data["to_user"]
        booking_data = request.data["booking_data"]
        message = request.data["message"]

        listing = Listing.objects.get(id=listing_id)

        from_date = datetime.strptime(booking_data["check_in"], "%Y-%m-%d").date()
        to_date = datetime.strptime(booking_data["check_out"], "%Y-%m-%d").date()

        if (
            from_date < current_date
            or to_date < current_date
            or not to_date > from_date
        ):
            return Response(
                {"message": "Invalid date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_filter = {
            "from_date": from_date,
            "to_date": to_date,
        }
        calendar_data = ListingCalendarDataProcess()(
            date_filter,
            listing_id,
        )

        calendar_data.popitem()

        checkout_data = ListingCheckoutCalculate()(
            booking_date_info=calendar_data.copy(),
            date_range=date_filter,
            instance=listing,
        )
        if checkout_data["status"] != 200:
            return Response(
                {"message": checkout_data["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checkout_data = checkout_data["data"]
        to_user = User.objects.get(id=to_user_id)
        if to_user.u_type != "host":
            return Response(
                {"message": "invalid user"}, status=status.HTTP_400_BAD_REQUEST
            )

        with connect_mongo() as collections:
            room_name = f"{request.user.username}:{to_user.username}"
            document = collections["ChatRoom"].find_one({"name": room_name}) or None

            mongo_from_user_id = collections["User"].find_one(
                {"username": request.user.username}
            )
            mongo_to_user_id = collections["User"].find_one(
                {"username": to_user.username}
            )

            if document:
                room_id = document["_id"]
            else:
                created_room = collections["ChatRoom"].insert_one(
                    {
                        "name": room_name,
                        "from_user": DBRef("User", mongo_from_user_id["_id"]),
                        "to_user": DBRef("User", mongo_to_user_id["_id"]),
                        "created_at": datetime.now(),
                        "status": "open",
                    }
                )
                room_id = created_room.inserted_id

            collections["Message"].insert_one(
                {
                    "chat_room": DBRef("ChatRoom", room_id),
                    "user": DBRef("User", mongo_from_user_id["_id"]),
                    "m_type": "system",
                    "is_read": False,
                    "content": f"Inquiry sent · {booking_data['total_guest_count']} guest, {format_date(booking_data['check_in'])} - {format_date(booking_data['check_out'])}",
                    "meta": {
                        "listing": str(listing.unique_id),
                        "booking": {
                            "booking_date": booking_data,
                            "checkout_data": checkout_data,
                        },
                        "user": request.user.id,
                    },
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )
            collections["Message"].insert_one(
                {
                    "chat_room": DBRef("ChatRoom", room_id),
                    "user": DBRef("User", mongo_from_user_id["_id"]),
                    "content": message,
                    "meta": None,
                    "m_type": "normal",
                    "is_read": False,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            )

            collections["ChatRoom"].update_one(
                {"_id": room_id},
                {
                    "$set": {
                        "latest_message": {
                            "content": message,
                            "created_at": datetime.now(),
                            "user": {
                                "username": mongo_from_user_id["username"],
                                "full_name": mongo_from_user_id["full_name"],
                                "image": mongo_from_user_id["image"],
                                "user_id": mongo_from_user_id["user_id"],
                            },
                            "m_type": "normal",
                        },
                        "status": "inquiry",
                        "booking_data": booking_data,
                        "listing": {"name": listing.title, "id": listing.id},
                        "updated_at": datetime.now(),
                    }
                },
            )

        event_type = NotificationEventTypeOption.BOOKING_INQUIRY
        host_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(listing.unique_id),
                "message": "Hello ! You’ve received a new inquiry for your property",
                "link": f"/host-dashboard/inbox?conversation_id={room_id}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=to_user.id,
        )

        guest_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(listing.unique_id),
                "message": f"Thanks ! Your query is successfully sent to the {to_user.get_full_name()}",
                "link": f"/messages?conversation_id={room_id}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=request.user.id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(listing.unique_id),
                "message": f"A new inquiry as been initiated between {to_user.get_full_name()} and {request.user.get_full_name()}",
                "link": f"/chat?id={room_id}",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data = [host_notification, guest_notification, admin_notification]

        Notification.objects.bulk_create(
            [Notification(**item) for item in notification_data]
        )

        send_sms(
            username=to_user.phone_number,
            message=f"You've got a new inquiry from {request.user.get_full_name()}",
        )
        send_notification(notification_data=notification_data)

        host_device_token = FCMToken.objects.filter(user_id=to_user.id).first()
        print(
            get_cache(key=f"user_mobile_logged_in_{to_user.username}"),
            "----------------------------",
        )
        if host_device_token:
            title = "Inquiry Message"
            body = f"You've got a new inquiry from {request.user.get_full_name()}"
            data = {
                "url": f"/host-dashboard/inbox?conversation_id={room_id}",
                "key2": "value2",
            }
            send_fcm_notification.delay(host_device_token.token, title, body, data)

        return Response(
            {"message": "message sent", "data": {"chat_room_id": str(room_id)}},
            status=status.HTTP_200_OK,
        )
