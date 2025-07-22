from datetime import datetime
from typing import Optional, Union
from beanie import Document, Insert, Link, Replace, SaveChanges, Update, before_event
from pydantic import Field
from src.core.helpers.utils import get_current_datetime
from src.modules.chat.schemas import LatestMessage
from src.core.helpers.enum import ChatRoomStatus, MessageTypeEnum

from src.modules.users.models import User


class ChatRoom(Document):
    name: str
    from_user: Link[User]
    # to_user: Link[User]
    to_user: Union[Link[User], list[Link[User]]]
    status: ChatRoomStatus
    listing: dict = {}
    booking_data: dict = {}
    latest_message: LatestMessage = {}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @before_event(Insert)
    def set_created_at(self):
        self.created_at = datetime.now()

    @before_event(Update, SaveChanges, Replace)
    def set_updated_at(self):
        self.updated_at = datetime.now()


class Message(Document):
    chat_room: Link[ChatRoom]
    user: Link[User]
    m_type: MessageTypeEnum
    content: str
    meta: Optional[dict] = None
    file: Optional[str] = None
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    @before_event(Insert)
    def set_created_at(self):
        self.created_at = datetime.now()

    @before_event(Update, SaveChanges, Replace)
    def set_updated_at(self):
        self.updated_at = datetime.now()
