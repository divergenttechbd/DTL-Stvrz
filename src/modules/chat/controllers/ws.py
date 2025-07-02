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
broadcast = Broadcast("redis://192.168.7.172:6379")

router = APIRouter(prefix="/user")

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

import re

# Comprehensive email detection regex
HEAVY_EMAIL_REGEX = re.compile(
    r'''
    (                           # Start of the non-capturing outer group
        # Standard email format
        \b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b |

        # Email with spaces around @ and dots
        [A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,} |

        # Email with separators and obfuscation
        [A-Za-z0-9._%+-]+[\s\-*#]*@[\s\-*#]*[A-Za-z0-9.-]+[\s\-*#]*\.[\s\-*#]*[A-Za-z]{2,} |

        # Email with 'at' and optional 'dot'
        [A-Za-z0-9._%+-]+\s*(?:at|AT)\s*[A-Za-z0-9.-]+\s*(?:dot|DOT|\.)?\s*[A-Za-z]{2,} |

        # Email with [at] or (at) or {at} and [dot]
        [A-Za-z0-9._%+-]+\s*[\(\[\{]?(?:at|AT)[\)\]\}]?\s*[A-Za-z0-9.-]+\s*[\(\[\{]?(?:dot  |DOT|\.)[\)\]\}]?\s*[A-Za-z]{2,} |
        
        [A-Za-z0-9._%+-]+\s*(?:@|@)\s*[A-Za-z0-9.\-]+\s*(?:.|.)\s*[A-Za-z]{2,} |

        # Email with underscores/dashes around @ and .
        [A-Za-z0-9._%+-]+\s*[_\-]*\s*@\s*[_\-]*\s*[A-Za-z0-9.-]+\s*[_\-]*\s*\.\s*[_\-]*\s*[A-Za-z]{2,} |

        # Split emails
        [A-Za-z0-9._%+-]+\s+@\s+[A-Za-z0-9.-]+\s+\.\s+[A-Za-z]{2,} |


        # Partial pattern
        [A-Za-z0-9._%+-]{3,}\s*@\s*[A-Za-z0-9.-]{3,}\s*\.\s*[A-Za-z]{2,}
        
       
    )                       
    ''',
    re.VERBOSE | re.IGNORECASE
)


# Pattern for common text obfuscations
EMAIL_OBFUSCATION_REGEX = re.compile(
    r'''
    (?:
        # "at" variations
        [A-Za-z0-9._%+-]+\s*(?:at|AT|@|＠)\s*[A-Za-z0-9.\-]+\s*(?:dot|DOT|\.)\s*(?:com|org|net|edu|gov|co|io|me|info|biz|uk|us|ca|au|de|fr|jp|in|bd|[a-z]{2,4})|

        # Bracketed variations
        [A-Za-z0-9._%+-]+\s*[\(\[\{]\s*(?:at|AT)\s*[\)\]\}]\s*[A-Za-z0-9.\-]+\s*[\(\[\{]\s*(?:dot|DOT)\s*[\)\]\}]\s*[A-Za-z]{2,4}|

        # Spaced out emails
        [A-Za-z0-9._%-]+\s+@\s+[A-Za-z0-9.\-]+\s+\.\s+[A-Za-z]{2,4}|

        # Email with extra characters
        [A-Za-z0-9._%+-]+[\*\#\s]*@[\*\#\s]*[A-Za-z0-9.\-]+[\*\#\s]*\.[\*\#\s]*[A-Za-z]{2,4}
    )
    ''',
    re.VERBOSE | re.IGNORECASE
)

# Pattern for written/spelled out emails
WRITTEN_EMAIL_REGEX = re.compile(
    r'(?:email|e-mail|mail|contact)[\s\-:]*(?:is|address)?[\s\-:]*[A-Za-z0-9._%+-]+[\s\-]*(?:at|@)[\s\-]*[A-Za-z0-9.-]+[\s\-]*(?:dot|\.)[\s\-]*[A-Za-z]{2,4}',
    re.IGNORECASE
)

# Common domain patterns that might be obfuscated
DOMAIN_PATTERN_REGEX = re.compile(
    r'[A-Za-z0-9._%+-]+\s*[@at]+\s*(?:gmail|yahoo|hotmail|outlook|protonmail|icloud|aol|live|msn)\s*(?:dot|\.)?\s*(?:com|org|net|co|uk|in|bd)',
    re.IGNORECASE
)



SANITIZED_PHONE_REGEX = re.compile(
    r'^(?:\+?88)?01[3-9]\d{8}$'
)


HEAVY_PHONE_REGEX = re.compile(
    r'''
    (?:
        # Bangladesh numbers with country code variations
        (?:\+?88[\s\-\.\(\)]*)?
        (?:0?1[3-9][\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d)|

        # International format variations
        (?:\+[\s\-\.\(\)]*8[\s\-\.\(\)]*8[\s\-\.\(\)]*0?1[3-9][\s\-\.\(\)]*\d{8})|

        # Any 11-digit sequence starting with 01[3-9]
        (?:0?1[3-9][\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d[\s\-\.\(\)\*\#]*\d)|

        # Partial numbers that could be completed
        (?:(?:\+?88[\s\-\.\(\)]*)?0?1[3-9][\s\-\.\(\)\*\#]*\d{6,8})|

        # Obfuscated numbers (with letters replacing digits)
        (?:(?:\+?88[\s\-\.\(\)]*)?0?1[3-9][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl][\s\-\.\(\)OoIl]*[0-9OoIl])|

        # Written numbers (zero, one, two, etc.)
        (?:(?:zero|oh)[\s\-]*(?:one)[\s\-]*(?:three|four|five|six|seven|eight|nine)(?:[\s\-]*(?:zero|one|two|three|four|five|six|seven|eight|nine)){8})|

        # Common formats with extra characters
        (?:(?:\+?88[\s\-\.\(\)]*)?[\(\[]?0?1[3-9][\)\]]?[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d[\s\-\.\(\)]*\d)|

        # Numbers with word boundaries
        (?:\b(?:\+?88[\s\-\.\(\)]*)?0?1[3-9]\d{8}\b)|

        # Reversed or scrambled patterns
        (?:\d{8}[3-9]10?(?:88\+?)?)|

        # Any sequence that looks like a BD mobile (more permissive)
        (?:(?:\+?88)?[\s\-\.\(\)]*0?1[3456789][\s\-\.\(\)\*\#]*(?:\d[\s\-\.\(\)\*\#]*){8})
    )
    ''',
    re.VERBOSE | re.IGNORECASE
)


NUMERIC_WORD_REGEX = re.compile(
    r'(?:zero|one|two|three|four|five|six|seven|eight|nine|oh)(?:\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|oh)){10,}',
    re.IGNORECASE
)


SPACED_NUMBER_REGEX = re.compile(
    r'(?:\+?88\s*)?0?\s*1\s*[3-9](?:\s*\d){8,}',
    re.IGNORECASE
)


SEPARATOR_REGEX = re.compile(
    r'(?:\+?88)?[^\w]*0?1[3-9](?:[^\w]*\d){8}',
    re.IGNORECASE
)

def is_email_present(message: str) -> bool:
    """
    Comprehensive email detection function
    Checks for emails in multiple formats and obfuscation attempts
    """

    # Primary heavy regex check
    if HEAVY_EMAIL_REGEX.search(message):
        return True

    # Check for obfuscated emails
    if EMAIL_OBFUSCATION_REGEX.search(message):
        return True

    # Check for written/spelled out emails
    if WRITTEN_EMAIL_REGEX.search(message):
        return True

    # Check for common domain patterns
    if DOMAIN_PATTERN_REGEX.search(message):
        return True

    # Normalize common substitutions and check again
    normalized_message = message.replace('(at)', '@').replace('[at]', '@').replace('{at}', '@')
    normalized_message = normalized_message.replace('(dot)', '.').replace('[dot]', '.').replace('{dot}', '.')
    normalized_message = normalized_message.replace(' at ', '@').replace(' dot ', '.')
    normalized_message = normalized_message.replace('＠', '@')  # Full-width @

    if HEAVY_EMAIL_REGEX.search(normalized_message):
        return True

    # Check for emails with excessive spacing
    spaced_removed = re.sub(r'\s+', '', message)
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', spaced_removed):
        return True

    # Check for partial email patterns that might be intentionally broken
    partial_patterns = [
        r'[A-Za-z0-9._%+-]{3,}@[A-Za-z0-9.-]{3,}',  # Missing TLD
        r'[A-Za-z0-9._%+-]{3,}\s+@\s+[A-Za-z0-9.-]{3,}',  # Spaced @ but missing TLD
        r'@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',  # Missing username
    ]

    for pattern in partial_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True

    # Check for email-like patterns with common typos/obfuscations
    typo_patterns = [
        r'[A-Za-z0-9._%+-]+\s*[@＠]\s*g\s*m\s*a\s*i\s*l\s*[.\s]*c\s*o\s*m',  # spaced gmail
        r'[A-Za-z0-9._%+-]+\s*[@＠]\s*y\s*a\s*h\s*o\s*o\s*[.\s]*c\s*o\s*m',  # spaced yahoo
        r'[A-Za-z0-9._%+-]+\s*[@＠]\s*h\s*o\s*t\s*m\s*a\s*i\s*l\s*[.\s]*c\s*o\s*m',  # spaced hotmail
    ]

    for pattern in typo_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return True

    return False


def is_contact_info_present(message: str) -> bool:

    if is_email_present(message):
        return True

    sanitized_message = re.sub(r'[^\d+]', '', message)
    original_regex = re.compile(r'^(?:\+?88)?01[3-9]\d{8}$')
    if original_regex.search(sanitized_message):
        return True


    if HEAVY_PHONE_REGEX.search(message):
        return True


    if NUMERIC_WORD_REGEX.search(message):
        return True


    if SPACED_NUMBER_REGEX.search(message):
        return True


    if SEPARATOR_REGEX.search(message):
        return True


    letter_substituted = message.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    if HEAVY_PHONE_REGEX.search(letter_substituted):
        return True


    words = message.split()
    concatenated = ''.join(re.findall(r'\d', ' '.join(words)))
    if len(concatenated) >= 11 and re.match(r'(?:88)?01[3-9]\d{8}', concatenated):
        return True


    reversed_sanitized = sanitized_message[::-1]
    if re.search(r'\d{8}[3-9]10(?:88)?', reversed_sanitized):
        return True


    partial_matches = re.findall(r'(?:\+?88)?0?1[3-9]\d{6,}', sanitized_message)
    for match in partial_matches:
        if len(re.sub(r'[^\d]', '', match)) >= 9:  # At least 9 digits
            return True


    digit_sequences = re.findall(r'\d{9,}', sanitized_message)
    for seq in digit_sequences:
        if re.search(r'(?:88)?01[3-9]\d{8}', seq):
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
