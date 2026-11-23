"""Chat SSE 端点。"""
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_user_id
from app.api.sse import encode_sse
from app.core.logging import current_request_id
from app.schemas.chat import ChatRequest
from app.services.chat_service import get_chat_service

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: UUID,
    payload: ChatRequest,
    user_id: str = Depends(get_user_id),
):
    service = get_chat_service()
    await service.get_conversation(user_id, conversation_id)
    request_id = current_request_id()

    async def event_stream():
        async for event in service.stream_turn(
            user_external_id=user_id,
            conversation_id=conversation_id,
            content=payload.content,
            request_id=request_id,
        ):
            yield encode_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-Id": request_id,
        },
    )
