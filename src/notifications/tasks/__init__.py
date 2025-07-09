from celery import shared_task
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from django.contrib.auth import get_user_model

from base.cache.redis_cache import get_cache
from notifications.models import FCMToken

# It's better to initialize Firebase only once when the app starts.
# A good place for this is a top-level __init__.py or in your settings.py.
# If you haven't already, ensure this runs only once.
# if not firebase_admin._apps:
#     cred = credentials.Certificate(settings.FCM_SERVER_KEY_PATH)
#     firebase_admin.initialize_app(cred)

# Assuming you have an FCMToken model and a get_cache function

  # Or wherever get_cache is located

User = get_user_model()

@shared_task(name="notifications.send_fcm_push")
def send_fcm_push_notification_task(user_id, title, body, data=None):
    """
    A robust Celery task to send a single FCM Push Notification.
    """
    try:

        user = User.objects.get(id=user_id)

        print(" -----------", user)
        fcm_record = FCMToken.objects.filter(user=user).first()

        print(fcm_record, " --- fcm")

        if not fcm_record or not fcm_record.token:
            print(f"FCM Task: No token found for user_id {user_id}.")
            return f"No token for user {user_id}"


        # if not get_cache(key=f"user_mobile_logged_in_{user.username}"):
        #     print(f"FCM Task: User {user.username} is not logged in on mobile. Skipping push.")
        #     return f"User {user.username} not on mobile."

        # 3. Construct the FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data if data else {}, # For deep-linking, etc.
            token=fcm_record.token,
        )

        # 4. Send the message
        response = messaging.send(message)
        print(f"FCM Task: Successfully sent notification to {user.username}: {response}")
        return f"Success: {response}"

    except User.DoesNotExist:
        print(f"FCM Task: User with id {user_id} does not exist.")
        return f"User {user_id} not found."
    except FCMToken.DoesNotExist:
        print(f"FCM Task: FCMToken record not found for user_id {user_id}.")
        return f"FCMToken for user {user_id} not found."
    except messaging.UnregisteredError:
        print(f"FCM Task: Token for user {user_id} is unregistered. Deleting it.")
        # Good practice to clean up invalid tokens
        if 'fcm_record' in locals():
            fcm_record.delete()
        return "Token unregistered and deleted."
    except Exception as e:
        print(f"FCM Task: An unexpected error occurred for user_id {user_id}: {e}")
        return f"Error: {e}"
