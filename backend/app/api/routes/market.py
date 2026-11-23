import asyncio
from typing import Literal

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import current_request_id
from app.schemas.common import ApiResponse
from app.schemas.market import (
    DistributionOut,
    MarketImportRequest,
    MarketImportResult,
    MarketOverviewOut,
    RolesOut,
    SkillDemandOut,
    SourcesOut,
    TrendOut,
)
from app.services.market_service import get_market_service

router = APIRouter(prefix="/market", tags=["market"])
DatasetKind = Literal["all", "real", "synthetic"]


def _service():
    return get_market_service()


@router.post("/import", response_model=ApiResponse[MarketImportResult])
async def import_market_data(payload: MarketImportRequest):
    if get_settings().app_env not in {"development", "test"}:
        raise AppError(
            "MARKET_IMPORT_DISABLED",
            "市场数据导入仅在开发/测试环境开放",
            status_code=403,
        )
    result = await asyncio.to_thread(_service().import_jobs, payload)
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/sources", response_model=ApiResponse[SourcesOut])
async def list_market_sources():
    result = await asyncio.to_thread(_service().sources)
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/roles", response_model=ApiResponse[RolesOut])
async def list_market_roles(
    dataset_kind: DatasetKind = Query(default="all"),
):
    result = await asyncio.to_thread(_service().roles, dataset_kind)
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/overview", response_model=ApiResponse[MarketOverviewOut])
async def market_overview(
    role: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=100),
    dataset_kind: DatasetKind = Query(default="all"),
):
    result = await asyncio.to_thread(
        _service().overview,
        role=role,
        location=location,
        dataset_kind=dataset_kind,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/insights", response_model=ApiResponse[MarketOverviewOut])
async def market_insights(
    role: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=100),
    dataset_kind: DatasetKind = Query(default="all"),
):
    return await market_overview(role=role, location=location, dataset_kind=dataset_kind)


@router.get("/skills", response_model=ApiResponse[SkillDemandOut])
async def market_skills(
    role: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=100),
    dataset_kind: DatasetKind = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=50),
):
    result = await asyncio.to_thread(
        _service().skills,
        role=role,
        location=location,
        dataset_kind=dataset_kind,
        limit=limit,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/distributions", response_model=ApiResponse[DistributionOut])
async def market_distribution(
    dimension: Literal["education", "experience", "location"] = Query(
        default="education"
    ),
    role: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=100),
    dataset_kind: DatasetKind = Query(default="all"),
):
    result = await asyncio.to_thread(
        _service().distribution,
        dimension,
        role=role,
        location=location,
        dataset_kind=dataset_kind,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.get("/trends", response_model=ApiResponse[TrendOut])
async def market_trends(
    role: str | None = Query(default=None, max_length=200),
    location: str | None = Query(default=None, max_length=100),
    dataset_kind: DatasetKind = Query(default="all"),
    months: int = Query(default=6, ge=2, le=24),
):
    result = await asyncio.to_thread(
        _service().trends,
        role=role,
        location=location,
        dataset_kind=dataset_kind,
        months=months,
    )
    return ApiResponse(data=result, request_id=current_request_id())
