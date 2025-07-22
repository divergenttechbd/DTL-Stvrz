from typing import Any
from fastapi import APIRouter, Depends, Request
from src.core.helpers.enum import UserTypeOption
from src.core.helpers.decorators import permission_required
from src.core.dependencies.param import CommonParam
from src.core.schemas.common import PaginatedResponse, QueryParam
from src.core.di import Container
from src.modules.chat.service import ChatService

from src.modules.chat.schemas import (
    ChatRoomResponse,
    ChatRoomMessageResponse,
    ChatRoomStatusUpdate,
)


router = APIRouter(prefix="")


@router.get("/rooms/", response_model=PaginatedResponse[ChatRoomResponse])
@permission_required(u_type=[UserTypeOption.SYSTEM])
async def get_chat_rooms(
    request: Request,
    chat_service: ChatService = Depends(Container().get_chat_service),
    params: QueryParam = Depends(CommonParam(filter_fields=["name"])),
) -> Any:
    current_user = request.state.user
    print(current_user, " --- ")
    return await chat_service.get_chat_rooms(
        query_param=params, current_user=current_user
    )


@router.get(
    "/rooms/{room_id}/", response_model=PaginatedResponse[ChatRoomMessageResponse]
)
@permission_required(u_type=[UserTypeOption.SYSTEM])
async def room_details(
    request: Request,
    room_id: str,
    chat_service: ChatService = Depends(Container().get_chat_service),
    params: QueryParam = Depends(CommonParam(filter_fields=["name"])),
) -> Any:
    current_user = request.state.user
    return await chat_service.get_room_messages(
        current_user=current_user, room_id=room_id, query_param=params
    )


@router.patch("/rooms/{room_id}/", response_model=ChatRoomResponse)
@permission_required(u_type=[UserTypeOption.SYSTEM])
async def room_status_update(
    request: Request,
    data: ChatRoomStatusUpdate,
    room_id: str,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> Any:
    current_user = request.state.user
    return await chat_service.update_chat_room_status(
        current_user=current_user, room_id=room_id, data=data
    )
