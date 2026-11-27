from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_user_id
from app.core.logging import current_request_id
from app.schemas.common import ApiResponse
from app.schemas.roadmap import (
    RoadmapGenerateRequest,
    RoadmapOut,
    RoadmapStateOut,
    RoadmapSummaryListOut,
    RoadmapSummaryOut,
    RoadmapTaskUpdateOut,
    RoadmapTaskUpdateRequest,
    SkillGapOut,
)
from app.services.profile_service import get_profile_service
from app.services.roadmap_service import get_roadmap_service

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


async def _user_id(user_external: str) -> UUID:
    return await get_profile_service().ensure_user_id(user_external)


@router.get("/gap", response_model=ApiResponse[SkillGapOut])
async def get_skill_gap(
    target_role: str | None = Query(default=None, max_length=200),
    user_id: str = Depends(get_user_id),
):
    service = get_roadmap_service()
    gap = await service.gap_for_user(await _user_id(user_id), target_role)
    return ApiResponse(data=gap, request_id=current_request_id())


@router.post(
    "/generate",
    response_model=ApiResponse[RoadmapOut],
    status_code=201,
)
async def generate_roadmap(
    payload: RoadmapGenerateRequest | None = None,
    user_id: str = Depends(get_user_id),
):
    service = get_roadmap_service()
    roadmap, _reused = await service.generate_draft(
        await _user_id(user_id),
        payload.target_role if payload else None,
        payload.regenerate if payload else False,
    )
    return ApiResponse(data=roadmap, request_id=current_request_id())


@router.get("/current", response_model=ApiResponse[RoadmapStateOut])
async def get_current_roadmap(user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    roadmap = await service.get_current(await _user_id(user_id))
    return ApiResponse(
        data=RoadmapStateOut(roadmap=roadmap),
        request_id=current_request_id(),
    )


@router.get("/drafts", response_model=ApiResponse[RoadmapSummaryListOut])
async def list_roadmap_drafts(user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    items = await service.list_drafts(await _user_id(user_id))
    return ApiResponse(
        data=RoadmapSummaryListOut(items=items),
        request_id=current_request_id(),
    )


@router.get("/history", response_model=ApiResponse[RoadmapSummaryListOut])
async def list_roadmap_history(user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    items = await service.list_history(await _user_id(user_id))
    return ApiResponse(
        data=RoadmapSummaryListOut(items=items),
        request_id=current_request_id(),
    )


@router.patch("/tasks/{task_id}", response_model=ApiResponse[RoadmapTaskUpdateOut])
async def update_roadmap_task(
    task_id: UUID,
    payload: RoadmapTaskUpdateRequest,
    user_id: str = Depends(get_user_id),
):
    service = get_roadmap_service()
    result = await service.update_task(
        await _user_id(user_id),
        task_id,
        status=payload.status,
        outcome=payload.outcome,
    )
    return ApiResponse(data=result, request_id=current_request_id())


@router.post("/{roadmap_id}/adjust", response_model=ApiResponse[RoadmapOut])
async def adjust_roadmap(roadmap_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    roadmap, _reused = await service.adjust_draft(
        await _user_id(user_id), roadmap_id
    )
    return ApiResponse(data=roadmap, request_id=current_request_id())


@router.get("/{roadmap_id}", response_model=ApiResponse[RoadmapOut])
async def get_roadmap(roadmap_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    roadmap = await service.get_roadmap(await _user_id(user_id), roadmap_id)
    return ApiResponse(data=roadmap, request_id=current_request_id())


@router.post("/{roadmap_id}/confirm", response_model=ApiResponse[RoadmapOut])
async def confirm_roadmap(roadmap_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    roadmap = await service.confirm(await _user_id(user_id), roadmap_id)
    return ApiResponse(data=roadmap, request_id=current_request_id())


@router.post(
    "/{roadmap_id}/discard",
    response_model=ApiResponse[RoadmapSummaryOut],
)
async def discard_roadmap(roadmap_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_roadmap_service()
    roadmap = await service.discard(await _user_id(user_id), roadmap_id)
    return ApiResponse(data=roadmap, request_id=current_request_id())
