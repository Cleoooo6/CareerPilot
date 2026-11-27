"""Unified AI service layer and career-context tests (no database)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.context import build_chat_career_context
from app.ai import PROFILE_ANALYSIS_SPEC
from app.ai.service import AIService
from app.core.config import Settings
from app.core.llm import LLMClient, LLMError
from app.schemas.profile import ProfileAnalysisResult

pytestmark = pytest.mark.unit


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _settings() -> Settings:
    return Settings(app_env="test", llm_mode="mock", llm_api_key="")


def _service() -> tuple[AIService, FakeRepository]:
    repository = FakeRepository()
    client = LLMClient(settings=_settings())
    return AIService(llm_client=client, repository=repository), repository


def test_structured_returns_schema_and_records_usage() -> None:
    service, repository = _service()
    payload = {
        "overview": "真实画像摘要",
        "strengths": [],
        "gaps": [],
        "fit": {"summary": "", "evidence": [], "uncertainty": []},
        "directions": [],
        "missing_information": [],
        "next_actions": [],
    }
    value, meta = service.structured(
        user_id=uuid4(),
        purpose="profile_analysis",
        prompt=PROFILE_ANALYSIS_SPEC,
        user_prompt="画像",
        schema=ProfileAnalysisResult,
        mock_payload=payload,
        source_type="profile",
    )
    assert isinstance(value, ProfileAnalysisResult)
    assert value.overview == "真实画像摘要"
    assert meta.prompt_version == PROFILE_ANALYSIS_SPEC.version
    assert meta.llm_mode == "mock"
    assert repository.calls[0]["status"] == "succeeded"
    assert repository.calls[0]["prompt_version"] == PROFILE_ANALYSIS_SPEC.version


def test_structured_failure_is_audited_and_reraises() -> None:
    service, repository = _service()
    with pytest.raises(LLMError):
        service.structured(
            user_id=uuid4(),
            purpose="profile_analysis",
            prompt=PROFILE_ANALYSIS_SPEC,
            user_prompt="画像",
            schema=ProfileAnalysisResult,
            mock_payload=None,
        )
    assert repository.calls[0]["status"] == "failed"
    assert repository.calls[0]["error_code"] == "LLM_NOT_CONFIGURED"


def test_record_stream_persists_status_and_tokens() -> None:
    service, repository = _service()
    service.record_stream(
        user_id=uuid4(),
        purpose="chat_reply",
        prompt=PROFILE_ANALYSIS_SPEC,
        model="glm-4.7-flash",
        duration_ms=123,
        usage=None,
        status="failed",
        error_code="LLM_TIMEOUT",
        source_type="chat",
    )
    call = repository.calls[0]
    assert call["status"] == "failed"
    assert call["error_code"] == "LLM_TIMEOUT"
    assert call["duration_ms"] == 123


def test_career_context_marks_stale_analysis_and_roadmap_progress() -> None:
    context = build_chat_career_context(
        profile_context="目标岗位：数据分析师",
        resume={
            "parsed_data": {
                "basic": {"name": "张三"},
                "skills": [{"name": "Python"}],
                "projects": [{"name": "项目A"}],
                "experiences": [],
            }
        },
        analysis={
            "analysis": {
                "overview": "总体分析",
                "strengths": [{"statement": "Python 基础"}],
                "gaps": [{"statement": "缺少量化成果"}],
            }
        },
        analysis_stale=True,
        gap={"to_improve": [{"name": "SQL"}], "not_recorded": [{"name": "Tableau"}]},
        roadmap={
            "target_role": "数据分析师",
            "stages": [
                {
                    "tasks": [
                        {"title": "完成 SQL 项目", "status": "completed"},
                        {"title": "补充可视化作品", "status": "pending"},
                    ]
                }
            ],
        },
    )
    assert "已确认简历解析" in context
    assert "可能过期" in context
    assert "SQL" in context
    assert "已完成 1 个" in context
    assert "完成 SQL 项目" in context


def test_career_context_is_empty_without_user_data() -> None:
    assert build_chat_career_context(profile_context="") == ""