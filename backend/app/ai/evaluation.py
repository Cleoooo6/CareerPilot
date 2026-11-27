"""Evaluation Harness v0: fixed synthetic samples + machine-readable gates.

Kept separate from business logic so prompts/models can be compared without
touching services. Schema validation and content quality are scored
independently: a model can pass schema while failing quality (or vice versa).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

HARNESS_VERSION = "eval_harness@v1"

PLACEHOLDER_PHRASES = (
    "多练习",
    "继续学习",
    "多学习",
    "了解更多",
    "深入学习",
    "待补充",
    "略",
    "todo",
)

GENERIC_BOILERPLATE = (
    "该用户具有较强的学习能力",
    "具备良好的沟通能力",
    "综合素质较强",
)


@dataclass(frozen=True)
class ResumeSample:
    sample_id: str
    text: str
    expected_name: str
    expected_role: str
    expected_core_skills: tuple[str, ...]
    allowed_entities: tuple[str, ...]


@dataclass(frozen=True)
class ProfileSample:
    sample_id: str
    profile: dict[str, Any]
    input_keywords: tuple[str, ...]


@dataclass(frozen=True)
class RoadmapSample:
    sample_id: str
    payload: dict[str, Any]
    input_keywords: tuple[str, ...]


RESUME_SAMPLES: tuple[ResumeSample, ...] = (
    ResumeSample(
        sample_id="resume_A",
        text=(
            "姓名：林舟\n"
            "目标岗位：数据分析师\n"
            "学历：本科\n"
            "专业：信息管理与信息系统\n"
            "所在地：上海\n"
            "毕业时间：2026\n"
            "学校：虚构大学\n"
            "技能：Python、SQL、Excel\n"
            "项目：校园二手交易数据分析（Python 清洗 1.2 万条记录，产出可视化报告）\n"
            "实习：虚构科技有限公司 数据分析实习生（整理销售数据，制作周报）\n"
            "证书：无\n"
        ),
        expected_name="林舟",
        expected_role="数据分析师",
        expected_core_skills=("Python", "SQL"),
        allowed_entities=("虚构大学", "虚构科技有限公司"),
    ),
    ResumeSample(
        sample_id="resume_B",
        text=(
            "姓名：李文静\n"
            "求职意向：数据分析岗位\n"
            "教育背景：本科 市场营销专业 上海商学院 2024 届\n"
            "工作经历：\n"
            "2024.07 至今 上海云帆信息技术有限公司 市场专员\n"
            "负责活动数据整理与月度报表，使用 Excel 与 SQL 完成基础分析\n"
            "项目经历：用户增长渠道分析（SQL 提取 5 万行行为数据，产出渠道对比结论）\n"
            "技能：Excel、SQL、基础 Python\n"
        ),
        expected_name="李文静",
        expected_role="数据分析",
        expected_core_skills=("Excel", "SQL"),
        allowed_entities=("上海商学院", "上海云帆信息技术有限公司"),
    ),
)

_PROFILE_A: dict[str, Any] = {
    "basic": {
        "name": "林舟",
        "education_level": "本科",
        "major": "信息管理与信息系统",
        "graduation_year": 2026,
        "location": "上海",
    },
    "goals": {
        "target_role": "数据分析师",
        "target_industry": "互联网",
        "job_status": "求职中",
        "desired_direction": "数据分析",
    },
    "skills": [
        {"name": "Python", "proficiency": "熟练", "evidence": "课程项目"},
        {"name": "SQL", "proficiency": "熟悉", "evidence": "课程项目"},
        {"name": "Excel", "proficiency": "熟悉", "evidence": ""},
    ],
    "education": [],
    "projects": [],
    "experiences": [],
}

_PROFILE_B: dict[str, Any] = {
    "basic": {
        "name": "李文静",
        "education_level": "本科",
        "major": "市场营销",
        "graduation_year": 2024,
        "location": "上海",
    },
    "goals": {
        "target_role": "数据分析师",
        "target_industry": "互联网",
        "job_status": "在职看机会",
        "desired_direction": "从市场营销转向数据分析",
    },
    "skills": [
        {"name": "Excel", "proficiency": "熟练", "evidence": "月度报表"},
        {"name": "SQL", "proficiency": "熟悉", "evidence": "渠道分析项目"},
        {"name": "Python", "proficiency": "了解", "evidence": ""},
    ],
    "education": [],
    "projects": [
        {"name": "用户增长渠道分析", "role": "分析", "description": "SQL 提取行为数据"}
    ],
    "experiences": [
        {"company": "上海云帆信息技术有限公司", "position": "市场专员"}
    ],
}

PROFILE_SAMPLES: tuple[ProfileSample, ...] = (
    ProfileSample(
        sample_id="profile_A",
        profile=_PROFILE_A,
        input_keywords=(
            "Python",
            "SQL",
            "Excel",
            "数据分析师",
            "信息管理与信息系统",
            "上海",
        ),
    ),
    ProfileSample(
        sample_id="profile_B",
        profile=_PROFILE_B,
        input_keywords=(
            "Excel",
            "SQL",
            "数据分析",
            "市场营销",
            "渠道分析",
            "报表",
        ),
    ),
)


def _gap_snapshot(to_improve: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target_role": "数据分析师",
        "basis": "general",
        "reference_only": True,
        "matched": [],
        "to_improve": to_improve,
        "not_recorded": [],
        "profile_skills": [
            {
                "name": "Python",
                "proficiency": "熟练",
                "evidence": "",
                "source": "",
                "verification": "",
            }
        ],
        "meta": {
            "sample_size": 0,
            "sample_sufficient": False,
            "dataset_kinds": [],
            "updated_at": None,
            "dataset_kind": "none",
            "warnings": [],
        },
        "warnings": ["无市场样本，仅供通用建议"],
        "computed_at": "2026-11-27T00:00:00Z",
    }


ROADMAP_SAMPLES: tuple[RoadmapSample, ...] = (
    RoadmapSample(
        sample_id="roadmap_A",
        payload={
            "target_role": "数据分析师",
            "profile": _PROFILE_A,
            "skill_gap": _gap_snapshot(
                [
                    {
                        "name": "SQL",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "high",
                        "reason": "目标岗位常见要求",
                    },
                    {
                        "name": "可视化",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "medium",
                        "reason": "展示分析结论",
                    },
                ]
            ),
        },
        input_keywords=("SQL", "可视化", "数据分析师"),
    ),
    RoadmapSample(
        sample_id="roadmap_B",
        payload={
            "target_role": "数据分析师",
            "profile": _PROFILE_B,
            "skill_gap": _gap_snapshot(
                [
                    {
                        "name": "Python",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "high",
                        "reason": "自动化分析需要",
                    },
                    {
                        "name": "统计基础",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "medium",
                        "reason": "解读数据结论",
                    },
                ]
            ),
        },
        input_keywords=("Python", "统计", "数据分析"),
    ),
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    # deterministic = 确定性规则（ground truth 对照/结构约束/非空长度），机器可判定；
    # semantic_heuristic = 语义启发（关键词命中/追溯性），仅作辅助信号，不能单独证明正确。
    check_type: str = "deterministic"


@dataclass
class EvaluationRecord:
    recorded_at: str
    harness_version: str
    mode: str
    model: str
    chain: str
    sample_id: str
    prompt_key: str
    prompt_version: str
    duration_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    error_code: str | None = None
    schema_pass: bool = False
    schema_errors: list[str] = field(default_factory=list)
    quality_pass: bool = False
    quality_checks: list[dict[str, Any]] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "harness_version": self.harness_version,
            "mode": self.mode,
            "model": self.model,
            "chain": self.chain,
            "sample_id": self.sample_id,
            "prompt_key": self.prompt_key,
            "prompt_version": self.prompt_version,
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
            "error_code": self.error_code,
            "schema_pass": self.schema_pass,
            "schema_errors": self.schema_errors,
            "quality_pass": self.quality_pass,
            "quality_checks": self.quality_checks,
            "failure_reasons": self.failure_reasons,
            "summary": self.summary,
            "output": self.output,
        }


def _hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [kw for kw in keywords if kw.lower() in lowered]


def _dedup_overlap(statements: list[str]) -> bool:
    non_empty = [s for s in statements if s.strip()]
    normalized = {s.strip() for s in non_empty}
    return len(normalized) < len(non_empty)


def evaluate_resume(sample: ResumeSample, value: Any) -> list[CheckResult]:
    checks: list[CheckResult] = []
    name = (getattr(value, "basic", None) and value.basic.name) or ""
    role = (getattr(value, "goals", None) and value.goals.target_role) or ""
    skills = [item.name for item in (getattr(value, "skills", None) or [])]

    checks.append(
        CheckResult(
            "name_extracted",
            bool(name) and sample.expected_name in name,
            f"name={name!r}",
        )
    )
    checks.append(
        CheckResult(
            "target_role_extracted",
            bool(role) and sample.expected_role in role,
            f"target_role={role!r}",
        )
    )
    core_hits = [s for s in sample.expected_core_skills if s in skills]
    checks.append(
        CheckResult(
            "core_skills_covered",
            len(core_hits) >= max(1, len(sample.expected_core_skills) - 1),
            f"hits={core_hits} expected={list(sample.expected_core_skills)}",
        )
    )

    fabricated: list[str] = []
    for item in (getattr(value, "education", None) or []):
        school = str(getattr(item, "school", "") or "")
        if school and school not in sample.allowed_entities and school not in sample.text:
            fabricated.append(f"education.school:{school}")
    for item in (getattr(value, "experiences", None) or []):
        company = str(getattr(item, "company", "") or "")
        if (
            company
            and company not in sample.allowed_entities
            and company not in sample.text
        ):
            fabricated.append(f"experiences.company:{company}")
    checks.append(
        CheckResult("no_fabricated_entities", not fabricated, f"fabricated={fabricated}")
    )

    missing = []
    if not name:
        missing.append("basic.name")
    if not role:
        missing.append("goals.target_role")
    checks.append(
        CheckResult(
            "required_fields_present",
            not missing,
            f"missing={missing}",
        )
    )
    return checks


def evaluate_profile(sample: ProfileSample, value: Any) -> list[CheckResult]:
    checks: list[CheckResult] = []
    overview = str(getattr(value, "overview", "") or "").strip()
    strengths = [
        str(item.statement).strip()
        for item in (getattr(value, "strengths", None) or [])
        if str(getattr(item, "statement", "")).strip()
    ]
    gaps = [
        str(item.statement).strip()
        for item in (getattr(value, "gaps", None) or [])
        if str(getattr(item, "statement", "")).strip()
    ]
    directions = [
        str(getattr(item, "statement", "") or "").strip()
        for item in (getattr(value, "directions", None) or [])
    ]
    directions = [d for d in directions if d]

    checks.append(
        CheckResult(
            "overview_nonempty",
            len(overview) >= 30,
            f"length={len(overview)}",
        )
    )
    body = overview + "".join(strengths) + "".join(gaps)
    keyword_hits = _hits(body, sample.input_keywords)
    checks.append(
        CheckResult(
            "traceable_to_input",
            len(keyword_hits) >= 2,
            f"hits={keyword_hits}",
            "semantic_heuristic",
        )
    )
    boilerplate_only = bool(overview) and all(
        phrase in overview for phrase in GENERIC_BOILERPLATE
    )
    checks.append(
        CheckResult(
            "overview_not_boilerplate",
            not boilerplate_only and len(overview) > 0,
            f"boilerplate_only={boilerplate_only}",
        )
    )
    checks.append(
        CheckResult("strengths_present", len(strengths) >= 1, f"count={len(strengths)}")
    )
    checks.append(CheckResult("gaps_present", len(gaps) >= 1, f"count={len(gaps)}"))
    checks.append(
        CheckResult(
            "directions_present", len(directions) >= 1, f"count={len(directions)}"
        )
    )
    short_items = [s for s in strengths + gaps if len(s) < 8]
    checks.append(
        CheckResult(
            "statements_substantive",
            not short_items,
            f"short={short_items[:3]}",
        )
    )
    duplicated = _dedup_overlap(strengths) or _dedup_overlap(gaps)
    checks.append(CheckResult("no_duplicate_statements", not duplicated, ""))
    overlap = set(strengths) & set(gaps)
    checks.append(
        CheckResult(
            "no_contradictory_statements",
            not overlap,
            f"overlap={list(overlap)[:3]}",
        )
    )
    return checks


def evaluate_roadmap(sample: RoadmapSample, value: Any) -> list[CheckResult]:
    checks: list[CheckResult] = []
    title = str(getattr(value, "title", "") or "").strip()
    stages = list(getattr(value, "stages", None) or [])
    tasks = [task for stage in stages for task in (stage.tasks or [])]
    task_titles = [str(task.title).strip() for task in tasks]

    checks.append(CheckResult("title_nonempty", len(title) >= 8, f"title={title!r}"))
    placeholder_titles = [
        t for t in task_titles if any(p in t for p in PLACEHOLDER_PHRASES)
    ]
    checks.append(
        CheckResult(
            "no_placeholder_tasks",
            not placeholder_titles,
            f"placeholders={placeholder_titles[:3]}",
        )
    )
    empty_stages = [s.title for s in stages if not (s.tasks or [])]
    checks.append(
        CheckResult("no_empty_stages", not empty_stages, f"empty={empty_stages}")
    )
    empty_criteria = [t for t in task_titles if len(t) < 6]
    checks.append(
        CheckResult(
            "task_titles_substantive",
            not empty_criteria,
            f"short={empty_criteria[:3]}",
        )
    )
    missing_criteria = [
        str(task.title)
        for task in tasks
        if not str(task.acceptance_criteria or "").strip()
    ]
    checks.append(
        CheckResult(
            "acceptance_criteria_present",
            not missing_criteria,
            f"missing={missing_criteria[:3]}",
        )
    )
    dup_titles = _dedup_overlap(task_titles)
    checks.append(CheckResult("no_duplicate_tasks", not dup_titles, ""))
    keyword_hits = _hits(
        title + "".join(task_titles), sample.input_keywords
    )
    checks.append(
        CheckResult(
            "grounded_in_gap",
            len(keyword_hits) >= 1,
            f"hits={keyword_hits}",
            "semantic_heuristic",
        )
    )
    return checks


EVALUATORS = {
    "resume_parse": evaluate_resume,
    "profile_analysis": evaluate_profile,
    "roadmap_generate": evaluate_roadmap,
}


@dataclass(frozen=True)
class AdjustSample:
    sample_id: str
    payload: dict[str, Any]
    completed_titles: tuple[str, ...]
    completed_criteria: tuple[str, ...]
    input_keywords: tuple[str, ...]


ADJUST_SAMPLES: tuple[AdjustSample, ...] = (
    AdjustSample(
        sample_id="adjust_A",
        payload={
            "target_role": "数据分析师",
            "profile": _PROFILE_A,
            "skill_gap": _gap_snapshot(
                [
                    {
                        "name": "SQL",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "high",
                        "reason": "目标岗位常见要求",
                    },
                    {
                        "name": "可视化",
                        "market_count": 0,
                        "market_share": 0.0,
                        "priority": "medium",
                        "reason": "展示分析结论",
                    },
                ]
            ),
            "current_roadmap": {
                "version": 1,
                "title": "应届生数据分析师三个月成长计划",
                "summary": "以 SQL 与可视化为核心的三阶段计划",
                "progress": {"total": 4, "completed": 1},
                "stages": [
                    {
                        "title": "SQL 基础强化",
                        "goal": "掌握进阶查询",
                        "tasks": [
                            {
                                "title": "完成 SQL 窗口函数专题练习",
                                "status": "completed",
                                "acceptance_criteria": "独立完成 20 道中等难度 SQL 题并整理错题",
                            },
                            {
                                "title": "完成 SQL 多表关联练习",
                                "status": "pending",
                                "acceptance_criteria": "独立完成 10 道多表关联题",
                            },
                        ],
                    },
                    {
                        "title": "可视化产出",
                        "goal": "完成作品集",
                        "tasks": [
                            {
                                "title": "产出一份可视化分析报告",
                                "status": "pending",
                                "acceptance_criteria": "报告包含清洗过程与结论",
                            },
                        ],
                    },
                ],
            },
            "completed_tasks": [
                {
                    "stage": "SQL 基础强化",
                    "title": "完成 SQL 窗口函数专题练习",
                    "acceptance_criteria": "独立完成 20 道中等难度 SQL 题并整理错题",
                    "outcome": "已完成 20 题并整理错题本",
                    "completed_at": "2026-11-27T00:00:00Z",
                }
            ],
        },
        completed_titles=("完成 SQL 窗口函数专题练习",),
        completed_criteria=(
            "独立完成 20 道中等难度 SQL 题并整理错题",
        ),
        input_keywords=("SQL", "可视化", "数据分析师"),
    ),
)


def evaluate_roadmap_adjust(
    sample: AdjustSample, value: Any
) -> list[CheckResult]:
    """Roadmap Adjust 专属门禁：生成门禁 + 已完成任务保护。"""
    base = RoadmapSample(
        sample_id=sample.sample_id,
        payload=sample.payload,
        input_keywords=sample.input_keywords,
    )
    checks = list(evaluate_roadmap(base, value))
    stages = list(getattr(value, "stages", None) or [])
    tasks = [task for stage in stages for task in (stage.tasks or [])]

    for title in sample.completed_titles:
        kept = [task for task in tasks if str(task.title).strip() == title]
        checks.append(
            CheckResult(
                f"completed_task_kept:{title[:12]}",
                bool(kept),
                f"matches={len(kept)}",
            )
        )
    criteria_by_title = {
        str(task.title).strip(): str(task.acceptance_criteria or "").strip()
        for task in tasks
    }
    for title, criteria in zip(
        sample.completed_titles, sample.completed_criteria
    ):
        kept_criteria = criteria_by_title.get(title, "")
        checks.append(
            CheckResult(
                f"completed_criteria_kept:{title[:12]}",
                kept_criteria == criteria,
                f"got={kept_criteria[:40]!r} expected={criteria[:40]!r}",
            )
        )
    return checks


EVALUATORS["roadmap_adjust"] = evaluate_roadmap_adjust


def summarize_checks(checks: list[CheckResult]) -> tuple[bool, list[dict[str, Any]], list[str]]:
    payload = [
        {
            "name": check.name,
            "passed": check.passed,
            "detail": check.detail,
            "check_type": check.check_type,
        }
        for check in checks
    ]
    failures = [check.name for check in checks if not check.passed]
    return (not failures), payload, failures
