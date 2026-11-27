"""Evaluation Harness v0 判定逻辑测试（纯内存，无网络/数据库）。"""
from __future__ import annotations

import pytest

from app.ai.evaluation import (
    PROFILE_SAMPLES,
    RESUME_SAMPLES,
    ROADMAP_SAMPLES,
    evaluate_profile,
    evaluate_resume,
    evaluate_roadmap,
    summarize_checks,
)
from app.schemas.profile import (
    AnalysisClaim,
    ExperienceItem,
    ProfileAnalysisResult,
    ProfileData,
    SkillItem,
)
from app.schemas.roadmap import RoadmapDraftLLM, RoadmapStageLLM, RoadmapTaskLLM

pytestmark = pytest.mark.unit


def _resume_value(
    name: str = "林舟",
    role: str = "数据分析师",
    company: str = "虚构科技有限公司",
) -> ProfileData:
    return ProfileData(
        basic={"name": name},
        goals={"target_role": role},
        skills=[SkillItem(name="Python"), SkillItem(name="SQL")],
        experiences=[ExperienceItem(company=company, position="数据分析实习生")],
    )


def _profile_value(
    overview: str = "林舟具备 Python 与 SQL 基础，目标为数据分析师岗位，项目经历以数据处理为主。",
    strengths: int = 1,
    gaps: int = 1,
    directions: int = 1,
) -> ProfileAnalysisResult:
    def claim(text: str) -> AnalysisClaim:
        return AnalysisClaim(
            statement=text, basis="inference", confidence="medium"
        )

    return ProfileAnalysisResult(
        overview=overview,
        strengths=[claim("Python 数据处理能力有课程项目支撑")] * strengths,
        gaps=[claim("缺少 SQL 窗口函数等进阶能力的证据")] * gaps,
        directions=[claim("优先补齐 SQL 进阶并产出分析作品")] * directions,
    )


def _roadmap_value(title: str = "应届生数据分析师三个月成长计划") -> RoadmapDraftLLM:
    task = RoadmapTaskLLM(
        title="完成 SQL 窗口函数专题练习",
        description="覆盖排名、分组统计等常见场景",
        acceptance_criteria="独立完成 20 道中等难度 SQL 题并整理错题",
    )
    second = RoadmapTaskLLM(
        title="产出一份可视化分析报告",
        description="基于公开数据集完成完整分析",
        acceptance_criteria="报告包含数据清洗过程与结论，可供作品集展示",
    )
    return RoadmapDraftLLM(
        title=title,
        summary="以 SQL 与可视化为核心的三阶段计划",
        stages=[
            RoadmapStageLLM(title="第一阶段", goal="SQL 进阶", tasks=[task]),
            RoadmapStageLLM(title="第二阶段", goal="作品产出", tasks=[second]),
        ],
    )


def _failures(checks) -> list[str]:
    _, _, failures = summarize_checks(checks)
    return failures


def test_resume_good_sample_passes_all_quality_checks():
    sample = RESUME_SAMPLES[0]
    failures = _failures(
        evaluate_resume(
            sample, _resume_value()
        )
    )
    assert failures == []


def test_resume_missing_name_and_fabricated_company_are_caught():
    sample = RESUME_SAMPLES[0]
    failures = _failures(
        evaluate_resume(
            sample, _resume_value(name="", company="从未出现过的公司")
        )
    )
    assert "name_extracted" in failures
    assert "no_fabricated_entities" in failures
    assert "required_fields_present" in failures


def test_profile_good_sample_passes_all_quality_checks():
    sample = PROFILE_SAMPLES[0]
    failures = _failures(
        evaluate_profile(
            sample, _profile_value()
        )
    )
    assert failures == []


def test_profile_empty_content_fails_quality_gates():
    sample = PROFILE_SAMPLES[0]
    failures = _failures(
        evaluate_profile(
            sample,
            _profile_value(overview="", strengths=0, gaps=0, directions=0),
        )
    )
    assert "overview_nonempty" in failures
    assert "strengths_present" in failures
    assert "gaps_present" in failures
    assert "directions_present" in failures
    assert "traceable_to_input" in failures


def test_roadmap_good_sample_passes_all_quality_checks():
    sample = ROADMAP_SAMPLES[0]
    failures = _failures(
        evaluate_roadmap(
            sample, _roadmap_value()
        )
    )
    assert failures == []


def test_roadmap_generic_title_and_ungrounded_tasks_fail():
    sample = ROADMAP_SAMPLES[0]
    ungrounded = RoadmapDraftLLM(
        title="成长路线",
        summary="通用计划",
        stages=[
            RoadmapStageLLM(
                title="第一阶段",
                goal="基础巩固",
                tasks=[
                    RoadmapTaskLLM(
                        title="认真学习基础知识",
                        description="巩固理论",
                        acceptance_criteria="完成教材阅读并整理笔记",
                    ),
                    RoadmapTaskLLM(
                        title="参与综合实践训练",
                        description="积累经验",
                        acceptance_criteria="完成一个综合训练项目",
                    ),
                ],
            )
        ],
    )
    failures = _failures(evaluate_roadmap(sample, ungrounded))
    assert "title_nonempty" in failures
    assert "grounded_in_gap" in failures
