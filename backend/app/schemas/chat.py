"""Chat 与元信息 schema。"""
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class LLMStatusOut(BaseModel):
    provider: str
    mode: str
    model: str
    base_url: str
    api_key_configured: bool
    real_calls_enabled: bool


class ToolOut(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolListOut(BaseModel):
    registered: list[ToolOut]
    planned: list[str]
