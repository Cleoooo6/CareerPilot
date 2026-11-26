"""认证 API：注册、登录、退出、会话、密码重置与账号生命周期。"""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import AuthContext, get_auth_context
from app.core.config import get_settings
from app.core.logging import current_request_id
from app.schemas.auth import (
    AccountDeleteRequest,
    AccountExportOut,
    AuthMessageOut,
    AuthSessionOut,
    AuthUserOut,
    EmailVerifyRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
)
from app.schemas.common import ApiResponse
from app.services.auth_service import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def _user_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")


def _set_auth_cookies(response: Response, session: dict[str, Any]) -> None:
    settings = get_settings()
    max_age = settings.auth_session_ttl_seconds
    response.set_cookie(
        settings.auth_session_cookie,
        session["token"],
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.auth_csrf_cookie,
        session["csrf_token"],
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (settings.auth_session_cookie, settings.auth_csrf_cookie):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.auth_cookie_secure,
            samesite="lax",
        )


def _user_out(user: dict[str, Any]) -> AuthUserOut:
    return AuthUserOut(
        id=user["id"],
        email=user.get("email"),
        display_name=user.get("display_name") or "",
        status=user.get("status") or "active",
        email_verified=bool(user.get("email_verified_at")),
        is_demo=bool(user.get("is_demo")),
    )


@router.post(
    "/register",
    response_model=ApiResponse[AuthSessionOut],
    status_code=201,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> ApiResponse[AuthSessionOut]:
    result = await get_auth_service().register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        user_agent=_user_agent(request),
        ip=_client_ip(request),
    )
    session = result["session"]
    _set_auth_cookies(response, session)
    return ApiResponse(
        data=AuthSessionOut(
            user=_user_out(result["user"]),
            csrf_token=session["csrf_token"],
            email_verification=result["email_verification"],
            session_expires_at=session["expires_at"],
        ),
        request_id=current_request_id(),
    )


@router.post("/login", response_model=ApiResponse[AuthSessionOut])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> ApiResponse[AuthSessionOut]:
    result = await get_auth_service().login(
        email=payload.email,
        password=payload.password,
        user_agent=_user_agent(request),
        ip=_client_ip(request),
    )
    session = result["session"]
    _set_auth_cookies(response, session)
    return ApiResponse(
        data=AuthSessionOut(
            user=_user_out(result["user"]),
            csrf_token=session["csrf_token"],
            email_verification=result["email_verification"],
            session_expires_at=session["expires_at"],
        ),
        request_id=current_request_id(),
    )


@router.post("/logout", response_model=ApiResponse[AuthMessageOut])
async def logout(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
) -> ApiResponse[AuthMessageOut]:
    await get_auth_service().logout(context.token)
    _clear_auth_cookies(response)
    return ApiResponse(
        data=AuthMessageOut(message="已退出登录"),
        request_id=current_request_id(),
    )


@router.post("/logout-all", response_model=ApiResponse[AuthMessageOut])
async def logout_all(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
) -> ApiResponse[AuthMessageOut]:
    await get_auth_service().logout_all(context.user["id"])
    _clear_auth_cookies(response)
    return ApiResponse(
        data=AuthMessageOut(message="已撤销全部会话"),
        request_id=current_request_id(),
    )


@router.get("/me", response_model=ApiResponse[AuthUserOut])
async def me(
    context: AuthContext = Depends(get_auth_context),
) -> ApiResponse[AuthUserOut]:
    return ApiResponse(
        data=_user_out(context.user),
        request_id=current_request_id(),
    )


@router.post(
    "/password-reset/request",
    response_model=ApiResponse[AuthMessageOut],
)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
) -> ApiResponse[AuthMessageOut]:
    delivery = await get_auth_service().request_password_reset(
        email=payload.email,
        ip=_client_ip(request),
    )
    return ApiResponse(
        data=AuthMessageOut(
            message="如果该邮箱已注册，我们会发送重置说明",
            delivery="sent" if delivery == "sent" else "not_configured",
        ),
        request_id=current_request_id(),
    )


@router.post(
    "/password-reset/confirm",
    response_model=ApiResponse[AuthMessageOut],
)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
) -> ApiResponse[AuthMessageOut]:
    await get_auth_service().confirm_password_reset(
        token=payload.token,
        new_password=payload.new_password,
        ip=_client_ip(request),
    )
    return ApiResponse(
        data=AuthMessageOut(message="密码已重置，请重新登录"),
        request_id=current_request_id(),
    )


@router.post("/email/verify", response_model=ApiResponse[AuthMessageOut])
async def verify_email(
    payload: EmailVerifyRequest,
    request: Request,
) -> ApiResponse[AuthMessageOut]:
    await get_auth_service().verify_email(
        token=payload.token,
        ip=_client_ip(request),
    )
    return ApiResponse(
        data=AuthMessageOut(message="邮箱已验证"),
        request_id=current_request_id(),
    )


@router.get("/export", response_model=ApiResponse[AccountExportOut])
async def export_account(
    context: AuthContext = Depends(get_auth_context),
) -> ApiResponse[AccountExportOut]:
    data = await get_auth_service().export_account(context.user["id"])
    return ApiResponse(
        data=AccountExportOut(exported_at=datetime.now(UTC), data=data),
        request_id=current_request_id(),
    )


@router.delete("/account", response_model=ApiResponse[AuthMessageOut])
async def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
) -> ApiResponse[AuthMessageOut]:
    await get_auth_service().delete_account(
        user=context.user,
        password=payload.password,
        ip=None,
    )
    _clear_auth_cookies(response)
    return ApiResponse(
        data=AuthMessageOut(message="账号及个人数据已删除"),
        request_id=current_request_id(),
    )
