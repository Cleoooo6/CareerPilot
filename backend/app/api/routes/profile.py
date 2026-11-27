from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_user_id
from app.core.config import get_settings
from app.core.logging import current_request_id
from app.schemas.common import ApiResponse
from app.schemas.profile import (
    ProfileAnalysisListOut,
    ProfileAnalysisOut,
    ProfileAnalyzeRequest,
    ProfileOut,
    ProfileRevisionDetailOut,
    ProfileRevisionListOut,
    ProfileRevisionOut,
    ProfileSaveRequest,
    ProfileStateOut,
    ResumeConfirmRequest,
    ResumeParseListOut,
    ResumeParseOut,
    ResumeUpdateRequest,
)
from app.services.profile_service import get_profile_service
from app.services.resume_service import get_resume_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ApiResponse[ProfileStateOut])
async def get_profile(user_id: str = Depends(get_user_id)):
    service = get_profile_service()
    profile = await service.get_profile(await service.ensure_user_id(user_id))
    return ApiResponse(
        data=ProfileStateOut(profile=ProfileOut.model_validate(profile) if profile else None),
        request_id=current_request_id(),
    )


@router.put("", response_model=ApiResponse[ProfileOut])
async def save_profile(
    payload: ProfileSaveRequest,
    user_id: str = Depends(get_user_id),
):
    service = get_profile_service()
    profile = await service.save_profile(
        await service.ensure_user_id(user_id), payload.data
    )
    return ApiResponse(
        data=ProfileOut.model_validate(profile),
        request_id=current_request_id(),
    )


@router.delete("", status_code=204)
async def delete_profile(user_id: str = Depends(get_user_id)):
    service = get_profile_service()
    await service.delete_profile(await service.ensure_user_id(user_id))
    return None


@router.get("/revisions", response_model=ApiResponse[ProfileRevisionListOut])
async def list_profile_revisions(user_id: str = Depends(get_user_id)):
    service = get_profile_service()
    rows = await service.list_revisions(await service.ensure_user_id(user_id))
    return ApiResponse(
        data=ProfileRevisionListOut(
            items=[ProfileRevisionOut.model_validate(row) for row in rows]
        ),
        request_id=current_request_id(),
    )


@router.get(
    "/revisions/{revision_id}",
    response_model=ApiResponse[ProfileRevisionDetailOut],
)
async def get_profile_revision(
    revision_id: UUID, user_id: str = Depends(get_user_id)
):
    service = get_profile_service()
    row = await service.get_revision(
        await service.ensure_user_id(user_id), revision_id
    )
    return ApiResponse(
        data=ProfileRevisionDetailOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.get("/resume", response_model=ApiResponse[ResumeParseListOut])
async def list_resumes(user_id: str = Depends(get_user_id)):
    service = get_resume_service()
    rows = await service.list_resumes(await service.ensure_user_id(user_id))
    return ApiResponse(
        data=ResumeParseListOut(
            items=[ResumeParseOut.model_validate(row) for row in rows]
        ),
        request_id=current_request_id(),
    )


@router.post(
    "/resume/upload",
    response_model=ApiResponse[ResumeParseOut],
    status_code=201,
)
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
):
    settings = get_settings()
    service = get_resume_service()
    data = await file.read(settings.resume_max_bytes + 1)
    try:
        row = await service.upload(
            await service.ensure_user_id(user_id),
            filename=file.filename or "",
            content_type=file.content_type,
            data=data,
        )
    finally:
        await file.close()
    return ApiResponse(
        data=ResumeParseOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.get("/resume/{resume_id}", response_model=ApiResponse[ResumeParseOut])
async def get_resume(resume_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_resume_service()
    row = await service.get_resume(await service.ensure_user_id(user_id), resume_id)
    return ApiResponse(
        data=ResumeParseOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.patch("/resume/{resume_id}", response_model=ApiResponse[ResumeParseOut])
async def update_resume(
    resume_id: UUID,
    payload: ResumeUpdateRequest,
    user_id: str = Depends(get_user_id),
):
    service = get_resume_service()
    row = await service.update_draft(
        await service.ensure_user_id(user_id), resume_id, payload.parsed_data
    )
    return ApiResponse(
        data=ResumeParseOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.post(
    "/resume/{resume_id}/reparse",
    response_model=ApiResponse[ResumeParseOut],
)
async def reparse_resume(resume_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_resume_service()
    row = await service.reparse(
        await service.ensure_user_id(user_id), resume_id
    )
    return ApiResponse(
        data=ResumeParseOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.post("/resume/{resume_id}/confirm", response_model=ApiResponse[ProfileOut])
async def confirm_resume(
    resume_id: UUID,
    payload: ResumeConfirmRequest,
    user_id: str = Depends(get_user_id),
):
    service = get_resume_service()
    profile = await service.confirm(
        await service.ensure_user_id(user_id),
        resume_id,
        sections=payload.sections,
        draft=payload.draft,
    )
    return ApiResponse(
        data=ProfileOut.model_validate(profile),
        request_id=current_request_id(),
    )


@router.post("/resume/{resume_id}/discard", response_model=ApiResponse[ResumeParseOut])
async def discard_resume(resume_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_resume_service()
    row = await service.discard(
        await service.ensure_user_id(user_id), resume_id
    )
    return ApiResponse(
        data=ResumeParseOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.post("/analysis", response_model=ApiResponse[ProfileAnalysisOut])
async def analyze_profile(
    payload: ProfileAnalyzeRequest | None = None,
    user_id: str = Depends(get_user_id),
):
    service = get_profile_service()
    row = await service.analyze(
        await service.ensure_user_id(user_id),
        force=bool(payload.force) if payload else False,
    )
    return ApiResponse(
        data=ProfileAnalysisOut.model_validate(row),
        request_id=current_request_id(),
    )


@router.get("/analysis", response_model=ApiResponse[ProfileAnalysisListOut])
async def list_analyses(user_id: str = Depends(get_user_id)):
    service = get_profile_service()
    rows = await service.list_analyses(await service.ensure_user_id(user_id))
    return ApiResponse(
        data=ProfileAnalysisListOut(
            items=[ProfileAnalysisOut.model_validate(row) for row in rows]
        ),
        request_id=current_request_id(),
    )


@router.get(
    "/analysis/{analysis_id}",
    response_model=ApiResponse[ProfileAnalysisOut],
)
async def get_analysis(analysis_id: UUID, user_id: str = Depends(get_user_id)):
    service = get_profile_service()
    row = await service.get_analysis(
        await service.ensure_user_id(user_id), analysis_id
    )
    return ApiResponse(
        data=ProfileAnalysisOut.model_validate(row),
        request_id=current_request_id(),
    )
