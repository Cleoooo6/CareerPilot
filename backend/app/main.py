"""CareerPilot FastAPI 入口。"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import is_test_auth_mode
from app.api.routes import (
    auth,
    chat,
    conversations,
    health,
    industry_pulse,
    market,
    meta,
    profile,
    roadmap,
)
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, current_request_id, request_id_ctx
from app.core.security import constant_time_equal
from app.db.pool import close_pool, open_pool
from app.schemas.common import ApiErrorDetail, ApiErrorResponse
from app.services.resume_cleanup import purge_expired_resume_files

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, secrets=(settings.llm_api_key,))
    try:
        open_pool(settings)
    except Exception:
        logger.exception("db_pool_startup_failed")
    else:
        try:
            await asyncio.to_thread(
                purge_expired_resume_files, settings.resume_ttl_hours
            )
        except Exception:
            logger.warning("resume_ttl_cleanup_failed", exc_info=True)
    yield
    close_pool()


app = FastAPI(
    title="CareerPilot AI API",
    version=get_settings().app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    token = request_id_ctx.set(request_id)
    try:
        response = _csrf_rejection(request) or await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-Id"] = request_id
    return response


def _csrf_rejection(request: Request) -> JSONResponse | None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    settings = get_settings()
    if not settings.auth_csrf_enabled or is_test_auth_mode():
        return None
    if not request.cookies.get(settings.auth_session_cookie):
        return None
    cookie_token = request.cookies.get(settings.auth_csrf_cookie)
    header_token = request.headers.get("X-CSRF-Token")
    if not constant_time_equal(cookie_token, header_token):
        return _error_response(403, "CSRF_FAILED", "CSRF 校验失败")
    return None


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ApiErrorResponse(
        error=ApiErrorDetail(code=code, message=message, details=details or {}),
        request_id=current_request_id(),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]
    return _error_response(422, "VALIDATION_ERROR", "请求参数不合法", {"errors": details})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _error_response(
        exc.status_code,
        "HTTP_ERROR",
        str(exc.detail),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_api_error")
    return _error_response(500, "INTERNAL_ERROR", "服务内部错误")


app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(industry_pulse.router, prefix="/api")
app.include_router(roadmap.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
