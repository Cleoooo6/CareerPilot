import asyncio
import json
from typing import Any
from uuid import UUID

from app.agents.context import build_chat_profile_context
from app.ai import PROFILE_ANALYSIS_SPEC, AIService
from app.core.errors import AppError, NotFoundError
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.db.profile_repositories import profile_repository, resume_repository
from app.db.repositories import user_repository
from app.schemas.profile import ProfileAnalysisResult, ProfileData
from app.services.profile_metadata import prepare_manual_skills

PROFILE_ANALYSIS_SYSTEM_PROMPT = PROFILE_ANALYSIS_SPEC.system


def profile_has_content(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    basic = data.get("basic") or {}
    goals = data.get("goals") or {}
    if any(
        str(basic.get(key) or "").strip()
        for key in ("name", "education_level", "major", "location")
    ):
        return True
    if any(
        str(goals.get(key) or "").strip()
        for key in ("target_role", "target_industry", "job_status", "desired_direction")
    ):
        return True
    return any(data.get(key) for key in ("skills", "education", "projects", "experiences"))


def _mock_analysis(data: dict[str, Any]) -> dict[str, Any]:

    goals = data.get("goals") or {}
    skills = [item.get("name", "") for item in data.get("skills", []) if item.get("name")]
    education = data.get("education", [])
    projects = data.get("projects", [])
    experiences = data.get("experiences", [])
    target = goals.get("target_role") or "尚未明确目标岗位"
    return {
        "overview": (
            f"【Mock 分析】目标：{target}；技能 {len(skills)} 项，"
            f"教育经历 {len(education)} 段，项目 {len(projects)} 个，"
            f"工作/实习 {len(experiences)} 段。当前未调用真实模型。"
        ),
        "strengths": (
            [
                {
                    "statement": f"已记录技能：{'、'.join(skills[:8])}",
                    "basis": "fact",
                    "confidence": "high",
                }
            ]
            if skills
            else []
        ),
        "gaps": [
            {
                "statement": "当前画像信息可能不足以支持精确匹配判断，需要补充目标岗位和量化成果。",
                "basis": "inference",
                "confidence": "medium",
            }
        ],
        "fit": {
            "summary": f"与目标岗位「{target}」的匹配需要更多经历和技能证据。",
            "evidence": [f"画像包含 {len(skills)} 项技能"] if skills else [],
            "uncertainty": ["Mock 分析不调用真实模型，不能替代真实 AI 分析。"],
        },
        "directions": [
            {
                "statement": "先补充目标岗位、核心技能证据和可量化项目成果，再进行匹配分析。",
                "basis": "suggestion",
                "confidence": "medium",
            }
        ],
        "missing_information": ["目标岗位的岗位要求", "项目/工作成果的量化指标"],
        "next_actions": ["完善 Profile 中的技能证据", "补充目标岗位和求职状态"],
    }


class ProfileService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self.llm = llm_client or get_llm_client()
        self.ai = ai_service or AIService(llm_client=self.llm)

    async def ensure_user_id(self, external_id: str) -> UUID:
        user = await asyncio.to_thread(user_repository.ensure_user, external_id)
        return user["id"]

    async def get_profile(self, user_id: UUID) -> dict[str, Any] | None:
        return await asyncio.to_thread(profile_repository.get, user_id)

    async def save_profile(self, user_id: UUID, data: ProfileData) -> dict[str, Any]:
        existing = await asyncio.to_thread(profile_repository.get_data, user_id)
        prepared = prepare_manual_skills(
            existing, data.model_dump(mode="json")
        )
        return await asyncio.to_thread(
            profile_repository.upsert,
            user_id,
            prepared,
            "manual",
        )

    async def delete_profile(self, user_id: UUID) -> None:
        deleted = await asyncio.to_thread(profile_repository.delete, user_id)
        if not deleted:
            raise NotFoundError("职业画像不存在")

    async def analyze(self, user_id: UUID, *, force: bool = False) -> dict[str, Any]:
        profile = await self.get_profile(user_id)
        if profile is None or not profile_has_content(profile.get("data")):
            raise AppError(
                "PROFILE_EMPTY",
                "请先完善并确认职业画像后再进行分析",
                status_code=409,
            )
        revision_version = await asyncio.to_thread(
            profile_repository.latest_revision_version, user_id
        )
        if not force:
            latest = await asyncio.to_thread(
                profile_repository.latest_analysis, user_id
            )
            if (
                latest is not None
                and latest.get("source_revision_version") == revision_version
                and latest.get("prompt_version")
                == PROFILE_ANALYSIS_SPEC.version
            ):
                # Business-level idempotency: unchanged profile + same prompt
                # version must not trigger a duplicate paid/free model call.
                return self._decorate(latest, revision_version)

        resume = await asyncio.to_thread(resume_repository.latest_confirmed, user_id)
        resume_id = resume["id"] if resume else None
        data = profile["data"]
        profile_context = json.dumps(data, ensure_ascii=False)[:8000]
        mock_payload = _mock_analysis(data) if self.ai.mode == "mock" else None
        try:
            result, meta = await asyncio.to_thread(
                self.ai.structured,
                user_id=user_id,
                purpose="profile_analysis",
                prompt=PROFILE_ANALYSIS_SPEC,
                user_prompt=f"已确认职业画像：\n{profile_context}",
                schema=ProfileAnalysisResult,
                mock_payload=mock_payload,
                source_type="profile",
                source_id=profile["id"],
            )
        except LLMError as exc:
            raise AppError(exc.code, exc.message, status_code=exc.status_code) from exc

        analysis = result.model_dump(mode="json")
        row = await asyncio.to_thread(
            profile_repository.create_analysis,
            user_id,
            profile["id"],
            meta.provider,
            meta.model,
            meta.llm_mode,
            analysis,
            prompt_version=meta.prompt_version,
            source_revision_version=revision_version,
            resume_id=resume_id,
            duration_ms=meta.duration_ms,
            total_tokens=meta.usage.total_tokens,
        )
        return self._decorate(row, revision_version)

    async def list_analyses(self, user_id: UUID) -> list[dict[str, Any]]:
        current = await asyncio.to_thread(
            profile_repository.latest_revision_version, user_id
        )
        rows = await asyncio.to_thread(
            profile_repository.list_analyses, user_id
        )
        return [self._decorate(row, current) for row in rows]

    async def get_analysis(
        self, user_id: UUID, analysis_id: UUID
    ) -> dict[str, Any]:
        analysis = await asyncio.to_thread(
            profile_repository.get_analysis, user_id, analysis_id
        )
        if analysis is None:
            raise NotFoundError("职业分析记录不存在")
        current = await asyncio.to_thread(
            profile_repository.latest_revision_version, user_id
        )
        return self._decorate(analysis, current)

    @staticmethod
    def _decorate(
        row: dict[str, Any], current_revision_version: int | None
    ) -> dict[str, Any]:
        payload = dict(row)
        payload["stale"] = (
            current_revision_version is not None
            and int(row.get("source_revision_version") or 0)
            < current_revision_version
        )
        payload["current_revision_version"] = current_revision_version
        return payload

    async def list_revisions(self, user_id: UUID) -> list[dict[str, Any]]:
        return await asyncio.to_thread(profile_repository.list_revisions, user_id)

    async def get_revision(
        self, user_id: UUID, revision_id: UUID
    ) -> dict[str, Any]:
        revision = await asyncio.to_thread(
            profile_repository.get_revision, user_id, revision_id
        )
        if revision is None:
            raise NotFoundError("画像版本记录不存在")
        return revision

    async def chat_profile_context(self, user_id: UUID) -> str:
        data = await asyncio.to_thread(profile_repository.get_data, user_id)
        return build_chat_profile_context(data)


_profile_service: ProfileService | None = None


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


def reset_profile_service() -> None:
    global _profile_service
    _profile_service = None
