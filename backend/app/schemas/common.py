"""统一 API 响应结构。"""
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    ok: Literal[True] = True
    data: T
    request_id: str


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ApiErrorDetail
    request_id: str
