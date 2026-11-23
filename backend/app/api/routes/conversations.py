"""会话与消息 API。"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_user_id
from app.core.logging import current_request_id
from app.schemas.common import ApiResponse
from app.schemas.conversations import (
    ConversationCreateRequest,
    ConversationListOut,
    ConversationOut,
    MessageListOut,
    MessageOut,
)
from app.services.chat_service import get_chat_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ApiResponse[ConversationOut], status_code=201)
async def create_conversation(
    payload: ConversationCreateRequest,
    user_id: str = Depends(get_user_id),
) -> ApiResponse[ConversationOut]:
    row = await get_chat_service().create_conversation(user_id, payload.title)
    return ApiResponse(
        data=ConversationOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.get("", response_model=ApiResponse[ConversationListOut])
async def list_conversations(
    user_id: str = Depends(get_user_id),
) -> ApiResponse[ConversationListOut]:
    rows = await get_chat_service().list_conversations(user_id)
    return ApiResponse(
        data=ConversationListOut(
            items=[ConversationOut.model_validate(row) for row in rows]
        ),
        request_id=current_request_id(),
    )


@router.get("/{conversation_id}", response_model=ApiResponse[ConversationOut])
async def get_conversation(
    conversation_id: UUID,
    user_id: str = Depends(get_user_id),
) -> ApiResponse[ConversationOut]:
    row = await get_chat_service().get_conversation(user_id, conversation_id)
    return ApiResponse(
        data=ConversationOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[MessageListOut],
)
async def list_messages(
    conversation_id: UUID,
    user_id: str = Depends(get_user_id),
) -> ApiResponse[MessageListOut]:
    rows = await get_chat_service().list_messages(user_id, conversation_id)
    return ApiResponse(
        data=MessageListOut(
            conversation_id=conversation_id,
            items=[MessageOut.model_validate(row) for row in rows],
        ),
        request_id=current_request_id(),
    )
