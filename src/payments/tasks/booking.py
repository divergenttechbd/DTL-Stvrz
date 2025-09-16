from datetime import datetime
from django.conf import settings
from bson import DBRef
from django.contrib.auth import get_user_model

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
User = get_user_model()


@shared_task(name="myproject.payments.booking_confirmed_process")
def booking_confirmed_process(booking_id: str) -> None:

    print(" ========== booking in side task")
    try:
        booking = Booking.objects.select_related('guest', 'host', 'listing').get(id=booking_id)
    except Booking.DoesNotExist:
        logger.error(f"Booking with ID {booking_id} not found for confirmation task.")
        return

    guest = booking.guest
    listing = booking.listing
    main_host = listing.host

    # --- MODIFICATION: GATHER ALL HOSTS AND CREATE CANONICAL ROOM NAME ---
    active_co_hosts = User.objects.filter(cohosting_gigs__listing=listing, cohosting_gigs__is_active=True)
    all_recipients = list(set([main_host] + list(active_co_hosts)))
    host_usernames = [user.username for user in all_recipients]
    sorted_host_usernames = sorted(host_usernames)
    room_name = f"{guest.username}:{':'.join(sorted_host_usernames)}"

    print(room_name, " room name")
    # --- END MODIFICATION ---

    with connect_mongo() as collections:
        mongo_guest_doc = collections["User"].find_one({"username": guest.username})
        mongo_host_docs = list(collections["User"].find({"username": {"$in": host_usernames}}))

        booking_data = {
            "check_in": str(booking.check_in), "check_out": str(booking.check_out),
            "total_guest_count": booking.guest_count, "adult": booking.adult_count,
            "children": booking.children_count, "infant": booking.infant_count,
        }

        if not mongo_guest_doc or len(mongo_host_docs) != len(all_recipients):
            logger.error(f"Mismatch of users in Mongo for booking {booking_id}. Cannot create/update chat room.")
            return

        # Use the new canonical room name to find or create the chat room
        chat_room = collections["ChatRoom"].find_one({"name": room_name})

        print(" chat_room ", chat_room)

        if not chat_room:
            created_room = collections["ChatRoom"].insert_one({
                "name": room_name,
                "from_user": DBRef("User", mongo_guest_doc["_id"]),
                "to_user": [DBRef("User", doc["_id"]) for doc in mongo_host_docs],  # Create as a group chat
                "created_at": datetime.now(),
                "status": "open",
            })
            chat_room_id = created_room.inserted_id
        else:
            chat_room_id = chat_room["_id"]

        guest_or_guests = "guests" if booking.guest_count > 1 else "guest"
        content = f"Your booking is confirmed for {booking.guest_count} {guest_or_guests}, from {format_date(str(booking.check_in))} to {format_date(str(booking.check_out))}"

        # Insert the system message
        collections["Message"].insert_one({
            "chat_room": DBRef("ChatRoom", chat_room_id),
            "user": DBRef("User", mongo_guest_doc["_id"]),
            "m_type": "system",
            "content": content,
            "is_read": False,
            "meta": {
                "listing": {"name": listing.title, "id": listing.id, "unique_id": str(listing.unique_id)},
                "booking": {"id": booking.id, "invoice_no": booking.invoice_no,
                            "reservation_code": booking.reservation_code},
            },
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        })

        # Update the chat room with latest message and status
        collections["ChatRoom"].update_one(
            {"_id": chat_room_id},
            {"$set": {
                "latest_message": {
                    "content": content, "created_at": datetime.now(),
                    "user": {"username": mongo_guest_doc["username"], "full_name": mongo_guest_doc["full_name"],
                             "image": mongo_guest_doc["image"], "user_id": mongo_guest_doc["user_id"]},
                    "m_type": "system",
                },
                "status": "confirmed", "booking_data": booking_data,
                "listing": {"name": listing.title, "id": listing.id},
                "updated_at": datetime.now(),
            }}
        )

        # --- MODIFICATION: NOTIFY ALL HOSTS/CO-HOSTS ---
        event_type = NotificationEventTypeOption.BOOKING_CONFIRMED
        notification_data = []

        for recipient in all_recipients:
            host_notification = create_notification(
                event_type=event_type,
                data={"identifier": str(listing.unique_id), "message": "Congratulations! A guest booked your property.",
                      "link": f"/host-dashboard/inbox?conversation_id={chat_room_id}"},
                n_type=NotificationTypeOption.USER_NOTIFICATION,
                user_id=recipient.id,
            )
            notification_data.append(host_notification)

            host_device_token = FCMToken.objects.filter(user_id=recipient.id).first()
            if host_device_token:
                send_fcm_notification_without_task(
                    host_device_token.token,
                    "Booking Confirmed",
                    "Congratulations! A guest booked your property.",
                    {"url": f"/host-dashboard/inbox?conversation_id={chat_room_id}"}
                )

        guest_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id),
                  "message": "Congratulations! You’ve successfully completed your booking.",
                  "link": f"/messages?conversation_id={chat_room_id}"},
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking.guest_id,
        )
        notification_data.append(guest_notification)

        admin_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id),
                  "message": f"A new booking has been confirmed for '{listing.title}'.",
                  "link": f"/chat?id={chat_room_id}"},
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data.append(admin_notification)

        Notification.objects.bulk_create([Notification(**item) for item in notification_data])

        # Save the correct chat room ID to the booking
        booking.chat_room_id = str(chat_room_id)
        booking.save()

        send_notification(notification_data=notification_data)

        guest_device_token = FCMToken.objects.filter(user_id=booking.guest_id).first()
        if guest_device_token:
            send_fcm_notification_without_task(
                guest_device_token.token,
                "Booking Confirmed",
                "Congratulations! You’ve successfully completed your booking.",
                {"url": f"/messages?conversation_id={chat_room_id}"}
            )
