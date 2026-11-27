"""认证与账号生命周期 schema。"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EmailVerificationState = Literal[
    "verified", "pending", "not_configured", "not_required"
]
DeliveryState = Literal["sent", "not_configured"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class AuthUserOut(BaseModel):
    id: UUID
    email: str | None
    display_name: str
    status: str
    email_verified: bool
    is_demo: bool = False


class AuthSessionOut(BaseModel):
    user: AuthUserOut
    csrf_token: str
    email_verification: EmailVerificationState
    session_expires_at: datetime


class AuthMessageOut(BaseModel):
    message: str
    delivery: DeliveryState | None = None


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=1, max_length=128)


class EmailVerifyRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class AccountExportOut(BaseModel):
    exported_at: datetime
    data: dict[str, Any]


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
