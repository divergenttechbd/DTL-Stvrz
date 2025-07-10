from typing import Any
from fastapi import APIRouter, Depends, Request
from src.core.helpers.enum import UserTypeOption
from src.core.helpers.decorators import permission_required
from src.core.dependencies.param import CommonParam
from src.core.schemas.common import PaginatedResponse, QueryParam
from src.core.di import Container
from src.modules.chat.service import ChatService

from src.modules.chat.schemas import ChatRoomResponse, ChatRoomMessageResponse


router = APIRouter(prefix="")


@router.get("/rooms/", response_model=PaginatedResponse[ChatRoomResponse])
@permission_required(u_type=[UserTypeOption.GUEST, UserTypeOption.HOST])
async def get_chat_rooms(
    request: Request,
    chat_service: ChatService = Depends(Container().get_chat_service),
    params: QueryParam = Depends(CommonParam(filter_fields=["name"])),
) -> Any:
    current_user = request.state.user
    return await chat_service.get_chat_rooms(
        query_param=params, current_user=current_user
    )

# @router.get("/rooms/", response_model=None) # Or just remove it
# @permission_required(u_type=[UserTypeOption.GUEST, UserTypeOption.HOST])
# async def get_chat_rooms(
#     request: Request,
#     chat_service: ChatService = Depends(Container().get_chat_service),
#     params: QueryParam = Depends(CommonParam(filter_fields=["name"])),
# ) -> Any:
#     current_user = request.state.user
#     # This will now return the raw data from the service layer
#     # without trying to fit it into PaginatedResponse[ChatRoomResponse]
#     return await chat_service.get_chat_rooms(
#         query_param=params, current_user=current_user
#     )

@router.get(
    "/rooms/{room_id}/", response_model=PaginatedResponse[ChatRoomMessageResponse]
)
@permission_required(u_type=[UserTypeOption.GUEST, UserTypeOption.HOST])
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


@router.get("/partners/", response_model=None)
@permission_required(u_type=[UserTypeOption.GUEST, UserTypeOption.HOST])
async def room_details(
    request: Request,
    chat_service: ChatService = Depends(Container().get_chat_service),
) -> Any:
    current_user = request.state.user
    return await chat_service.get_user_all_room_partner(current_user=current_user)
