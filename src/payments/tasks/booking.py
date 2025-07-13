from datetime import datetime
from django.conf import settings
from bson import DBRef
from base.cache.redis_cache import get_cache
from celery import shared_task
from celery.utils.log import get_task_logger
from base.helpers.utils import format_date
from base.mongo.connection import connect_mongo

from base.type_choices import NotificationEventTypeOption, NotificationTypeOption
from bookings.models import Booking
from notifications.models import FCMToken, Notification
from notifications.tasks.notification import send_fcm_notification_without_task
from notifications.utils import create_notification, send_notification


logger = get_task_logger(__name__)


@shared_task(name="myproject.payments.booking_confirmed_process")
def booking_confirmed_process(booking_id: str) -> None:
    booking = Booking.objects.get(id=booking_id)
    print(" ------------------------------------ ssl done -------------------------")

    guest = booking.guest
    host = booking.host

    with connect_mongo() as collections:
        listing = booking.listing
        mongo_from_user_id = collections["User"].find_one({"username": guest.username})
        mongo_to_user_id = collections["User"].find_one({"username": host.username})
        booking_data = {
            "check_in": str(booking.check_in),
            "check_out": str(booking.check_out),
            "total_guest_count": booking.guest_count,
            "adult": booking.adult_count,
            "children": booking.children_count,
            "infant": booking.infant_count,
        }

        if not mongo_from_user_id or not mongo_to_user_id:
            return

        room_name = f"{guest.username}:{host.username}"
        chat_room = collections["ChatRoom"].find_one({"name": room_name}) or None

        if not chat_room:
            chat_room = collections["ChatRoom"].insert_one(
                {
                    "name": room_name,
                    "from_user": DBRef("User", mongo_from_user_id["_id"]),
                    "to_user": DBRef("User", mongo_to_user_id["_id"]),
                    "created_at": datetime.now(),
                    "status": "open",
                    # "listing": {"name": listing.title, "id": listing.id},
                    # "booking_data": booking_data,
                }
            )
            chat_room_id = chat_room.inserted_id
        else:
            chat_room_id = chat_room["_id"]

        guest_or_guests = "guests" if booking.guest_count > 1 else "guest"
        content = f"Your booking confirmed for {booking.guest_count} {guest_or_guests}, on {format_date(str(booking.check_in))} - {format_date(str(booking.check_out))}"
        collections["Message"].insert_one(
            {
                "chat_room": DBRef("ChatRoom", chat_room_id),
                "user": DBRef("User", mongo_from_user_id["_id"]),
                "m_type": "system",
                "content": content,
                "is_read": False,
                "meta": {
                    "listing": None,
                    "booking": {
                        "id": booking.id,
                        "invoice_no": booking.invoice_no,
                        "reservation_code": booking.reservation_code,
                    },
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )

        collections["ChatRoom"].update_one(
            {"_id": chat_room_id},
            {
                "$set": {
                    "latest_message": {
                        "content": content,
                        "created_at": datetime.now(),
                        "user": {
                            "username": mongo_from_user_id["username"],
                            "full_name": mongo_from_user_id["full_name"],
                            "image": mongo_from_user_id["image"],
                            "user_id": mongo_from_user_id["user_id"],
                        },
                        "m_type": "system",
                    },
                    "status": "confirmed",
                    "booking_data": booking_data,
                    "listing": {"name": listing.title, "id": listing.id},
                    "updated_at": datetime.now(),
                }
            },
        )

        event_type = NotificationEventTypeOption.BOOKING_CONFIRMED
        host_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(booking.listing.unique_id),
                "message": "Congratulations ! A guest booked your property just now",
                "link": f"/host-dashboard/inbox?conversation_id={chat_room_id}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking.host_id,
        )

        guest_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(booking.listing.unique_id),
                "message": "Congratulations ! You’ve successfully completed your booking",
                "link": f"/messages?conversation_id={chat_room_id}",
            },
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking.guest_id,
        )

        admin_notification = create_notification(
            event_type=event_type,
            data={
                "identifier": str(booking.listing.unique_id),
                "message": "A new booking has been confirmed",
                "link": f"/chat?id={chat_room_id}",
            },
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )

        notification_data = [
            host_notification,
            guest_notification,
            admin_notification,
        ]
        Notification.objects.bulk_create(
            [Notification(**item) for item in notification_data]
        )
        booking.chat_room_id = chat_room_id
        booking.save()

        send_notification(notification_data=notification_data)
        print(" --------------- send pre --------------")

        host_device_token = FCMToken.objects.filter(user_id=booking.host_id).first()
        if host_device_token :
            title = "Booking Message"
            body = f"Congratulations ! A guest booked your property just now"
            data = {
                "url": f"/host-dashboard/inbox?conversation_id={chat_room_id}",
                "key2": "value2",
            }
            send_fcm_notification_without_task(
                host_device_token.token, title, body, data
            )

        guest_device_token = FCMToken.objects.filter(user_id=booking.guest_id).first()
        if guest_device_token :
            title = "Booking Message"
            body = f"Congratulations ! You’ve successfully completed your booking"
            data = {
                "url": f"/messages?conversation_id={chat_room_id}",
                "key2": "value2",
            }
            send_fcm_notification_without_task(
                guest_device_token.token, title, body, data
            )

