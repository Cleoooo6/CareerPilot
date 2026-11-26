import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_context, get_user_id
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import current_request_id
from app.schemas.common import ApiResponse
from app.schemas.industry_pulse import (
    IndustryFilter,
    IndustryPulseArticleOut,
    IndustryPulseOut,
    IndustryPulseRefreshOut,
    RegionFilter,
)
from app.services.industry_pulse_service import get_industry_pulse_service
from app.services.profile_service import get_profile_service

router = APIRouter(prefix="/industry-pulse", tags=["industry-pulse"])
_refresh_lock = asyncio.Lock()
_last_refresh: float | None = None


def _service():
    return get_industry_pulse_service()


@router.get("", response_model=ApiResponse[IndustryPulseOut])
async def list_industry_pulse(
    industry: IndustryFilter = Query(default="all"),
    region: RegionFilter = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    result = await asyncio.to_thread(
        _service().list_articles,
        industry=None if industry == "all" else industry,
        region=None if region == "all" else region,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/personal", response_model=ApiResponse[IndustryPulseOut])
async def personal_industry_pulse(
    industry: IndustryFilter = Query(default="all"),
    region: RegionFilter = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_user_id),
):
    profile_service = get_profile_service()
    user_uuid = await profile_service.ensure_user_id(user_id)
    profile = await profile_service.get_profile(user_uuid)
    result = await asyncio.to_thread(
        _service().personal_articles,
        profile_data=profile["data"] if profile else None,
        industry=None if industry == "all" else industry,
        region=None if region == "all" else region,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.post("/refresh", response_model=ApiResponse[IndustryPulseRefreshOut])
async def refresh_industry_pulse(
    _: AuthContext = Depends(get_auth_context),
):
    global _last_refresh
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise AppError(
            "INDUSTRY_PULSE_REFRESH_DISABLED",
            "行业动态手动采集仅在开发/测试环境开放",
            status_code=403,
        )
    async with _refresh_lock:
        now = time.monotonic()
        if _last_refresh is not None:
            elapsed = now - _last_refresh
            if elapsed < settings.industry_pulse_refresh_cooldown:
                raise AppError(
                    "INDUSTRY_PULSE_RATE_LIMITED",
                    "采集过于频繁，请稍后再试",
                    status_code=429,
                    details={"retry_after": int(settings.industry_pulse_refresh_cooldown - elapsed)},
                )
        _last_refresh = now
        try:
            run = await asyncio.wait_for(
                _service().collect_once(),
                timeout=settings.industry_pulse_collect_timeout,
            )
        except TimeoutError as exc:
            raise AppError(
                "INDUSTRY_PULSE_TIMEOUT", "行业动态采集超时", status_code=504
            ) from exc
    return ApiResponse(data={"run": run}, request_id=current_request_id())


@router.post("/articles/{article_id}/analyze", response_model=ApiResponse[IndustryPulseArticleOut])
async def analyze_industry_article(
    article_id: UUID,
    _: AuthContext = Depends(get_auth_context),
):
    article = await asyncio.to_thread(_service().analyze_article, article_id)
    return ApiResponse(data=article, request_id=current_request_id())


def reset_refresh_guard() -> None:
    global _last_refresh
    _last_refresh = None
