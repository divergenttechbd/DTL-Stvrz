import json
from typing import Any
import anyio
from beanie import PydanticObjectId
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
    if isinstance(obj, (ObjectId, PydanticObjectId)):
        return str(obj)
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@router.websocket("/user-global-room/")
async def websocket_user_global_room_endpoint(
    websocket: WebSocket,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> None:
    await websocket.accept()
    current_user = websocket.state.user

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
            message = await websocket.receive_text()
            await broadcast.publish(
                channel=f"user_global_room_{current_user.id}", message=message
            )
            # async for message in websocket.iter_text():
            #     await broadcast.publish(
            #         channel=f"user_global_room_{current_user_id}", message=message
            #     )
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

    async with anyio.create_task_group() as task_group:

        async def run_chatroom_ws_receiver() -> None:
            await chatroom_ws_receiver(
                websocket=websocket,
                current_user=websocket.state.user,
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
    try:
        while True:
            message = await websocket.receive_text()
            try:
                body: dict[Any, Any] = json.loads(message)
                other_user_id = (
                    chat_room.from_user.id
                    if current_user.id == chat_room.to_user.id
                    else chat_room.to_user.id
                )
                other_user_type = (
                    UserTypeOption.GUEST
                    if current_user.u_type == UserTypeOption.HOST
                    else UserTypeOption.HOST
                )
                if body["action"] == "message":
                    # body["user"] = current_user.id

                    user_message_content = body.get("message", "")
                    if is_contact_info_present(user_message_content):
                        print(" ----------------- ")
                        error_payload = {
                            "action": "error",
                            "type": "forbidden_content",
                            "detail": "Sharing contact information (email or phone number) is not allowed."
                        }
                        await websocket.send_text(json.dumps(error_payload))
                        continue

                    if chat_room.status == RoomStatusEnum.CLOSED:
                        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

                    saved_message = await chat_service.save_message(
                        data=body, chat_room=chat_room, current_user=current_user
                    )
                    body["user"] = str(current_user.id)
                    await broadcast.publish(
                        channel=str(chat_room.id), message=json.dumps(body)
                    )

                    chat_room_dict = ChatRoomResponse(
                        **chat_room.model_dump()
                    ).model_dump()
                    body["room"] = chat_room_dict
                    body["user"] = UserLiteBase(
                        **current_user.model_dump()
                    ).model_dump()
                    body["id"] = str(saved_message.id)
                    body["created_at"] = str(saved_message.created_at)
                    # str(
                    #     saved_message.created_at + timedelta(hours=6)
                    # )
                    await broadcast.publish(
                        channel=f"user_global_room_{other_user_id}",
                        message=json.dumps(body, default=custom_encoder),
                    )
                    await broadcast.publish(
                        channel=f"user_global_room_{str(current_user.id)}",
                        message=json.dumps(body, default=custom_encoder),
                    )

                    await broadcast.publish(
                        channel=f"chat_stat_{str(other_user_id)}",
                        message=json.dumps(
                            {
                                "count": await chat_service.get_user_unread_message_count(
                                    user_id=other_user_id, u_type=other_user_type
                                )
                            }
                        ),
                    )

                    chat_room_other_user = await chat_service.get_by_id(
                        id=other_user_id
                    )

                    if (
                        chat_room_other_user.fcm_token
                        and not chat_room_other_user.online_status
                        and await Cache.get(
                            key=f":1:user_mobile_logged_in_{chat_room_other_user.username}"
                        )
                    ):
                        fcm_title = "New Message"
                        fcm_body = "You've got a new message"
                        fcm_data = {
                            "key1": "value1",
                            "url": (
                                f"/host-dashboard/inbox?conversation_id={str(chat_room.id)}"
                                if chat_room_other_user.u_type == UserTypeOption.HOST
                                else f"/messages?conversation_id={str(chat_room.id)}"
                            ),
                        }
                        send_fcm_notification(
                            chat_room_other_user.fcm_token,
                            fcm_title,
                            fcm_body,
                            fcm_data,
                        )

                elif body["action"] == "is_read":
                    await chat_service.update_chat_room_message(
                        chat_room=chat_room, other_user_id=other_user_id
                    )
                    await broadcast.publish(
                        channel=f"user_global_room_{other_user_id}",
                        message=json.dumps(
                            {"action": "read_done", "room_id": str(chat_room.id)}
                        ),
                    )

                    await broadcast.publish(
                        channel=f"chat_stat_{str(current_user.id)}",
                        message=json.dumps(
                            {
                                "count": await chat_service.get_user_unread_message_count(
                                    user_id=current_user.id, u_type=current_user.u_type
                                )
                            }
                        ),
                    )
                elif body["action"] in ["inquiry", "confirmed"]:
                    number_of_message = 2 if body["action"] == "inquiry" else 1

                    (
                        messages,
                        total_messages,
                    ) = await chat_service.get_latest_message(
                        chat_room=chat_room, number_of_message=number_of_message
                    )
                    data = {
                        "messages": messages,
                        "action_type": body["action"],
                        "is_new_chatroom": total_messages < number_of_message,
                    }
                    await broadcast.publish(
                        channel=f"user_global_room_{other_user_id}",
                        message=json.dumps(
                            data,
                            default=custom_encoder,
                        ),
                    )
                    await broadcast.publish(
                        channel=f"chat_stat_{str(other_user_id)}",
                        message=json.dumps(
                            {
                                "count": await chat_service.get_user_unread_message_count(
                                    user_id=other_user_id, u_type=other_user_type
                                )
                            }
                        ),
                    )
                else:
                    await broadcast.publish(
                        channel=f"user_global_room_{other_user_id}",
                        message=json.dumps(body),
                    )
            except Exception as err:
                print(err, "-")
    except WebSocketDisconnect:
        await broadcast.publish(
            channel=f"user_global_room_{other_user_id}",
            message=json.dumps(
                {"message": f"{current_user.username} leave the chat"},
                default=custom_encoder,
            ),
        )


async def chatroom_ws_sender(websocket: WebSocket, room_id: str) -> None:
    async with broadcast.subscribe(channel=room_id) as subscriber:
        async for event in subscriber:  # type: ignore
            await websocket.send_text(event.message)
