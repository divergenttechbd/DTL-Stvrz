from firebase_admin import messaging, exceptions # Assuming you've initialized firebase_admin
from .models import FCMToken # Your FCMToken model
from django.contrib.auth import get_user_model

User = get_user_model()

def send_native_push_notification(user_id, title, body, data=None):
    """
    Sends a native FCM push notification to a user.
    'data' is a dictionary for custom payload (click_action, screen navigation, etc.).
    """
    try:
        fcm_record = FCMToken.objects.get(user_id=user_id)
        token = fcm_record.token

        if not token:
            print(f"PushService: No FCM token found for user ID {user_id}.")
            return False

        # Construct the FCM message
        # https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-specific-devices
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data if data else {}, # Custom key-value pairs
            token=token,
            # You can also set Android-specific or APNs-specific configurations here if needed
            # android=messaging.AndroidConfig(...),
            # apns=messaging.APNSConfig(...),
        )

        try:
            response = messaging.send(message)
            print(f"PushService: Successfully sent FCM message to user ID {user_id} (token: {token[:20]}...): {response}")
            return True
        except messaging.UnregisteredError:
            print(f"PushService: FCM token {token[:20]}... for user ID {user_id} is no longer registered. Deactivating.")
            # Optionally, deactivate the token or delete the FCMToken record
            # fcm_record.delete() # Or mark as inactive
            return False
        except exceptions.FirebaseError as e:
            print(f"PushService: Error sending FCM message to user ID {user_id} (token: {token[:20]}...): {e}")
            return False
        except Exception as e: # Catch any other error
            print(f"PushService: General error sending FCM to user ID {user_id}: {e}")
            return False

    except FCMToken.DoesNotExist:
        print(f"PushService: No FCMToken record found for user ID {user_id}.")
        return False
    except Exception as e:
        print(f"PushService: Outer error for user ID {user_id}: {e}")
        return False
