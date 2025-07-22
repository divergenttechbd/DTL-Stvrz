from datetime import datetime
from beanie import PydanticObjectId, Link
import beanie
from beanie.odm.operators.find.comparison import In
from bson import ObjectId
import pymongo
from beanie.odm.operators.find.logical import Or
from fastapi import HTTPException
from src.modules.chat.schemas import (
    ChatRoomMessageResponse,
    ChatRoomResponse,
    ChatRoomStatusUpdate,
)
from src.core.helpers.enum import ChatRoomStatus, RoomStatusEnum, UserTypeOption
from src.modules.users.models import User
from src.core.schemas.common import QueryParam
from src.core.repository.base_repository import BaseRepository
from src.modules.chat.models import ChatRoom, Message


class ChatRepository(BaseRepository):

    async def get_chat_rooms(
        self,
        param: QueryParam,
        filter_param: dict | tuple = {},
        sorting: list = [],
    ) -> tuple[list[ChatRoom], int]:
        offset = (param.page - 1) * param.offset_limit
        limit = param.limit

        if isinstance(filter_param, dict):
            # If it's a raw dictionary, pass it directly without unpacking.
            query = ChatRoom.find(filter_param, fetch_links=True)
            count_query = ChatRoom.find(filter_param)
        else:
            # Otherwise, assume it's a tuple/list of Beanie expressions and unpack it.
            query = ChatRoom.find(*filter_param, fetch_links=True)
            count_query = ChatRoom.find(*filter_param)

        data = await query.sort(sorting).skip(offset).limit(limit).to_list()
        total_count = await count_query.count()
        return data, total_count

    async def get_room_messages(
        self, room_id: str, query_param: QueryParam
    ) -> tuple[list[Message], int]:
        try:
            offset = (query_param.page - 1) * query_param.offset_limit
            limit = query_param.limit
            data = await Message.find(
                Message.chat_room.id == room_id,
                limit=limit,
                skip=offset,
                fetch_links=True,
            ).to_list()

            count = await Message.find(
                Message.chat_room.id == room_id,
            ).count()
            return data, count
        except (ValueError, beanie.exceptions.DocumentNotFound):
            raise HTTPException(status_code=400, detail="Not found")

    async def update_chat_message(
        self, chat_room: ChatRoom, other_user_id: PydanticObjectId
    ) -> None:
        try:
            await Message.find(
                Message.chat_room.id == chat_room.id, Message.user.id == other_user_id
            ).update({"$set": {Message.is_read: True}})

            await chat_room.set(
                {
                    ChatRoom.latest_message.is_read: True,
                }
            )
            return None
        except Exception as err:
            print(err)

    async def create_message(
        self, data: dict, chat_room_update_data: dict, chat_room=ChatRoom
    ) -> Message:
        created_object = Message(**data)  # type: ignore
        created_message = await created_object.create()
        await chat_room.set(
            {
                ChatRoom.latest_message: chat_room_update_data.get("latest_message"),
                ChatRoom.created_at: datetime.now(),
                ChatRoom.updated_at: datetime.now(),
                # ChatRoom.booking_data: chat_room_update_data.get("booking_data"),
                # ChatRoom.listing: chat_room_update_data.get("listing"),
            }
        )
        return created_message

    async def update_chat_room_status(
        self, current_user: User, chat_room: ChatRoom, status: ChatRoomStatusUpdate
    ) -> ChatRoomResponse:
        created_object = Message(
            chat_room=chat_room.id,
            content=(
                f"Room is closed"
                if status == ChatRoomStatus.CLOSED
                else "Room is Open by admin"
            ),
            user=current_user.id,
            m_type="system",
            meta=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await created_object.create()
        await chat_room.set(
            {
                ChatRoom.status: status,
                ChatRoom.updated_at: datetime.now(),
                ChatRoom.latest_message: created_object.model_dump(),
            }
        )

        return chat_room

    async def get_latest_message(
        self, chat_room: ChatRoom, number_of_message: int
    ) -> tuple[list[Message], int]:
        messages = (
            await Message.find(
                Message.chat_room.id == chat_room.id,
                limit=number_of_message,
                fetch_links=True,
            )
            .sort(
                [
                    (ChatRoom.updated_at, pymongo.DESCENDING),
                ]
            )
            .to_list()
        )

        total_message = await Message.find(
            Message.chat_room.id == chat_room.id,
        ).count()

        return messages, total_message

    async def get_user_all_room(
        self,
        filter_param: dict | tuple = {},
    ) -> list[ChatRoom]:
        return await ChatRoom.find(*filter_param).to_list()

    async def update_user_last_seen(
        self,
        current_user: User,
        online_status: bool,
    ) -> None:
        if online_status:
            update_query = {User.online_status: online_status}
        else:
            update_query = {
                User.last_online: datetime.now(),
                User.online_status: online_status,
            }
        await current_user.set(update_query)

    async def count_user_all_message(
        self,
        filter_param: dict | tuple = {},
    ) -> int:
        return await Message.find(*filter_param).count()

    async def count_user_unread_message(
        self, user_id: str, u_type: UserTypeOption, is_read: bool = False
    ) -> int:
        user_obj_id = PydanticObjectId(user_id)

        # Reuse the backward-compatible filter from the service layer
        if u_type == UserTypeOption.GUEST:
            filter_expression = (ChatRoom.from_user.id == user_obj_id,)
        else:  # HOST
            filter_expression = (
                Or(
                    ChatRoom.to_user.id == user_obj_id,
                    In(ChatRoom.to_user.id, [user_obj_id])
                ),
            )

        user_all_chat_room = await ChatRoom.find(*filter_expression, fetch_links=True).to_list()

        total_unread_msg_count = 0
        for room in user_all_chat_room:
            other_user_ids = []
            # --- BACKWARD-COMPATIBLE LOGIC ---
            # Determine who the "other" users are based on the room structure
            if room.from_user.id == user_obj_id:  # If current user is the guest
                if isinstance(room.to_user, list):
                    other_user_ids.extend([host.id for host in room.to_user])
                elif isinstance(room.to_user, Link):
                    other_user_ids.append(room.to_user.id)
            else:  # If current user is a host
                other_user_ids.append(room.from_user.id)
            # --- END ---

            if not other_user_ids:
                continue

            # Count unread messages sent by any of the "other" users in this room
            individual_chat_room_msg_count = await Message.find(
                Message.chat_room.id == room.id,
                In(Message.user.id, other_user_ids),
                Message.is_read == False,
            ).count()

            if individual_chat_room_msg_count > 0:
                total_unread_msg_count += 1

        return total_unread_msg_count
