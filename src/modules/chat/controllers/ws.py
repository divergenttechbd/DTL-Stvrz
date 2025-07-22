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
def remove_uuids_from_message(message: str) -> str:
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
    return cleaned_message


def is_phone_number_present(message: str) -> bool:
    """
    Conservative phone number detection that only catches actual phone numbers
    """
    # Remove UUIDs first
    cleaned_message = remove_uuids_from_message(message)

    # Remove JSON structure and common non-phone contexts to avoid false positives
    temp_message = cleaned_message

    # Remove entire JSON-like structures
    temp_message = re.sub(r"'[^']*':\s*\d+", "", temp_message)  # Remove 'property':1523
    temp_message = re.sub(r"'[^']*':\s*'[^']*'", "", temp_message)  # Remove 'cost':'BDT 1200/per night'
    temp_message = re.sub(r'"[^"]*":\s*\d+', "", temp_message)  # Remove "property":1523
    temp_message = re.sub(r'"[^"]*":\s*"[^"]*"', "", temp_message)  # Remove "cost":"BDT 1200/per night"

    # Remove common non-phone number patterns
    temp_message = re.sub(r'BDT\s*\d+', '', temp_message)  # Remove BDT amounts
    temp_message = re.sub(r'\d+/per\s+\w+', '', temp_message)  # Remove rates like "1200/per night"
    temp_message = re.sub(r'\d+(?:st|nd|rd|th)\s+floor', '', temp_message)  # Remove floor numbers
    temp_message = re.sub(r'https?://[^\s\'\"]+', '', temp_message)  # Remove URLs
    temp_message = re.sub(r'[a-fA-F0-9]{8,}', '', temp_message)  # Remove long hex strings

    # Only look for phone numbers with clear context or formatting
    phone_patterns = [
        # Phone numbers with clear context words
        r'(?:phone|mobile|call|contact|number|dial|reach)[\s\-:]*(?:\+?88[\s\-]*)?0?1[3-9][\s\-]*\d{8}',

        # Phone numbers with specific formatting (parentheses, clear separators)
        r'[\(\[](?:\+?88[\s\-]*)?0?1[3-9][\s\-]*\d{8}[\)\]]',

        # Phone numbers with country code clearly indicated
        r'\+88[\s\-]*0?1[3-9][\s\-]*\d{8}',

        # Phone numbers with clear separators (dashes, spaces) - must be 11 digits
        r'(?<!\d)01[3-9][\s\-]{1,2}\d{3}[\s\-]{1,2}\d{3}[\s\-]{1,2}\d{3}(?!\d)',

        # Phone numbers clearly separated by spaces or dashes
        r'(?<!\d)(?:\+?88[\s\-]+)?01[3-9](?:[\s\-]+\d){8}(?!\d)',

        # Stand-alone phone numbers at word boundaries with minimum formatting
        r'(?<!\d)(?:\+?88)?01[3-9]\d{8}(?!\d)(?=\s|$|[^\d])',
    ]

    # Check patterns on cleaned message
    for pattern in phone_patterns:
        matches = re.findall(pattern, temp_message, re.IGNORECASE)
        for match in matches:
            # Extract only digits
            digits_only = re.sub(r'[^\d]', '', match)

            # Validate Bangladesh mobile number format
            if len(digits_only) == 11 and digits_only.startswith('01') and digits_only[2] in '3456789':
                return True
            elif len(digits_only) == 13 and digits_only.startswith('88') and digits_only[2:4] == '01' and digits_only[
                4] in '3456789':
                return True

    # Check for standalone Bangladesh phone numbers in the original message
    # This catches cases like "01716990881" sent as a standalone message
    standalone_pattern = r'(?<!\d)01[3-9]\d{8}(?!\d)'
    standalone_matches = re.findall(standalone_pattern, cleaned_message)

    for match in standalone_matches:
        # Make sure it's not part of a larger number or within structured data
        # Check if it's surrounded by non-digit characters or at string boundaries
        if re.search(r'(?<!\d)' + re.escape(match) + r'(?!\d)', cleaned_message):
            # Additional check: make sure it's not within a JSON structure
            # Look for the pattern in the original context
            match_context = re.search(r'.{0,20}' + re.escape(match) + r'.{0,20}', cleaned_message)
            if match_context:
                context = match_context.group()
                # Skip if it's clearly within structured data (has quotes and colons nearby)
                if not (re.search(r'[\'"][^\'":]*' + re.escape(match) + r'[^\'":]*[\'"]', context) or
                        re.search(r'[\'"][^\'":]*:\s*' + re.escape(match), context)):
                    return True

    # Check for obvious phone sharing patterns only
    phone_sharing_patterns = [
        r'(?:my|call|phone|mobile|number|contact)[\s\w]*(?:is|:)[\s]*(?:\+?88[\s\-]*)?0?1[3-9][\s\-]*\d{8}',
        r'(?:\+?88[\s\-]*)?0?1[3-9][\s\-]*\d{8}[\s]*(?:is|call|phone|mobile|number|contact)',
    ]

    for pattern in phone_sharing_patterns:
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
    Conservative contact info detection
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
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if isinstance(obj, (ObjectId, PydanticObjectId)):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    # This will catch any other types that are not serializable
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

    # await broadcast.publish(
    #     channel=f"chat_stat_{current_user.username}",
    #     message=json.dumps({"action": "chat_stat", "user": current_user.username}),
    # )

    async with anyio.create_task_group() as task_group:

        async def run_user_chat_stat() -> None:
            await user_chat_stat(websocket=websocket, current_user=current_user)
            task_group.cancel_scope.cancel()

        task_group.start_soon(run_user_chat_stat)
        await user_chat_stat_ws_sender(
            websocket=websocket, current_user_id=str(current_user.id)
        )


async def user_chat_stat_ws_sender(websocket: WebSocket, current_user_id: str):
    async with broadcast.subscribe(
        channel=f"chat_stat_{current_user_id}"
    ) as subscriber:
        async for event in subscriber:
            await websocket.send_text(event.message)


async def user_chat_stat(websocket, current_user):
    try:
        while True:
            message = await websocket.receive_text()
            await broadcast.publish(
                channel=f"chat_stat_{current_user.id}", message=message
            )
            async for message in websocket.iter_text():
                await broadcast.publish(
                    channel=f"user_global_room_{current_user.id}", message=message
                )
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

    # Safely add the guest's ID
    if chat_room.from_user:
        all_participants_ids.append(chat_room.from_user.id)
        print(all_participants_ids)

    # Safely handle the hosts/co-hosts
    if isinstance(chat_room.to_user, list):
        for user_link in chat_room.to_user:
            user = await user_link.fetch() if isinstance(user_link, Link) else user_link
            if user:
                all_participants_ids.append(user.id)
    elif isinstance(chat_room.to_user, User):
        if chat_room.to_user:
            all_participants_ids.append(chat_room.to_user.id)

    other_participants_ids = [pid for pid in all_participants_ids if pid != current_user.id]

    print(" ================= >>> ")
    try:
        while True:
            message = await websocket.receive_text()

            try:
                body: dict[Any, Any] = json.loads(message)
            except json.JSONDecodeError:
                print(f"WARNING: Received non-JSON message, ignoring: '{message}'")
                continue

            try:
                if body.get("action") == "message":
                    saved_message = await chat_service.save_message(
                        data=body,
                        chat_room=chat_room,
                        current_user=current_user
                    )

                    simple_payload = {
                        "action": "message",
                        "user": str(current_user.id),
                        "message": body.get("message", ""),
                        "id": str(saved_message.id),
                        "created_at": str(saved_message.created_at)
                    }
                    await broadcast.publish(
                        channel=str(chat_room.id),
                        message=json.dumps(simple_payload)
                    )

                    # --- FIXED SERIALIZATION ---
                    # 1. Manually serialize chat room to avoid model_dump issues with Link lists
                    try:
                        chat_room_data = {
                            "id": str(chat_room.id),
                            "name": chat_room.name,
                            "status": chat_room.status.value if hasattr(chat_room.status, 'value') else str(
                                chat_room.status),
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
                                # It's a list of Links
                                to_user_ids = []
                                for user_link in chat_room.to_user:
                                    if hasattr(user_link, 'id'):
                                        to_user_ids.append(str(user_link.id))
                                    else:
                                        to_user_ids.append(str(user_link))
                                chat_room_data["to_user"] = to_user_ids
                            else:
                                # It's a single Link
                                if hasattr(chat_room.to_user, 'id'):
                                    chat_room_data["to_user"] = [str(chat_room.to_user.id)]
                                else:
                                    chat_room_data["to_user"] = [str(chat_room.to_user)]
                        else:
                            chat_room_data["to_user"] = []

                    except Exception as room_err:
                        print(f"Error serializing chat room: {room_err}")
                        # Fallback to basic room info
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

                    # 3. Create user data safely - manually build UserLiteBase compatible dict
                    try:
                        # Manually extract fields that UserLiteBase expects
                        user_data = {}

                        # Required fields
                        user_data["id"] = current_user.id  # Keep as PydanticObjectId, don't convert to string
                        user_data["username"] = getattr(current_user, 'username', '')
                        user_data["full_name"] = getattr(current_user, 'full_name', '')
                        user_data["user_id"] = getattr(current_user, 'user_id', 0)

                        # Optional fields
                        user_data["email"] = getattr(current_user, 'email', None)
                        user_data["image"] = getattr(current_user, 'image', None)
                        user_data["phone_number"] = getattr(current_user, 'phone_number', None)
                        user_data["last_online"] = getattr(current_user, 'last_online', None)
                        user_data["online_status"] = getattr(current_user, 'online_status', False)

                        # Create UserLiteBase instance and serialize it
                        user_lite = UserLiteBase(**user_data)
                        serialized_user = user_lite.model_dump()

                    except Exception as user_err:
                        print(f"Error serializing user data: {user_err}")
                        print(f"Current user attributes: {dir(current_user)}")
                        # Fallback to basic user info
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

                    # 4. Build the final payload using only basic Python types
                    global_room_payload = {
                        "action": "message",
                        "id": str(saved_message.id),
                        "created_at": str(saved_message.created_at),
                        "user": serialized_user,  # Use the safely serialized user
                        "room": chat_room_data,
                        "message": body.get("message"),
                    }

                    # 5. Convert to JSON string with custom encoder
                    message_to_broadcast = json.dumps(global_room_payload, default=custom_encoder)

                    # 6. Broadcast to all participants
                    all_subscribers_to_notify = [str(current_user.id)] + [str(pid) for pid in other_participants_ids]
                    for user_id in all_subscribers_to_notify:
                        await broadcast.publish(
                            channel=f"user_global_room_{user_id}",
                            message=message_to_broadcast,
                        )

                # Handle other actions here...
                # elif body.get("action") == "other_action":
                #     pass

            except Exception as err:
                print(f"ERROR processing valid JSON message: {err}")
                import traceback
                traceback.print_exc()  # This will help you debug further issues

    except WebSocketDisconnect:
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
