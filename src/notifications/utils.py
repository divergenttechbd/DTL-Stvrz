from base.type_choices import NotificationEventTypeOption, NotificationTypeOption
from notifications.models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .tasks import send_fcm_push_notification_task

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.contrib.auth import get_user_model

# Your other utility functions (create_notification, etc.) are here
from .models import FCMToken
from base.cache.redis_cache import get_cache # Or wherever get_cache is

User = get_user_model()

def send_notification(notification_data: list):

    print( " ------------------------- send notification -----------------------")
    for item in notification_data:
        channel_layer = get_channel_layer()
        if item.get("user_id"):
            unread_notifications_count = Notification.objects.filter(
                user_id=item.get("user_id"), is_read=False
            ).count()
        else:
            unread_notifications_count = Notification.objects.filter(
                n_type=NotificationTypeOption.ADMIN_NOTIFICATION, is_read=False
            ).count()
        async_to_sync(channel_layer.group_send)(
            f"{item.get('user_id', 'admin')}_notify",
            {
                "type": "notifications",
                "message": item["data"]["message"],
                "count": unread_notifications_count,
            },
        )

        # print(" ----------- fcm -----------")
        # if item.get("user_id"):
        #     user_id = item.get("user_id")
        #     title = "You have a new notification!"
        #     body = item["data"]["message"]
        #
        #
        #     payload_data = {
        #         "url": item["data"].get("link", "/"),
        #         "identifier": item["data"].get("identifier", "")
        #     }
        #
        #     print(f"Dispatching FCM push task for user_id: {user_id}")
        #     send_fcm_push_directly(
        #         user_id=user_id,
        #         title=title,
        #         body=body,
        #         data=payload_data
        #     )


def create_notification(
    event_type: NotificationEventTypeOption,
    n_type: NotificationTypeOption,
    data: dict,
    user_id: str | None = None,
) -> dict:
    data = {
        "event_type": event_type,
        "data": data,
        "n_type": n_type,
    }
    if user_id:
        data["user_id"] = user_id

    return data




def send_fcm_push_directly(user_id, title, body, data=None):

    print(f"--- Attempting to send FCM directly to user_id: {user_id} ---")
    try:
        user = User.objects.get(id=user_id)
        fcm_record = FCMToken.objects.filter(user=user).first()

        if not fcm_record or not fcm_record.token:
            print(f"Direct FCM: No token found for user_id {user_id}.")
            return

        android_config = messaging.AndroidConfig(
            priority='high'
        )
        apns_config = messaging.APNSConfig(
            headers={'apns-priority': '10'}
        )

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data if data else {},
            token=fcm_record.token,
            android=android_config,
            apns=apns_config,
        )

        response = messaging.send(message)
        print(f"Direct FCM: Successfully sent notification to {user.username}: {response}")

    except User.DoesNotExist:
        print(f"Direct FCM: User with id {user_id} does not exist.")
    except messaging.UnregisteredError:
        print(f"Direct FCM: Token for user {user_id} is unregistered. Deleting.")
        if 'fcm_record' in locals():
            fcm_record.delete()
    except Exception as e:
        print(f"Direct FCM: An unexpected error occurred for user_id {user_id}: {e}")
