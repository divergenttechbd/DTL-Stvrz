from datetime import datetime, timedelta
import pytz
from typing import Optional, Union
from beanie.odm.fields import PydanticObjectId
from pydantic import BaseModel, model_validator
from src.core.helpers.enum import ChatRoomStatus, MessageTypeEnum, RoomStatusEnum

from src.modules.users.schemas import UserLiteBase


class InitializeRoom(BaseModel):
    to_user: str
    message: str


class CreateChatRoom(BaseModel):
    name: str
    from_user: PydanticObjectId
    to_user: PydanticObjectId
    message: str


class LatestMessage(BaseModel):
    content: str
    user: dict
    is_read: bool | None = None
    m_type: MessageTypeEnum
    created_at: datetime


class ChatRoomResponse(BaseModel):
    id: PydanticObjectId
    name: str
    from_user: UserLiteBase
    # to_user:  UserLiteBase
    to_user: Union[UserLiteBase, list[UserLiteBase]]
    status: ChatRoomStatus
    latest_message: LatestMessage
    booking_data: dict
    listing: dict
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ChatRoomMessageResponse(BaseModel):
    id: PydanticObjectId
    user: UserLiteBase
    content: str
    meta: Optional[dict] = None
    created_at: datetime = datetime.now()
    updated_at: Optional[datetime] = None
    is_read: bool
    file: Optional[str] = None
    m_type: MessageTypeEnum
    status: Optional[RoomStatusEnum] = None


class ChatRoomMessageResponse2(BaseModel):
    data: list[ChatRoomMessageResponse]


class ChatRoomStatusUpdate(BaseModel):
    status: ChatRoomStatus
