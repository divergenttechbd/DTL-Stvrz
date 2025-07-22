from datetime import datetime
from beanie import PydanticObjectId, Link
from beanie.odm.operators.find.comparison import In
from beanie.odm.operators.find.logical import Or
from fastapi import HTTPException
import pymongo
from src.modules.chat.schemas import (
    ChatRoomMessageResponse,
    ChatRoomResponse,
    ChatRoomStatusUpdate,
)
from src.core.helpers.enum import ChatRoomStatus, RoomStatusEnum, UserTypeOption
from src.core.helpers.utils import paginateResponse
from src.core.schemas.common import PaginatedResponse, QueryParam
from src.modules.chat.repository import ChatRepository
from src.modules.users.models import User
from src.modules.chat.models import ChatRoom, Message
from src.core.service import BaseService
from src.core.logging import logger
from bson import DBRef

class ChatService(BaseService):
    def __init__(self, chat_repository: ChatRepository):
        super().__init__(repository=chat_repository)

    async def _resolve_user_links(self, user_field):
        """Helper method to resolve Link[User] objects to actual User data"""
        if isinstance(user_field, Link):
            # Fetch the actual user object
            resolved_user = await user_field.fetch()
            return resolved_user.model_dump() if resolved_user else None
        elif isinstance(user_field, list):
            resolved_users = []
            for user_link in user_field:
                if isinstance(user_link, Link):
                    resolved_user = await user_link.fetch()
                    if resolved_user:
                        resolved_users.append(resolved_user.model_dump())
                else:
                    # Already resolved
                    resolved_users.append(user_link.model_dump() if hasattr(user_link, 'model_dump') else user_link)
            return resolved_users
        else:
            # Already resolved or None
            return user_field.model_dump() if hasattr(user_field, 'model_dump') else user_field

    async def check_user_has_room_permission(
        self, room_id: str, current_user: User
    ) -> tuple[ChatRoom | None, bool]:
        chat_room = await self.repository.get_by_id(model=ChatRoom, id=room_id)

        if not chat_room:
            return None, False

        # Resolve from_user Link
        from_user = await chat_room.from_user.fetch() if isinstance(chat_room.from_user, Link) else chat_room.from_user

        # Check if current user is the from_user
        is_participant = False
        if from_user and current_user.id == from_user.id:
            is_participant = True
        elif isinstance(chat_room.to_user, list):
            # New group chat: check if user is in the list of hosts
            for user_link in chat_room.to_user:
                user = await user_link.fetch() if isinstance(user_link, Link) else user_link
                if user and current_user.id == user.id:
                    is_participant = True
                    break
        elif isinstance(chat_room.to_user, Link):
            # Old 1-to-1 chat: check if user is the single host
            to_user = await chat_room.to_user.fetch()
            if to_user and current_user.id == to_user.id:
                is_participant = True

        if not is_participant:
            return None, False

        return chat_room, True

    async def get_room_messages(
        self, current_user: User, room_id: str, query_param: QueryParam
    ) -> PaginatedResponse[Message]:

        chat_room, has_access = await self.check_user_has_room_permission(room_id, current_user)

        if not has_access:
            raise HTTPException(status_code=403, detail="You are not a member of this chat room")

        messages, count = await self.repository.get_room_messages(
            room_id=chat_room.id, query_param=query_param
        )
        user_unread_message_count = await self.repository.count_user_unread_message(
            user_id=current_user.id, u_type=current_user.u_type
        )

        # Properly resolve Links before creating ChatRoomResponse
        try:
            resolved_from_user = await self._resolve_user_links(chat_room.from_user)
            resolved_to_user = await self._resolve_user_links(chat_room.to_user)

            chat_room_data = {
                "id": chat_room.id,
                "name": chat_room.name,
                "from_user": resolved_from_user,
                "to_user": resolved_to_user,
                "status": chat_room.status,
                "latest_message": chat_room.latest_message,
                "booking_data": chat_room.booking_data,
                "listing": chat_room.listing,
                "created_at": chat_room.created_at,
                "updated_at": chat_room.updated_at,
            }

            return paginateResponse(
                data=messages,
                total=count,
                page=query_param.page,
                limit=query_param.offset_limit,
                extra_data={
                    "chat_room": ChatRoomResponse(**chat_room_data),
                    "unread_message_count": user_unread_message_count,
                },
            )
        except Exception as e:
            logger.error(f"Error resolving chat room data: {str(e)}")
            raise HTTPException(status_code=500, detail="Error processing chat room data")

    async def get_chat_rooms(
        self, query_param: QueryParam, current_user: User
    ) -> PaginatedResponse[ChatRoomResponse]:

        user_obj_id = PydanticObjectId(current_user.id)

        if current_user.u_type == UserTypeOption.GUEST:
            filter_expression = (ChatRoom.from_user.id == user_obj_id,)
        elif current_user.u_type == UserTypeOption.HOST:
            filter_expression = {
                "$or": [
                    {"to_user": DBRef("User", user_obj_id)},
                    {"to_user": {"$elemMatch": {"$id": user_obj_id}}}
                ]
            }
        elif current_user.u_type == UserTypeOption.SYSTEM:
            filter_expression = {}
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")

        sorting = [(ChatRoom.updated_at, pymongo.DESCENDING)]

        chat_rooms, count = await self.repository.get_chat_rooms(
            param=query_param, filter_param=filter_expression, sorting=sorting
        )

        # Resolve all Links properly before serialization
        serialized_chat_rooms = []
        for room in chat_rooms:
            try:
                # Resolve Links
                resolved_from_user = await self._resolve_user_links(room.from_user)
                resolved_to_user = await self._resolve_user_links(room.to_user)

                room_data = {
                    "id": room.id,
                    "name": room.name,
                    "from_user": resolved_from_user,
                    "to_user": resolved_to_user,
                    "status": room.status,
                    "latest_message": room.latest_message,
                    "booking_data": room.booking_data,
                    "listing": room.listing,
                    "created_at": room.created_at,
                    "updated_at": room.updated_at,
                }

                # Validate with Pydantic model
                chat_room_response = ChatRoomResponse(**room_data)
                serialized_chat_rooms.append(chat_room_response.model_dump())

            except Exception as e:
                logger.error(f"Error serializing chat room {room.id}: {str(e)}")
                # Skip problematic rooms rather than failing entirely
                continue

        filter_param = (Message.user.id == PydanticObjectId(current_user.id),)
        all_message_count = await self.repository.count_user_all_message(
            filter_param=filter_param
        )

        return paginateResponse(
            data=serialized_chat_rooms,
            total=count,
            page=query_param.page,
            limit=query_param.offset_limit,
            extra_data={"all_message_count": all_message_count},
        )

    async def update_chat_room_message(self, chat_room: ChatRoom, other_user_id: PydanticObjectId) -> None:
        await self.repository.update_chat_message(chat_room=chat_room, other_user_id=other_user_id)
        return None

    async def save_message(self, data: dict, chat_room: ChatRoom, current_user: User) -> Message:
        formatted_data = {"chat_room": chat_room.id, "user": current_user.id, "content": data.get("message", ""),
                          "file": data.get("file"), "m_type": "normal"}
        chat_room_update_data = {
            "latest_message": {"content": data.get("message", ""), "created_at": datetime.now(),
                               "user": {"username": current_user.username, "full_name": current_user.full_name,
                                        "image": current_user.image, "user_id": current_user.user_id, },
                               "m_type": "normal", "is_read": False, },
            "booking_data": chat_room.booking_data, "listing": chat_room.listing, "status": chat_room.status,
        }
        saved_message = await self.repository.create_message(data=formatted_data,
                                                             chat_room_update_data=chat_room_update_data,
                                                             chat_room=chat_room)
        return saved_message

    async def update_chat_room_status(self, current_user: User, room_id: str,
                                      data: ChatRoomStatusUpdate) -> ChatRoomResponse:
        chat_room = await self.repository.get_by_id(model=ChatRoom, id=room_id)
        if not chat_room:
            raise HTTPException(status_code=400, detail="Room does not exists")
        return await self.repository.update_chat_room_status(current_user=current_user, chat_room=chat_room,
                                                             status=data.status)

    async def get_latest_message(self, chat_room: ChatRoom, number_of_message: int) -> tuple[list[Message], int]:
        return await self.repository.get_latest_message(chat_room=chat_room, number_of_message=number_of_message)

    async def get_user_all_room_partner(self, current_user: User) -> list:
        user_obj_id = PydanticObjectId(current_user.id)

        if current_user.u_type == UserTypeOption.GUEST:
            filter_expression = (ChatRoom.from_user.id == user_obj_id,)
        elif current_user.u_type == UserTypeOption.HOST:
            filter_expression = (Or(ChatRoom.to_user.id == user_obj_id, In(ChatRoom.to_user.id, [user_obj_id])),)
        else:
            filter_expression = {}

        data = await self.repository.get_user_all_room(filter_param=filter_expression)

        partner_ids = set()
        for item in data:
            # Resolve from_user Link
            from_user = await item.from_user.fetch() if isinstance(item.from_user, Link) else item.from_user

            if from_user and current_user.id == from_user.id:
                # Current user is the guest. Partners are all hosts.
                if isinstance(item.to_user, list):
                    for host_link in item.to_user:
                        host = await host_link.fetch() if isinstance(host_link, Link) else host_link
                        if host:
                            partner_ids.add(host.id)
                elif isinstance(item.to_user, Link):
                    host = await item.to_user.fetch()
                    if host:
                        partner_ids.add(host.id)
            else:
                # Current user is a host. Partner is the guest.
                if from_user:
                    partner_ids.add(from_user.id)

        return list(partner_ids)

    async def update_user_last_seen(self, current_user: User, online_status: bool) -> None:
        return await self.repository.update_user_last_seen(current_user=current_user, online_status=online_status)

    async def get_user_unread_message_count(self, user_id: str, u_type: UserTypeOption) -> int:
        return await self.repository.count_user_unread_message(user_id=user_id, u_type=u_type)

    async def get_by_id(self, id: str) -> User | None:
        return await self.repository.get_by_id(model=User, id=id)
