"""CareerPilot FastAPI 入口。"""
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import chat, conversations, health, meta
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, current_request_id, request_id_ctx
from app.db.pool import close_pool, open_pool
from app.schemas.common import ApiErrorDetail, ApiErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, secrets=(settings.llm_api_key,))
    try:
        open_pool(settings)
    except Exception:
        logger.exception("db_pool_startup_failed")
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
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-Id"] = request_id
    return response


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
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
