"""Authentication, sessions, account lifecycle and auth audit logging."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID

from psycopg import errors as pg_errors

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ConflictError
from app.core.security import (
    dummy_password_hash,
    generate_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.db.auth_repository import AuthRepository

logger = logging.getLogger("app.auth")

EMAIL_MAX_LENGTH = 320
DISPLAY_NAME_MAX_LENGTH = 80
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
RESET_TOKEN_TTL = timedelta(hours=1)
EMAIL_VERIFY_TOKEN_TTL = timedelta(hours=24)
TOUCH_INTERVAL_SECONDS = 60

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(raw: str) -> str:
    value = (raw or "").strip().lower()
    if (
        not value
        or len(value) > EMAIL_MAX_LENGTH
        or not _EMAIL_RE.fullmatch(value)
    ):
        raise AppError("INVALID_EMAIL", "邮箱格式不正确", status_code=422)
    return value


def validate_password(password: str) -> str:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise AppError(
            "WEAK_PASSWORD",
            f"密码长度必须为 {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} 位",
            status_code=422,
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AppError("WEAK_PASSWORD", "密码必须同时包含字母和数字", status_code=422)
    return password


def normalize_display_name(raw: str | None, email: str) -> str:
    value = (raw or "").strip()
    if not value:
        value = email.split("@", 1)[0]
    if len(value) > DISPLAY_NAME_MAX_LENGTH:
        raise AppError("INVALID_DISPLAY_NAME", "昵称过长", status_code=422)
    return value


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "-"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def audit(
    event: str,
    outcome: str,
    *,
    user_id: Any = None,
    email: str | None = None,
    ip: str | None = None,
) -> None:
    logger.info(
        "auth_event",
        extra={
            "event": f"auth.{event}",
            "status": outcome,
            "user_id": str(user_id) if user_id else None,
        },
    )
    logger.info(
        "auth_audit email=%s ip=%s event=%s outcome=%s",
        mask_email(email),
        ip or "-",
        event,
        outcome,
    )


class LoginRateLimiter:
    """In-process sliding window.

    A single API container is assumed. Horizontally scaled deployments need a
    shared store (e.g. Redis) to enforce the limit across replicas.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _key(self, email: str, ip: str | None) -> str:
        return f"{email}|{ip or '-'}"

    def allow(self, email: str, ip: str | None, settings: Settings) -> bool:
        key = self._key(email, ip)
        now = datetime.now(UTC).timestamp()
        cutoff = now - settings.auth_login_window_seconds
        with self._lock:
            bucket = self._failures.get(key)
            if bucket is None:
                return True
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if not bucket:
                self._failures.pop(key, None)
                return True
            return len(bucket) < settings.auth_login_max_attempts

    def record_failure(self, email: str, ip: str | None, settings: Settings) -> None:
        key = self._key(email, ip)
        now = datetime.now(UTC).timestamp()
        cutoff = now - settings.auth_login_window_seconds
        with self._lock:
            bucket = self._failures.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)

    def reset(self, email: str, ip: str | None) -> None:
        with self._lock:
            self._failures.pop(self._key(email, ip), None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()


class AuthService:
    def __init__(
        self,
        repository: AuthRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository or AuthRepository()
        self.settings = settings or get_settings()

    @property
    def email_delivery_available(self) -> bool:
        return bool(self.settings.auth_email_configured and self.settings.auth_email_from)

    def _issue_session(
        self,
        user_id: UUID,
        *,
        user_agent: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        token = generate_token()
        csrf_token = generate_token()
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.auth_session_ttl_seconds
        )
        self.repository.create_session(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
            user_agent=(user_agent or "")[:512] or None,
            ip_address=(ip or "")[:64] or None,
        )
        return {"token": token, "csrf_token": csrf_token, "expires_at": expires_at}

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None,
        user_agent: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        validate_password(password)
        name = normalize_display_name(display_name, normalized)
        password_hash = await asyncio.to_thread(hash_password, password)
        try:
            user = await asyncio.to_thread(
                self.repository.create_user,
                email=normalized,
                password_hash=password_hash,
                display_name=name,
            )
        except pg_errors.UniqueViolation as exc:
            audit("register", "duplicate", email=normalized, ip=ip)
            raise ConflictError("该邮箱已注册") from exc

        session = self._issue_session(
            user["id"], user_agent=user_agent, ip=ip
        )
        verification = (
            "pending" if self.email_delivery_available else "not_configured"
        )
        audit("register", "success", user_id=user["id"], email=normalized, ip=ip)
        return {
            "user": user,
            "session": session,
            "email_verification": verification,
        }

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        if not login_rate_limiter.allow(normalized, ip, self.settings):
            audit("login", "rate_limited", email=normalized, ip=ip)
            raise AppError(
                "TOO_MANY_ATTEMPTS",
                "登录尝试过于频繁，请稍后再试",
                status_code=429,
            )

        user = await asyncio.to_thread(self.repository.get_by_email, normalized)
        if user is None:
            await asyncio.to_thread(verify_password, password, dummy_password_hash())
            login_rate_limiter.record_failure(normalized, ip, self.settings)
            audit("login", "invalid_credentials", email=normalized, ip=ip)
            raise AppError("INVALID_CREDENTIALS", "邮箱或密码不正确", status_code=401)

        if user.get("status") != "active":
            audit(
                "login",
                "disabled",
                user_id=user.get("id"),
                email=normalized,
                ip=ip,
            )
            raise AppError("ACCOUNT_DISABLED", "账号已被禁用", status_code=403)

        if not await asyncio.to_thread(verify_password, password, user.get("password_hash")):
            login_rate_limiter.record_failure(normalized, ip, self.settings)
            audit(
                "login",
                "invalid_credentials",
                user_id=user.get("id"),
                email=normalized,
                ip=ip,
            )
            raise AppError("INVALID_CREDENTIALS", "邮箱或密码不正确", status_code=401)

        login_rate_limiter.reset(normalized, ip)
        if needs_rehash(user.get("password_hash")):
            new_hash = await asyncio.to_thread(hash_password, password)
            await asyncio.to_thread(self.repository.set_password, user["id"], new_hash)

        session = self._issue_session(user["id"], user_agent=user_agent, ip=ip)
        audit("login", "success", user_id=user["id"], email=normalized, ip=ip)
        return {
            "user": user,
            "session": session,
            "email_verification": (
                "verified" if user.get("email_verified_at") else "pending"
            ),
        }

    async def resolve_session(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        row = await asyncio.to_thread(
            self.repository.get_session_user, hash_token(token)
        )
        if row is None:
            return None
        last_seen = row.get("last_seen_at")
        now = datetime.now(UTC)
        if last_seen is None or (now - last_seen).total_seconds() > TOUCH_INTERVAL_SECONDS:
            await asyncio.to_thread(self.repository.touch_session, row["session_id"])
        return row

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        await asyncio.to_thread(self.repository.revoke_session, hash_token(token))
        audit("logout", "success")

    async def logout_all(self, user_id: UUID) -> None:
        await asyncio.to_thread(self.repository.revoke_all_sessions, user_id)
        audit("logout_all", "success", user_id=user_id)

    async def request_password_reset(
        self, *, email: str, ip: str | None
    ) -> str:
        normalized = normalize_email(email)
        user = await asyncio.to_thread(self.repository.get_by_email, normalized)
        if user is None or user.get("status") != "active":
            audit("password_reset_request", "noop", email=normalized, ip=ip)
            return "sent"

        if not self.email_delivery_available:
            audit("password_reset_request", "not_configured", email=normalized, ip=ip)
            return "not_configured"

        token = generate_token()
        await asyncio.to_thread(
            self.repository.create_token,
            user_id=user["id"],
            purpose="password_reset",
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + RESET_TOKEN_TTL,
        )
        delivered = await self._deliver_email(
            normalized, "reset", token, "password_reset"
        )
        audit(
            "password_reset_request",
            "sent" if delivered else "delivery_failed",
            user_id=user["id"],
            email=normalized,
            ip=ip,
        )
        return "sent" if delivered else "not_configured"

    async def confirm_password_reset(
        self, *, token: str, new_password: str, ip: str | None
    ) -> None:
        validate_password(new_password)
        row = await asyncio.to_thread(
            self.repository.consume_token, hash_token(token), "password_reset"
        )
        if row is None:
            audit("password_reset_confirm", "invalid_token", ip=ip)
            raise AppError("INVALID_TOKEN", "重置链接无效或已过期", status_code=400)
        password_hash = await asyncio.to_thread(hash_password, new_password)
        await asyncio.to_thread(self.repository.set_password, row["user_id"], password_hash)
        await asyncio.to_thread(self.repository.revoke_all_sessions, row["user_id"])
        audit(
            "password_reset_confirm",
            "success",
            user_id=row["user_id"],
            ip=ip,
        )

    async def verify_email(self, *, token: str, ip: str | None) -> None:
        row = await asyncio.to_thread(
            self.repository.consume_token, hash_token(token), "email_verify"
        )
        if row is None:
            audit("email_verify", "invalid_token", ip=ip)
            raise AppError("INVALID_TOKEN", "验证链接无效或已过期", status_code=400)
        await asyncio.to_thread(self.repository.mark_email_verified, row["user_id"])
        audit("email_verify", "success", user_id=row["user_id"], ip=ip)

    async def export_account(self, user_id: UUID) -> dict[str, Any]:
        data = await asyncio.to_thread(self.repository.export_user, user_id)
        audit("account_export", "success", user_id=user_id)
        return data

    async def delete_account(
        self, *, user: dict[str, Any], password: str, ip: str | None
    ) -> int:
        user_id = user["id"]
        if not await asyncio.to_thread(
            verify_password, password, user.get("password_hash")
        ):
            audit("account_delete", "invalid_credentials", user_id=user_id, ip=ip)
            raise AppError("INVALID_CREDENTIALS", "密码不正确", status_code=401)

        files = await asyncio.to_thread(
            self.repository.resume_files_for_user, user_id
        )
        await asyncio.to_thread(self.repository.delete_user, user_id)

        from app.services.resume_service import ResumeStorage

        storage = ResumeStorage()
        removed = 0
        for name in files:
            await asyncio.to_thread(storage.delete, name)
            removed += 1
        audit("account_delete", "success", user_id=user_id, ip=ip)
        return removed

    async def _deliver_email(
        self, email: str, kind: str, token: str, purpose: str
    ) -> bool:
        # No mail provider is wired up yet. Never report a false success.
        logger.warning(
            "auth_email_delivery_unavailable kind=%s email=%s purpose=%s",
            kind,
            mask_email(email),
            purpose,
        )
        return False


_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def reset_auth_service() -> None:
    global _auth_service
    _auth_service = None
    login_rate_limiter.clear()
