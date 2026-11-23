from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.market import MarketMeta, SkillDemandItem, SkillDemandOut
from app.schemas.roadmap import RoadmapDraftLLM
from app.services.roadmap_gap import compute_skill_gap
from app.services.roadmap_service import _mock_roadmap


def _meta(
    sample_size: int = 6,
    *,
    warnings: list[str] | None = None,
) -> MarketMeta:
    return MarketMeta(
        sample_size=sample_size,
        sample_sufficient=sample_size >= 5,
        period_start=None,
        period_end=None,
        updated_at=None,
        dataset_kinds=["synthetic"] if sample_size else [],
        sources=[],
        warnings=list(warnings or []),
    )


def _demand(
    rows: list[tuple[str, int, float]], meta: MarketMeta | None = None
) -> SkillDemandOut:
    return SkillDemandOut(
        items=[
            SkillDemandItem(skill=name, count=count, share=share, rank=index)
            for index, (name, count, share) in enumerate(rows, start=1)
        ],
        meta=meta or _meta(),
    )


def _skill(
    name: str,
    evidence: str = "课程项目",
    verification: str = "confirmed",
) -> dict[str, Any]:
    return {
        "name": name,
        "proficiency": "熟练",
        "evidence": evidence,
        "source": "manual",
        "verification": verification,
    }


def _profile(*skills: dict[str, Any]) -> dict[str, Any]:
    return {
        "goals": {"target_role": "数据分析师"},
        "skills": list(skills),
    }


def test_gap_classifies_evidence_and_missing_skills():
    gap = compute_skill_gap(
        profile_data=_profile(
            _skill("Python"),
            _skill("SQL", evidence=""),
            _skill("Vue"),
        ),
        target_role="数据分析师",
        demand=_demand(
            [
                ("Python", 4, 0.6667),
                ("SQL", 3, 0.5),
                ("Spark", 2, 0.3333),
                ("Tableau", 1, 0.1667),
            ]
        ),
    )
    assert gap.basis == "market"
    assert [item.name for item in gap.matched] == ["Python"]
    assert [item.name for item in gap.to_improve] == ["SQL"]
    assert [item.name for item in gap.not_recorded] == ["Spark", "Tableau"]
    assert gap.not_recorded[0].priority == "high"
    assert gap.to_improve[0].priority == "medium"
    assert {item.name for item in gap.matched}.isdisjoint(
        {item.name for item in gap.not_recorded}
    )
    assert {item.name for item in gap.profile_skills} == {"Python", "SQL", "Vue"}
    assert "synthetic" in gap.meta.dataset_kinds
    assert any("合成数据" in warning for warning in gap.warnings)


def test_gap_without_market_sample_degrades_to_general():
    gap = compute_skill_gap(
        profile_data=_profile(_skill("Python")),
        target_role="数据分析师",
        demand=_demand([], meta=_meta(0, warnings=["暂无匹配市场数据"])),
    )
    assert gap.basis == "general"
    assert gap.reference_only is False
    assert gap.matched == []
    assert gap.to_improve == []
    assert gap.not_recorded == []
    assert gap.meta.sample_size == 0
    assert any("没有可用的市场样本" in warning for warning in gap.warnings)


def test_matched_reason_explains_unverified_user_evidence():
    gap = compute_skill_gap(
        profile_data=_profile(_skill("Python")),
        target_role="数据分析师",
        demand=_demand([("Python", 4, 0.6667)]),
    )
    reason = gap.matched[0].reason
    assert "手动录入" in reason
    assert "资料已确认" in reason
    assert "未做客观验证" in reason


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("Python3", "Python"),
        ("Python开发", "Python"),
        ("py", "Python"),
        ("PYTHON", "Python"),
        ("Vue3", "Vue"),
    ],
)
def test_skill_alias_normalization(alias, canonical):
    gap = compute_skill_gap(
        profile_data=_profile(_skill(alias)),
        target_role="数据分析师",
        demand=_demand([(canonical, 3, 1.0)]),
    )
    assert [item.name for item in gap.matched] == [canonical]
    assert gap.not_recorded == []


def test_gap_does_not_treat_confirmation_as_objective_verification():
    gap = compute_skill_gap(
        profile_data=_profile(_skill("SQL", evidence="项目", verification="")),
        target_role="数据分析师",
        demand=_demand([("SQL", 5, 0.8333)]),
    )
    assert gap.matched == []
    assert [item.name for item in gap.to_improve] == ["SQL"]
    assert "不能视为已具备" in gap.to_improve[0].reason


def test_gap_keeps_market_basis_when_sample_is_insufficient():
    meta = _meta(3, warnings=["样本量不足 5 条，不得视为全国市场结论"])
    gap = compute_skill_gap(
        profile_data=_profile(),
        target_role="数据分析师",
        demand=_demand([("Spark", 3, 1.0)], meta=meta),
    )
    assert gap.basis == "market"
    assert gap.reference_only is True
    assert gap.meta.sample_sufficient is False
    assert [item.name for item in gap.not_recorded] == ["Spark"]
    assert any("样本量不足" in warning for warning in gap.warnings)
    assert any("参考" in warning for warning in gap.warnings)


def test_mock_roadmap_passes_structural_validation():
    gap = compute_skill_gap(
        profile_data=_profile(_skill("SQL", evidence="")),
        target_role="数据分析师",
        demand=_demand([("SQL", 4, 0.6667), ("Spark", 3, 0.5)]),
    )
    payload = _mock_roadmap("数据分析师", gap)
    draft = RoadmapDraftLLM.model_validate(payload)
    assert len(draft.stages) >= 3
    assert sum(len(stage.tasks) for stage in draft.stages) >= 2
    assert all(
        task.acceptance_criteria.strip()
        for stage in draft.stages
        for task in stage.tasks
    )
    assert "synthetic" in draft.summary


def _draft_payload(
    stages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "title": "数据分析师成长路线",
        "summary": "先补齐技能，再完成端到端项目。",
        "stages": stages
        or [
            {
                "title": "阶段一",
                "goal": "补齐基础",
                "duration": "2 周",
                "priority": "high",
                "tasks": [
                    {
                        "title": "完成 Python 基础练习与自测",
                        "description": "完成练习",
                        "task_type": "learning",
                        "priority": "high",
                        "estimated_time": "1 周",
                        "acceptance_criteria": "提交练习代码与说明",
                    },
                    {
                        "title": "完成 SQL 查询练习与复盘",
                        "description": "完成练习",
                        "task_type": "learning",
                        "priority": "medium",
                        "estimated_time": "1 周",
                        "acceptance_criteria": "提交查询结果与复盘笔记",
                    },
                ],
            }
        ],
    }


def test_roadmap_draft_rejects_vague_acceptance_criteria():
    payload = _draft_payload()
    payload["stages"][0]["tasks"][0]["acceptance_criteria"] = ""
    with pytest.raises(ValidationError):
        RoadmapDraftLLM.model_validate(payload)


def test_roadmap_draft_rejects_duplicate_task_titles():
    payload = _draft_payload()
    payload["stages"][0]["tasks"][1]["title"] = "完成 Python 基础练习与自测"
    with pytest.raises(ValidationError):
        RoadmapDraftLLM.model_validate(payload)


def test_roadmap_draft_requires_at_least_two_tasks():
    payload = _draft_payload()
    payload["stages"][0]["tasks"] = payload["stages"][0]["tasks"][:1]
    with pytest.raises(ValidationError):
        RoadmapDraftLLM.model_validate(payload)


def test_roadmap_draft_rejects_duplicate_stage_titles():
    stage = _draft_payload()["stages"][0]
    with pytest.raises(ValidationError):
        RoadmapDraftLLM.model_validate(_draft_payload([stage, stage]))
