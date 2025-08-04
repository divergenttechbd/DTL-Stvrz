from datetime import datetime
from django.conf import settings
from bson import DBRef
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model

from base.helpers.utils import format_date
from base.mongo.connection import connect_mongo

from base.type_choices import NotificationEventTypeOption, NotificationTypeOption
from bookings.models import Booking
from notifications.models import Notification
from notifications.utils import create_notification, send_notification


logger = get_task_logger(__name__)
User = get_user_model()

@shared_task(name="myproject.payments.booking_cancelled_process")
def booking_cancelled_process(booking_id: str) -> None:
    try:
        booking = Booking.objects.select_related('guest', 'host', 'listing').get(id=booking_id)
    except Booking.DoesNotExist:
        logger.error(f"Booking with ID {booking_id} not found for cancellation task.")
        return

    guest = booking.guest
    listing = booking.listing
    main_host = listing.host

    # --- GATHER ALL HOSTS AND CREATE CANONICAL ROOM NAME ---
    active_co_hosts = User.objects.filter(cohosting_gigs__listing=listing, cohosting_gigs__is_active=True)
    all_recipients = list(set([main_host] + list(active_co_hosts)))
    host_usernames = [user.username for user in all_recipients]
    sorted_host_usernames = sorted(host_usernames)
    room_name = f"{guest.username}:{':'.join(sorted_host_usernames)}"

    with connect_mongo() as collections:
        mongo_guest_doc = collections["User"].find_one({"username": guest.username})

        booking_data = {
            "check_in": str(booking.check_in), "check_out": str(booking.check_out),
            "total_guest_count": booking.guest_count, "adult": booking.adult_count,
            "children": booking.children_count, "infant": booking.infant_count,
        }

        if not mongo_guest_doc:
            logger.error(
                f"Mongo user for guest {guest.username} not found. Cannot update chat room for booking {booking_id}.")
            return

        chat_room = collections["ChatRoom"].find_one({"name": room_name})

        if not chat_room:
            logger.warning(
                f"Chat room '{room_name}' not found for cancelled booking {booking_id}. System message will not be posted.")
            chat_room_id_str = booking.chat_room_id  # Fallback to existing ID on booking
        else:
            chat_room_id = chat_room["_id"]
            chat_room_id_str = str(chat_room_id)
            content = "This booking was successfully cancelled."

            # Insert the system message
            collections["Message"].insert_one({
                "chat_room": DBRef("ChatRoom", chat_room_id),
                "user": DBRef("User", mongo_guest_doc["_id"]),
                "m_type": "system",
                "content": content,
                "is_read": False,
                "meta": {
                    "listing": None,
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
                    "status": "cancelled", "booking_data": booking_data,
                    "listing": {"name": listing.title, "id": listing.id},
                    "updated_at": datetime.now(),
                }}
            )

        # --- NOTIFY ALL HOSTS/CO-HOSTS ---
        event_type = NotificationEventTypeOption.BOOKING_CANCELLED
        notification_data = []

        for recipient in all_recipients:
            host_notification = create_notification(
                event_type=event_type,
                data={"identifier": str(listing.unique_id),
                      "message": "A guest has cancelled their booking for your property.",
                      "link": f"/host-dashboard/inbox?conversation_id={chat_room_id_str}"},
                n_type=NotificationTypeOption.USER_NOTIFICATION,
                user_id=recipient.id,
            )
            notification_data.append(host_notification)

        guest_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id), "message": "You’ve successfully cancelled your booking.",
                  "link": f"/messages?conversation_id={chat_room_id_str}"},
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=booking.guest_id,
        )
        notification_data.append(guest_notification)

        admin_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id),
                  "message": f"A booking for '{listing.title}' has been cancelled.",
                  "link": f"/chat?id={chat_room_id_str}"},
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data.append(admin_notification)

        Notification.objects.bulk_create([Notification(**item) for item in notification_data])

        # --- booking.save() is RESTORED HERE ---
        # It's possible other parts of the cancellation logic (not shown here)
        # modified the booking object (e.g., status, refund_amount).
        # This ensures any such changes are persisted to the database.
        if chat_room:  # Only update the chat_room_id if we successfully found/used it
            booking.chat_room_id = chat_room_id_str
        booking.save()
        # --- END OF RESTORATION ---

        send_notification(notification_data=notification_data)
