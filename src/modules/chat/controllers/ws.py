import json
from enum import Enum
from typing import Any
import anyio
from beanie import PydanticObjectId, Link
from bson import ObjectId

from datetime import datetime, timedelta
from src.core.cache.cache_manager import Cache
from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from pydantic import BaseModel
from src.core.fcm.push_notification import send_fcm_notification
from src.core.helpers.enum import RoomStatusEnum, UserTypeOption
from src.modules.users.schemas import UserLiteBase
from src.modules.chat.schemas import (
    ChatRoomMessageResponse,
    ChatRoomMessageResponse2,
    ChatRoomResponse,
)
from src.modules.chat.models import ChatRoom
from src.modules.users.models import User
from src.core.broadcaster import Broadcast
from src.core.di import Container
from src.modules.chat.service import ChatService
import re

# broadcast = Broadcast("redis://localhost:6379")
# broadcast = Broadcast("redis://192.168.7.172:6379")
broadcast = Broadcast("redis://45.114.85.18:6379")

router = APIRouter(prefix="/user")
import re
from typing import Any

import re
from typing import Any

# change p---
def is_likely_uuid(text: str) -> bool:
    """
    Check if a string is likely a UUID based on length and alphanumeric content
    """
    # Remove common separators
    clean_text = re.sub(r'[-_\s{}()]', '', text)

    # Check if it's alphanumeric and has UUID-like length
    if re.match(r'^[0-9a-fA-F]+$', clean_text):
        # Standard UUID without separators is 32 characters
        # Allow some flexibility for variations
        if len(clean_text) >= 28 and len(clean_text) <= 36:
            return True

    return False


def remove_uuids_from_message(message: str) -> str:
    """
    Remove UUIDs and UUID-like strings from message
    """
    UUID_REGEX = re.compile(
        r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
    )

    UUID_VARIANTS_REGEX = re.compile(
        r'''
        (?:
            # Standard UUID format
            \b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b|
            # UUID without hyphens
            \b[0-9a-fA-F]{32}\b|
            # UUID with spaces instead of hyphens
            \b[0-9a-fA-F]{8}\s[0-9a-fA-F]{4}\s[0-9a-fA-F]{4}\s[0-9a-fA-F]{4}\s[0-9a-fA-F]{12}\b|
            # UUID with underscores
            \b[0-9a-fA-F]{8}_[0-9a-fA-F]{4}_[0-9a-fA-F]{4}_[0-9a-fA-F]{4}_[0-9a-fA-F]{12}\b|
            # UUID in curly braces
            \{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}
        )
        ''',
        re.VERBOSE | re.IGNORECASE
    )

    cleaned_message = UUID_REGEX.sub('', message)
    cleaned_message = UUID_VARIANTS_REGEX.sub('', cleaned_message)

    # Additional check for UUID-like alphanumeric strings
    words = cleaned_message.split()
    filtered_words = []
    for word in words:
        if not is_likely_uuid(word):
            filtered_words.append(word)

    return ' '.join(filtered_words)


def is_phone_number_present(message: str) -> bool:
    """
    Enhanced phone number detection that catches various formats including special characters
    """
    # Remove UUIDs first
    cleaned_message = remove_uuids_from_message(message)

    # Remove JSON structure and common non-phone contexts to avoid false positives
    temp_message = cleaned_message

    # Remove entire JSON-like structures
    temp_message = re.sub(r"'[^']*':\s*\d+", "", temp_message)
    temp_message = re.sub(r"'[^']*':\s*'[^']*'", "", temp_message)
    temp_message = re.sub(r'"[^"]*":\s*\d+', "", temp_message)
    temp_message = re.sub(r'"[^"]*":\s*"[^"]*"', "", temp_message)

    # Remove common non-phone number patterns
    temp_message = re.sub(r'BDT\s*\d+', '', temp_message)
    temp_message = re.sub(r'\d+/per\s+\w+', '', temp_message)
    temp_message = re.sub(r'\d+(?:st|nd|rd|th)\s+floor', '', temp_message)
    temp_message = re.sub(r'https?://[^\s\'\"]+', '', temp_message)

    # Define common separators used in phone numbers (including special chars)
    separators = r'[\s\-_\.,:;|/\\~`!@#$%^&*()+=\[\]{}\'"]'

    # Enhanced phone number patterns - catches variations with special characters
    phone_patterns = [
        # Phone numbers with clear context words and any separators
        rf'(?:phone|mobile|call|contact|number|dial|reach){separators}*(?:\+?88{separators}*)?0?1[0-9]{separators}*\d{{8,9}}',

        # Phone numbers with specific formatting (parentheses, brackets, etc.)
        rf'[\(\[\{{](?:\+?88{separators}*)?0?1[0-9]{separators}*\d{{8,9}}[\)\]\}}]',

        # Phone numbers with country code clearly indicated
        rf'\+88{separators}*0?1[0-9]{separators}*\d{{8,9}}',

        # Phone numbers with any separators - flexible pattern
        rf'(?<!\d)01[0-9](?:{separators}+\d){{8,9}}(?!\d)',

        # Stand-alone phone numbers with various separators
        rf'(?<!\d)(?:\+?88{separators}*)?01[0-9](?:{separators}*\d){{8,9}}(?!\d)(?=\s|$|[^\d])',

        # Catch patterns like "017-1-69-90881" or "017*1*69*90881" etc.
        rf'(?<!\d)01[0-9]{separators}+\d{separators}+\d{{2}}{separators}+\d{{5}}(?!\d)',

        # General pattern for numbers with any special character separators
        rf'(?<!\d)01[0-9](?:{separators}*\d){{8,9}}(?!\d)',

        # Pattern for phone numbers disguised with multiple special chars
        rf'(?<!\d)0{separators}*1{separators}*[0-9](?:{separators}*\d){{8,9}}(?!\d)',
    ]

    # Check patterns on cleaned message
    for pattern in phone_patterns:
        matches = re.findall(pattern, temp_message, re.IGNORECASE)
        for match in matches:
            # Extract only digits
            digits_only = re.sub(r'[^\d]', '', match)

            # More flexible validation - any number starting with 01 and having 10-11 digits
            if len(digits_only) >= 10 and len(digits_only) <= 13:
                if digits_only.startswith('01'):
                    return True
                elif len(digits_only) >= 12 and digits_only.startswith('88') and digits_only[2:4] == '01':
                    return True

    # Additional check: Look for sequences that could be phone numbers with special chars
    # This catches creative obfuscation attempts
    potential_phone_pattern = rf'(?<!\d)0{separators}*1{separators}*[0-9](?:{separators}*\d){{7,10}}(?!\d)'
    potential_matches = re.findall(potential_phone_pattern, cleaned_message, re.IGNORECASE)

    for match in potential_matches:
        digits_only = re.sub(r'[^\d]', '', match)
        if len(digits_only) >= 10 and len(digits_only) <= 11 and digits_only.startswith('01'):
            # Check if it's not within structured data
            match_context = re.search(r'.{0,20}' + re.escape(match) + r'.{0,20}', cleaned_message)
            if match_context:
                context = match_context.group()
                if not (re.search(r'[\'"][^\'":]*' + re.escape(match) + r'[^\'":]*[\'"]', context) or
                        re.search(r'[\'"][^\'":]*:\s*' + re.escape(match), context)):
                    return True

    # Check for obvious phone sharing patterns with special characters
    phone_sharing_patterns = [
        rf'(?:my|call|phone|mobile|number|contact)[\s\w]*(?:is|:){separators}*(?:\+?88{separators}*)?0?1[0-9]{separators}*\d{{8,9}}',
        rf'(?:\+?88{separators}*)?0?1[0-9]{separators}*\d{{8,9}}{separators}*(?:is|call|phone|mobile|number|contact)',
    ]

    for pattern in phone_sharing_patterns:
        if re.search(pattern, temp_message, re.IGNORECASE):
            return True

    # Special check for heavily obfuscated numbers
    # Look for patterns like "zero one seven", "0-1-7", "0*1*7" etc.
    obfuscated_patterns = [
        # Numbers spelled out
        r'(?:zero|oh)\s*(?:one|1)\s*(?:seven|7|eight|8|nine|9|six|6|five|5|four|4|three|3|two|2)',
        # With dots, stars, or other special chars between each digit
        rf'0{separators}+1{separators}+[0-9](?:{separators}+\d){{7,9}}',
    ]

    for pattern in obfuscated_patterns:
        if re.search(pattern, temp_message, re.IGNORECASE):
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


def is_contact_info_present(message: str) -> bool:
    """
    Enhanced contact info detection
    """
    message_without_uuids = remove_uuids_from_message(message).strip()
    if not message_without_uuids:
        return False

    if is_email_present(message):
        return True

    if is_phone_number_present(message):
        return True

    return False

def custom_encoder(obj):
    """A robust JSON encoder for Pydantic V2."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, (ObjectId, PydanticObjectId)):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@router.websocket("/user-global-room/")
async def websocket_user_global_room_endpoint(
    websocket: WebSocket,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> None:
    await websocket.accept()
    current_user = websocket.state.user
    print(current_user, " current user ")

    all_partners = await chat_service.get_user_all_room_partner(
        current_user=current_user
    )

    for partner_id in all_partners:
        await broadcast.publish(
            channel=f"user_global_room_{partner_id}",
            message=json.dumps(
                {
                    "message": f"{current_user.username} join the chat",
                    "user_id": str(current_user.id),
                    "action": "join",
                },
                default=custom_encoder,
            ),
        )
        print(" ======== ", partner_id)

    await chat_service.update_user_last_seen(
        current_user=current_user, online_status=True
    )

    async with anyio.create_task_group() as task_group:

        async def run_user_global_room_ws_receiver() -> None:
            await user_global_room_ws_receiver(
                websocket=websocket,
                current_user=current_user,
                all_partners=all_partners,
                chat_service=chat_service,
            )
            task_group.cancel_scope.cancel()

        task_group.start_soon(run_user_global_room_ws_receiver)
        await user_global_room_ws_sender(
            websocket=websocket, current_user_id=str(current_user.id)
        )


async def user_global_room_ws_receiver(
    websocket,
    current_user: User,
    all_partners: list,
    chat_service: ChatService,
):
    try:
        while True:
            print(" -- re - ")
            message = await websocket.receive_text()
            print(" === X ===")
            print(message, current_user.id, " ========= while ==== ")
            await broadcast.publish(
                channel=f"user_global_room_{current_user.id}", message=message
            )

    except WebSocketDisconnect:
        await chat_service.update_user_last_seen(
            current_user=current_user, online_status=False
        )
        for partner_id in all_partners:
            await broadcast.publish(
                channel=f"user_global_room_{partner_id}",
                message=json.dumps(
                    {
                        "message": f"{current_user.username} leave the chat",
                        "last_online": str(datetime.now()),
                        "user_id": str(current_user.id),
                        "action": "leave",
                    },
                    default=custom_encoder,
                ),
            )


async def user_global_room_ws_sender(websocket: WebSocket, current_user_id: str):
    async with broadcast.subscribe(
        channel=f"user_global_room_{current_user_id}"
    ) as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)


@router.websocket("/chat-stat/")
async def websocket_user_chat_stat(
    websocket: WebSocket,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> None:
    await websocket.accept()
    current_user = websocket.state.user

    try:
        # The service method now directly returns an integer.

        initial_count = await chat_service.get_user_unread_message_count(
            user_id=str(current_user.id), u_type=current_user.u_type
        )

        await websocket.send_text(json.dumps({"count": initial_count}))

        async with anyio.create_task_group() as task_group:
            async def receiver_task():
                await user_chat_stat_receiver(websocket)
                task_group.cancel_scope.cancel()

            task_group.start_soon(receiver_task)
            await user_chat_stat_sender(websocket, current_user, chat_service)

    except WebSocketDisconnect:
        print(f"User {current_user.username} disconnected from chat-stat.")
    except Exception as e:
        print(f"An error occurred in chat-stat websocket: {e}")
        try:
            await websocket.send_text(json.dumps({"error": "Internal server error", "count": 0}))
        except:
            pass
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


async def user_chat_stat_sender(
    websocket: WebSocket, current_user: User, chat_service: ChatService
):
    channel = f"chat_stat_{current_user.id}"
    async with broadcast.subscribe(channel=channel) as subscriber:
        async for event in subscriber:
            try:
                # The service method directly returns an integer.
                new_count = await chat_service.get_user_unread_message_count(
                    user_id=str(current_user.id), u_type=current_user.u_type
                )

                await websocket.send_text(json.dumps({"count": new_count}))

            except Exception as e:
                print(f"Error in user_chat_stat_sender: {e}")
                try:
                    await websocket.send_text(json.dumps({"error": "Failed to get count", "count": 0}))
                except:
                    pass


async def user_chat_stat_receiver(websocket: WebSocket):
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


@router.websocket("/{room_id}/")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> None:
    await websocket.accept()
    current_user = websocket.state.user

    chat_room, has_access = await chat_service.check_user_has_room_permission(
        room_id=room_id, current_user=current_user
    )
    if not has_access or not chat_room:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    # Explicitly fetch all nested links to prevent errors in the receiver task
    await chat_room.fetch_all_links()

    async with anyio.create_task_group() as task_group:
        async def run_chatroom_ws_receiver() -> None:
            await chatroom_ws_receiver(
                websocket=websocket,
                current_user=current_user,
                chat_room=chat_room,
                chat_service=chat_service,
            )
            task_group.cancel_scope.cancel()

        task_group.start_soon(run_chatroom_ws_receiver)
        await chatroom_ws_sender(websocket=websocket, room_id=room_id)


async def chatroom_ws_receiver(
    websocket: WebSocket,
    current_user: User,
    chat_room: ChatRoom,
    chat_service: ChatService,
) -> None:
    print(" =====>>><<<====")
    all_participants_ids = []

    # Add from_user (guest) - handle both Link and direct User objects
    if chat_room.from_user:
        try:
            if isinstance(chat_room.from_user, Link):
                from_user = await chat_room.from_user.fetch()
                if from_user and hasattr(from_user, 'id'):
                    all_participants_ids.append(from_user.id)
            elif hasattr(chat_room.from_user, 'id'):
                all_participants_ids.append(chat_room.from_user.id)
            print(f"Added from_user: {all_participants_ids}")
        except Exception as e:
            print(f"Error processing from_user: {e}")

    # Add to_user (host/co-hosts) - handle both single Link, list of Links, and direct User objects
    if chat_room.to_user:
        try:
            if isinstance(chat_room.to_user, list):
                # It's a list of Links or Users
                for user_ref in chat_room.to_user:
                    if isinstance(user_ref, Link):
                        user = await user_ref.fetch()
                        if user and hasattr(user, 'id'):
                            all_participants_ids.append(user.id)
                    elif hasattr(user_ref, 'id'):
                        all_participants_ids.append(user_ref.id)
            else:
                # It's a single Link or User
                if isinstance(chat_room.to_user, Link):
                    user = await chat_room.to_user.fetch()
                    if user and hasattr(user, 'id'):
                        all_participants_ids.append(user.id)
                elif hasattr(chat_room.to_user, 'id'):
                    all_participants_ids.append(chat_room.to_user.id)
            print(f"Added to_user(s): {all_participants_ids}")
        except Exception as e:
            print(f"Error processing to_user: {e}")

    # Remove duplicates and ensure we have all unique participant IDs
    all_participants_ids = list(set(all_participants_ids))
    print(f"All participants: {all_participants_ids}")
    print(f"Current user: {current_user.id}")

    # OTHER participants (excluding current user) for disconnect notifications
    other_participants_ids = [pid for pid in all_participants_ids if pid != current_user.id]
    print(f"Other participants: {other_participants_ids}")

    try:
        while True:
            message = await websocket.receive_text()

            try:
                body: dict[Any, Any] = json.loads(message)
            except json.JSONDecodeError:
                print(f"WARNING: Received non-JSON message, ignoring: '{message}'")
                continue

            try:
                action = body.get("action")
                if body.get("action") == "message":

                    if chat_room.status == RoomStatusEnum.CLOSED:
                        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

                    message_content = body.get("message", "")

                    if is_contact_info_present(message_content):
                        print(f"Message from user {current_user.id} contains contact info and is forbidden.")
                        forbidden_response = {
                            "action": "error",
                            "type": "forbidden",
                            "message": "Sending contact information is not allowed."
                        }
                        await websocket.send_text(json.dumps(forbidden_response, default=custom_encoder))
                        continue

                    saved_message = await chat_service.save_message(
                        data=body,
                        chat_room=chat_room,
                        current_user=current_user
                    )

                    # Send to room subscribers (both participants will get it in their chat room)
                    simple_payload = {
                        "action": "message",
                        "user": str(current_user.id),
                        "message": message_content,
                        "id": str(saved_message.id),
                        "created_at": str(saved_message.created_at)
                    }


                    await broadcast.publish(
                        channel=str(chat_room.id),
                        message=json.dumps(simple_payload)
                    )

                    try:
                        chat_room_data = {
                            "id": str(chat_room.id),
                            "name": chat_room.name,
                            "status": chat_room.status.value if hasattr(chat_room.status, 'value') else str(chat_room.status),
                            "listing": chat_room.listing,
                            "booking_data": chat_room.booking_data,
                            "latest_message": chat_room.latest_message,
                            "created_at": chat_room.created_at.isoformat() if chat_room.created_at else None,
                            "updated_at": chat_room.updated_at.isoformat() if chat_room.updated_at else None,
                        }

                        # Handle from_user Link
                        if chat_room.from_user:
                            if hasattr(chat_room.from_user, 'id'):
                                chat_room_data["from_user"] = str(chat_room.from_user.id)
                            else:
                                chat_room_data["from_user"] = str(chat_room.from_user)

                        # Handle to_user (can be single Link or list of Links)
                        if chat_room.to_user:
                            if isinstance(chat_room.to_user, list):
                                to_user_ids = []
                                for user_link in chat_room.to_user:
                                    if hasattr(user_link, 'id'):
                                        to_user_ids.append(str(user_link.id))
                                    else:
                                        to_user_ids.append(str(user_link))
                                chat_room_data["to_user"] = to_user_ids
                            else:
                                if hasattr(chat_room.to_user, 'id'):
                                    chat_room_data["to_user"] = [str(chat_room.to_user.id)]
                                else:
                                    chat_room_data["to_user"] = [str(chat_room.to_user)]
                        else:
                            chat_room_data["to_user"] = []

                    except Exception as room_err:
                        print(f"Error serializing chat room: {room_err}")
                        chat_room_data = {
                            "id": str(chat_room.id),
                            "name": getattr(chat_room, 'name', ''),
                            "status": str(getattr(chat_room, 'status', '')),
                            "listing": getattr(chat_room, 'listing', {}),
                            "booking_data": getattr(chat_room, 'booking_data', {}),
                            "latest_message": getattr(chat_room, 'latest_message', {}),
                            "created_at": str(getattr(chat_room, 'created_at', '')),
                            "updated_at": str(getattr(chat_room, 'updated_at', '')),
                            "from_user": str(getattr(chat_room.from_user, 'id', '')) if chat_room.from_user else None,
                            "to_user": []
                        }

                    # 2. Create user data safely
                    try:
                        user_data = {
                            "id": current_user.id,
                            "username": getattr(current_user, 'username', ''),
                            "full_name": getattr(current_user, 'full_name', ''),
                            "user_id": getattr(current_user, 'user_id', 0),
                            "email": getattr(current_user, 'email', None),
                            "image": getattr(current_user, 'image', None),
                            "phone_number": getattr(current_user, 'phone_number', None),
                            "last_online": getattr(current_user, 'last_online', None),
                            "online_status": getattr(current_user, 'online_status', False)
                        }
                        user_lite = UserLiteBase(**user_data)
                        serialized_user = user_lite.model_dump()
                    except Exception as user_err:
                        print(f"Error serializing user data: {user_err}")
                        serialized_user = {
                            "id": str(current_user.id),
                            "username": getattr(current_user, 'username', 'Unknown'),
                            "full_name": getattr(current_user, 'full_name', ''),
                            "user_id": getattr(current_user, 'user_id', 0),
                            "email": getattr(current_user, 'email', None),
                            "image": getattr(current_user, 'image', None),
                            "phone_number": getattr(current_user, 'phone_number', None),
                            "last_online": getattr(current_user, 'last_online', None),
                            "online_status": getattr(current_user, 'online_status', False)
                        }

                    # 3. Build the global room payload
                    global_room_payload = {
                        "action": "message",
                        "id": str(saved_message.id),
                        "created_at": str(saved_message.created_at),
                        "user": serialized_user,
                        "room": chat_room_data,
                        "message": message_content,
                    }

                    # 4. Convert to JSON string with custom encoder
                    message_to_broadcast = json.dumps(global_room_payload, default=custom_encoder)

                    # 5. FIXED: Broadcast to ALL participants' global rooms
                    # This ensures both host and guest get the message in their global room
                    print(f"Broadcasting to all participants: {all_participants_ids}")
                    for participant_id in all_participants_ids:
                        channel_name = f"user_global_room_{participant_id}"
                        print(f"Broadcasting to channel: {channel_name}")
                        await broadcast.publish(
                            channel=channel_name,
                            message=message_to_broadcast,
                        )

                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"chat_stat_{participant_id}",
                            message=json.dumps({"action": "update_count"})
                        )

                    for participant_id in other_participants_ids:
                        other_user = await chat_service.get_by_id(id=participant_id)
                        if not other_user: continue

                        # is_mobile_user = await Cache.get(key=f":1:user_mobile_logged_in_{other_user.username}")
                        if other_user.fcm_token:
                            fcm_title = "New Message"
                            fcm_body = "You've got a new message"
                            fcm_data = {
                                "url": (
                                    f"/host-dashboard/inbox?conversation_id={str(chat_room.id)}"
                                    if other_user.u_type == UserTypeOption.HOST
                                    else f"/messages?conversation_id={str(chat_room.id)}"
                                )
                            }
                            send_fcm_notification(other_user.fcm_token, fcm_title, fcm_body, fcm_data)


                elif body.get("action") == "is_read":
                    print(f"Marking messages as read for user {current_user.id} in room {chat_room.id}")

                    # Mark messages as read
                    await chat_service.mark_messages_as_read(
                        chat_room_id=chat_room.id, reader_id=current_user.id
                    )

                    print("Messages marked as read, broadcasting updates...")

                    # Broadcast to OTHER participants' global rooms that messages were read
                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"user_global_room_{participant_id}",
                            message=json.dumps({
                                "action": "read_done",
                                "room_id": str(chat_room.id),
                                "reader_id": str(current_user.id)
                            }),
                        )

                    # Update chat stat count for the CURRENT USER (who read the messages)
                    await broadcast.publish(
                        channel=f"chat_stat_{str(current_user.id)}",
                        message=json.dumps({"action": "update_count"})
                    )

                    # Also update other participants' chat stats in case they have shared conversations
                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"chat_stat_{participant_id}",
                            message=json.dumps({"action": "update_count"})
                        )

                elif action in ["inquiry", "confirmed"]:

                    number_of_message = 2 if action == "inquiry" else 1
                    messages, total_messages = await chat_service.get_latest_message(
                        chat_room=chat_room, number_of_message=number_of_message
                    )
                    data = {
                        "messages": [msg.model_dump() for msg in messages],
                        "action_type": action,
                        "is_new_chatroom": total_messages < number_of_message,
                    }


                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"user_global_room_{participant_id}",
                            message=json.dumps(data, default=custom_encoder),
                        )

                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"chat_stat_{participant_id}",
                            message=json.dumps({"action": "update_count"})
                        )

                else:
                    for participant_id in other_participants_ids:
                        await broadcast.publish(
                            channel=f"user_global_room_{participant_id}",
                            message=json.dumps(body),
                        )

            except Exception as err:
                print(f"ERROR processing valid JSON message: {err}")
                import traceback
                traceback.print_exc()

    except WebSocketDisconnect:
        # Notify other participants about disconnection
        for participant_id in other_participants_ids:
            await broadcast.publish(
                channel=f"user_global_room_{participant_id}",
                message=json.dumps({
                    "message": f"{current_user.username} left the chat",
                    "room_id": str(chat_room.id)
                }, default=custom_encoder),
            )


async def chatroom_ws_sender(websocket: WebSocket, room_id: str) -> None:
    async with broadcast.subscribe(channel=room_id) as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)
