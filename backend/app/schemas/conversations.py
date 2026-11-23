"""会话与消息 schema。"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListOut(BaseModel):
    items: list[ConversationOut]


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class MessageListOut(BaseModel):
    conversation_id: UUID
    items: list[MessageOut]
