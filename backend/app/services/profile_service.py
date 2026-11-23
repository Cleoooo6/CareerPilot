import asyncio
import json
from typing import Any
from uuid import UUID

from app.agents.context import build_chat_profile_context
from app.core.errors import AppError, NotFoundError
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.db.profile_repositories import profile_repository
from app.db.repositories import user_repository
from app.schemas.profile import ProfileAnalysisResult, ProfileData
from app.services.profile_metadata import prepare_manual_skills

PROFILE_ANALYSIS_SYSTEM_PROMPT = """你是 CareerPilot AI 的职业画像分析师。
只基于用户已确认的职业画像进行分析，不得编造不存在的经历、技能、学历或成果。
所有判断必须区分：
- fact：画像中有明确事实依据；
- inference：基于事实的推断，必须给出不确定性；
- suggestion：面向下一步的建议。
只输出 JSON 对象，字段必须符合给定 Schema。不要输出 Markdown 或额外字段。
缺少证据时写入 missing_information，不要补造。"""


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
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

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

    async def analyze(self, user_id: UUID) -> dict[str, Any]:
        profile = await self.get_profile(user_id)
        if profile is None or not profile_has_content(profile.get("data")):
            raise AppError(
                "PROFILE_EMPTY",
                "请先完善并确认职业画像后再进行分析",
                status_code=409,
            )
        data = profile["data"]
        profile_context = json.dumps(data, ensure_ascii=False)[:8000]
        mock_payload = _mock_analysis(data) if self.llm.mode == "mock" else None
        try:
            result = await asyncio.to_thread(
                self.llm.complete_structured_with_meta,
                PROFILE_ANALYSIS_SYSTEM_PROMPT,
                f"已确认职业画像：\n{profile_context}",
                ProfileAnalysisResult,
                mock_payload=mock_payload,
            )
        except LLMError as exc:
            raise AppError(exc.code, exc.message, status_code=exc.status_code) from exc

        analysis = result.value.model_dump(mode="json")
        return await asyncio.to_thread(
            profile_repository.create_analysis,
            user_id,
            profile["id"],
            self.llm.settings.llm_provider,
            result.model or self.llm.settings.llm_model,
            self.llm.mode,
            analysis,
        )

    async def list_analyses(self, user_id: UUID) -> list[dict[str, Any]]:
        return await asyncio.to_thread(profile_repository.list_analyses, user_id)

    async def get_analysis(
        self, user_id: UUID, analysis_id: UUID
    ) -> dict[str, Any]:
        analysis = await asyncio.to_thread(
            profile_repository.get_analysis, user_id, analysis_id
        )
        if analysis is None:
            raise NotFoundError("职业分析记录不存在")
        return analysis

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
