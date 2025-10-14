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

from base.type_choices import NotificationEventTypeOption, NotificationTypeOption, UserTypeOption
from listings.models import Listing
from listings.views.service import ListingCalendarDataProcess, ListingCheckoutCalculate
from notifications.models import FCMToken, Notification
from notifications.tasks.notification import send_fcm_notification
from notifications.utils import create_notification, send_notification
import re
User = get_user_model()
import json

class UserChatApiView(views.APIView):
    permission_classes = (IsAuthenticated,)
    swagger_tags = ["User Chat"]

    def post(self, request, *args, **kwargs):

        current_date = date.today()
        try:
            listing_id = request.data["listing"]
            booking_data = request.data["booking_data"]
            message = request.data["message"]
            main_host_id_from_request = request.data["to_user"]
        except KeyError as e:
            return Response({"message": f"Missing required field: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        if is_contact_info_present(message):
            return Response(
                {
                    "message": "Sending contact information is not allowed. Please use the platform's messaging system for communication.",
                    "error_type": "contact_info_forbidden"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            listing = Listing.objects.select_related('host').get(id=listing_id)

            print(listing.host.id, " ===== ", main_host_id_from_request)
            if str(listing.host.id) != str(main_host_id_from_request):
                return Response({"message": "Invalid host for the given listing."}, status=status.HTTP_400_BAD_REQUEST)
        except Listing.DoesNotExist:
            return Response({"message": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)



        from_date = datetime.strptime(booking_data["check_in"], "%Y-%m-%d").date()
        to_date = datetime.strptime(booking_data["check_out"], "%Y-%m-%d").date()

        if from_date < current_date or to_date < current_date or not to_date > from_date:
            return Response({"message": "Invalid booking dates"}, status=status.HTTP_400_BAD_REQUEST)

        # --- 2. GATHER ALL HOSTS AND CREATE CANONICAL ROOM NAME ---
        guest_user = request.user
        main_host = listing.host
        
        # Get all active co-hosts for this listing
        active_co_hosts = User.objects.filter(cohosting_gigs__listing=listing, cohosting_gigs__is_active=True)
        
        # Combine main host and co-hosts into a single list of recipients
        all_recipients = list(set([main_host] + list(active_co_hosts)))
        
        if not all_recipients:
            return Response({"message": "No valid host or co-hosts found for this listing."}, status=status.HTTP_400_BAD_REQUEST)


        # Get all host usernames and sort them to create a deterministic, canonical name
        # Get all host usernames and sort them to create a deterministic, canonical name
        host_usernames = [user.username for user in all_recipients]
        sorted_host_usernames = sorted(host_usernames)
        
        # The room name is now unique to the guest and the group of hosts
        room_name = f"{guest_user.username}:{':'.join(sorted_host_usernames)}"

        print(" ==== ", room_name, " ====")

        # --- 3. BUSINESS LOGIC (Calendar & Checkout Calculation) ---
        date_filter = {"from_date": from_date, "to_date": to_date}
        calendar_data = ListingCalendarDataProcess()(date_filter, listing_id)
        if calendar_data:
            calendar_data.popitem()

        checkout_data = ListingCheckoutCalculate()(
            booking_date_info=calendar_data.copy(),
            date_range=date_filter,
            instance=listing,
        )
        if checkout_data["status"] != 200:
            return Response({"message": checkout_data["message"]}, status=status.HTTP_400_BAD_REQUEST)
        checkout_data = checkout_data["data"]
        
        # --- 4. MONGO DB INTERACTION (Find or Create Room and Messages) ---
        with connect_mongo() as collections:

            document = collections["ChatRoom"].find_one({"name": room_name})


            mongo_from_user_doc = collections["User"].find_one({"username": guest_user.username})
            mongo_to_user_docs = list(collections["User"].find({"username": {"$in": host_usernames}}))

            print(guest_user.username, mongo_from_user_doc, len(mongo_to_user_docs), len(all_recipients), " >>> === ",all_recipients, "<< ----------------- >>", mongo_to_user_docs, " mdb")
            

            if not mongo_from_user_doc or len(mongo_to_user_docs) != len(all_recipients):
                 return Response({"message": "One or more users not found in chat service. Please ensure users are synced."}, status=status.HTTP_404_NOT_FOUND)

            if document:
                room_id = document["_id"]
            else:
                # Create the room with the new group structure
                created_room = collections["ChatRoom"].insert_one({
                    "name": room_name,
                    "from_user": DBRef("User", mongo_from_user_doc["_id"]),
                    "to_user": [DBRef("User", doc["_id"]) for doc in mongo_to_user_docs], # Use to_users list
                    "created_at": datetime.now(),
                    "status": "open",
                })
                room_id = created_room.inserted_id

            # Insert system message for inquiry
            collections["Message"].insert_one({
                "chat_room": DBRef("ChatRoom", room_id),
                "user": DBRef("User", mongo_from_user_doc["_id"]),
                "m_type": "system",
                "is_read": False,
                "content": f"Inquiry sent · {booking_data['total_guest_count']} guest, {format_date(booking_data['check_in'])} - {format_date(booking_data['check_out'])}",
                "meta": {"listing": str(listing.unique_id),
                         "booking": {"booking_date": booking_data, "checkout_data": checkout_data}, "user": request.user.id},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            })

            print(" ----- ", booking_data)
            print(" ===== ", checkout_data)

            # Insert user's actual message
            collections["Message"].insert_one({
                "chat_room": DBRef("ChatRoom", room_id),
                "user": DBRef("User", mongo_from_user_doc["_id"]),
                "content": message,
                "meta": None,
                "m_type": "normal",
                "is_read": False,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            })

            # Update the ChatRoom's latest message and other metadata
            collections["ChatRoom"].update_one(
                {"_id": room_id},
                {"$set": {
                    "latest_message": {
                        "content": message,
                        "created_at": datetime.now(),
                        "user": {"username": mongo_from_user_doc["username"], "full_name": mongo_from_user_doc["full_name"], "image": mongo_from_user_doc["image"], "user_id": mongo_from_user_doc["user_id"]},
                        "m_type": "normal",
                        "is_read": False, # Ensure new messages are marked unread
                    },
                    "status": "inquiry",
                    "booking_data": booking_data,
                    "listing": {"name": listing.title, "id": listing.id},
                    "updated_at": datetime.now(),
                }}
            )

        # --- 5. NOTIFICATION DISPATCH (to Guest, all Hosts, and Admin) ---
        event_type = NotificationEventTypeOption.BOOKING_INQUIRY
        notification_data = []

        # Create notifications for each host and co-host
        for recipient in all_recipients:
            host_notification = create_notification(
                event_type=event_type,
                data={"identifier": str(listing.unique_id), "message": "You’ve received a new inquiry for your property", "link": f"/host-dashboard/inbox?conversation_id={room_id}"},
                n_type=NotificationTypeOption.USER_NOTIFICATION,
                user_id=recipient.id,
            )
            notification_data.append(host_notification)

            send_sms(username=recipient.phone_number, message=f"You've got a new inquiry from {guest_user.get_full_name()}")
            
            host_device_token = FCMToken.objects.filter(user_id=recipient.id).first()
            if host_device_token:
                title = "New Inquiry"
                body = f"You've received a new inquiry from {guest_user.get_full_name()}"
                fcm_payload = {"url": f"/host-dashboard/inbox?conversation_id={room_id}"}
                send_fcm_notification.delay(host_device_token.token, title, body, fcm_payload)

        # Guest's own confirmation notification
        guest_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id), "message": "Your query has been sent to the hosting team.", "link": f"/messages?conversation_id={room_id}"},
            n_type=NotificationTypeOption.USER_NOTIFICATION,
            user_id=guest_user.id,
        )
        notification_data.append(guest_notification)

        # Admin notification
        admin_notification = create_notification(
            event_type=event_type,
            data={"identifier": str(listing.unique_id),
                  "message": f"A new inquiry has been initiated for '{listing.title}' between the hosting team and {guest_user.get_full_name()}",
                  "link": f"/chat?id={room_id}"},
            n_type=NotificationTypeOption.ADMIN_NOTIFICATION,
        )
        notification_data.append(admin_notification)
        
        # Bulk create all notifications for efficiency
        Notification.objects.bulk_create([Notification(**item) for item in notification_data])
        # Send notifications (if this function handles pushing them out)
        send_notification(notification_data=notification_data)

        return Response(
            {"message": "Message sent to hosting team", "data": {"chat_room_id": str(room_id)}},
            status=status.HTTP_201_CREATED,
        )

WORD_TO_DIGIT = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
}


def is_valid_json_string(s: str) -> bool:
    """
    Checks if a string is a valid, self-contained JSON object or array.
    """
    s = s.strip()
    if not ((s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']'))):
        return False
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False


def remove_uuids(text: str) -> str:
    """
    Removes standard UUID formats from a string to prevent false positives.
    """
    uuid_pattern = re.compile(
        r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
        re.IGNORECASE
    )
    return uuid_pattern.sub('', text)


def convert_written_numbers_to_digits(text: str) -> str:
    """
    Converts written numbers (e.g., "one", "two") to digits in the text.
    """
    word_pattern = r'\b(' + '|'.join(WORD_TO_DIGIT.keys()) + r')\b'

    def replace_word(match):
        return WORD_TO_DIGIT.get(match.group(0).lower(), '')

    return re.sub(word_pattern, replace_word, text, flags=re.IGNORECASE)


def has_long_number_sequences(message_content: str) -> bool:
    """
    Detects if conversational text contains sequences of 5 or more numbers.
    It explicitly allows messages that are valid JSON strings or contain UUIDs.
    """
    # 1. Allow if the entire message is a valid JSON string.
    if is_valid_json_string(message_content):
        return False

    # 2. Remove UUIDs from the content to prevent them from being flagged.
    cleaned_message = remove_uuids(message_content)

    # 3. Convert any remaining number words to digits.
    converted_message = convert_written_numbers_to_digits(cleaned_message)

    # 4. Remove all non-digit characters (like -, _, spaces) to concatenate numbers.
    # This is the key step that handles all separator formats.
    digits_only = re.sub(r'\D', '', converted_message)

    # 5. Block if the resulting sequence of digits is 5 or longer.
    if len(digits_only) > 5:
        print(f"Blocked: Found long number sequence: '{digits_only}'")
        return True

    return False

def is_email_present(message: str) -> bool:
    """
    Conservative email detection
    """
    # Basic email pattern - only catch obvious emails
    basic_email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'

    if re.search(basic_email_pattern, message):
        return True

    # Check for obvious email obfuscation attempts
    obfuscation_patterns = [
        r'[A-Za-z0-9._%+-]+\s*(?:at|AT)\s*[A-Za-z0-9.-]+\s*(?:dot|DOT)\s*(?:com|org|net|edu|gov)',
        r'[A-Za-z0-9._%+-]+\s*[\(\[\{]at[\)\]\}]\s*[A-Za-z0-9.-]+\s*[\(\[\{]dot[\)\]\}]\s*[A-Za-z]{2,4}',
        r'(?:email|e-mail|mail|contact)[\s\-:]*(?:is|address)?[\s\-:]*[A-Za-z0-9._%+-]+[@at][A-Za-z0-9.-]+[.dot][A-Za-z]{2,4}',
    ]

    for pattern in obfuscation_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True

    return False


def is_contact_info_present(message_content: str) -> bool:
    """
    Main validation function. It checks the extracted 'message' field from the websocket payload.
    """
    # Ensure the content to check is a string
    if not isinstance(message_content, str):
        # If the content is not a string (e.g., a dict or list from the JSON),
        # it's considered structured data and should be allowed.
        return False

    print("--- Running Contact Info Check ---")

    if has_long_number_sequences(message_content):
        return True

    if is_email_present(message_content):
        print("Blocked: Found email address.")
        return True

    return False
