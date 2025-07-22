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
    #
    # @model_validator(mode='before')
    # @classmethod
    # def unify_to_user_field(cls, data: any) -> any:
    #
    #     if isinstance(data, dict):
    #         to_user_field = data.get('to_user')
    #         if to_user_field:
    #             if not isinstance(to_user_field, list):
    #                 data['to_user'] = [to_user_field]
    #
    #         if 'to_user' in data:
    #             data['to_user'] = data.pop('to_user')
    #     return data


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

    # @model_validator(mode="after")
    # def check_passwords_match(self):
    #     # if self.m_type == MessageTypeEnum.NORMAL:
    #     self.created_at = self.created_at + timedelta(hours=6)
    #     return self

    # @field_serializer("created_at")
    # def serialize_created_at(self, created_at: datetime, _info):
    #     return created_at + timedelta(hours=6)

    # bd_tz = pytz.timezone("Asia/Dhaka")
    # local_datetime = bd_tz.localize(created_at)
    # local_date_string = local_datetime.strftime("%Y-%m-%d %I:%M %p")

    # # Convert the local datetime to string format
    # return local_date_string


class ChatRoomMessageResponse2(BaseModel):
    data: list[ChatRoomMessageResponse]


class ChatRoomStatusUpdate(BaseModel):
    status: ChatRoomStatus
