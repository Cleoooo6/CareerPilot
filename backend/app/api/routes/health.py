"""健康检查与就绪检查。"""
from fastapi import APIRouter

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import current_request_id
from app.db.pool import check_database
from app.schemas.common import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
def health() -> ApiResponse[dict[str, str]]:
    settings = get_settings()
    return ApiResponse(
        data={
            "status": "ok",
            "service": "careerpilot-api",
            "version": settings.app_version,
        },
        request_id=current_request_id(),
    )


@router.get("/ready", response_model=ApiResponse[dict[str, str]])
def ready() -> ApiResponse[dict[str, str]]:
    if not check_database():
        raise AppError(
            "NOT_READY",
            "数据库未就绪或迁移未应用",
            status_code=503,
        )
    return ApiResponse(
        data={"status": "ready", "database": "ok"},
        request_id=current_request_id(),
    )
