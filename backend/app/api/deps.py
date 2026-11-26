"""服务端会话认证依赖。

身份只能来自服务端会话。``X-User-Id`` 仅在显式测试模式
（``APP_ENV=test`` 且 ``AUTH_TEST_MODE=true``）下用于兼容隔离测试套件，
生产环境完全忽略该 header，也不再回退到 ``DEFAULT_USER_ID``。
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.db.repositories import user_repository
from app.services.auth_service import get_auth_service

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


@dataclass(frozen=True)
class AuthContext:
    user: dict[str, Any]
    token: str | None = None
    token_hash: str | None = None


def is_test_auth_mode() -> bool:
    settings = get_settings()
    return settings.app_env == "test" and settings.auth_test_mode


async def _test_context(request: Request) -> AuthContext | None:
    if not is_test_auth_mode():
        return None
    settings = get_settings()
    identifier = request.headers.get("X-User-Id")
    has_session = bool(request.cookies.get(settings.auth_session_cookie))
    if identifier is None and has_session:
        # A real cookie session always wins over the test fallback.
        return None
    if identifier is None:
        identifier = settings.default_user_id
    identifier = identifier.strip()
    if not _USER_ID_RE.fullmatch(identifier):
        raise AppError(
            "INVALID_USER_ID",
            "X-User-Id 只允许 1-64 位字母、数字、下划线、点和短横线",
            status_code=400,
        )
    user = await asyncio.to_thread(user_repository.ensure_test_user, identifier)
    return AuthContext(user=user)


async def get_auth_context(request: Request) -> AuthContext:
    test_context = await _test_context(request)
    if test_context is not None:
        return test_context

    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie)
    row = await get_auth_service().resolve_session(token)
    if row is None:
        raise AppError("UNAUTHORIZED", "请先登录", status_code=401)
    user = {key: row.get(key) for key in row if key not in {"session_id", "expires_at", "last_seen_at"}}
    return AuthContext(
        user=user,
        token=token,
        token_hash=hash_token(token) if token else None,
    )


async def get_user_id(request: Request) -> str:
    context = await get_auth_context(request)
    return str(context.user["id"])
