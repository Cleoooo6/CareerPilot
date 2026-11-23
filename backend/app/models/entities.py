"""领域实体（仅阶段一基础设施，不代表完整职业业务模型）。"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class User(BaseModel):
    id: UUID
    external_id: str
    display_name: str
    created_at: datetime


class Conversation(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class AgentRun(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    status: str
    request_id: str
    started_at: datetime
    finished_at: datetime | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    id: UUID
    run_id: UUID
    user_id: UUID
    conversation_id: UUID
    node_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    error_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
