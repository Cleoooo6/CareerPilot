"""Real Zhipu API verification for the four Phase C business chains.

Usage (from backend/):
    .venv/Scripts/python.exe scripts/verify_real_ai.py

Safety:
- Reads LLM_* from the project .env; never prints the API key.
- Forces APP_ENV=development and LLM_MODE=real for this process only.
- Uses a no-op audit repository, so no database rows are written.
- Stops on the first LLMError; never falls back to mock or another model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser(
    description="Real Zhipu model verification via the unified AIService"
)
parser.add_argument(
    "--model",
    default="glm-5.3-flash",
    help="官方 Model Code（优先级高于 .env）",
)
parser.add_argument(
    "--minimal",
    action="store_true",
    help="仅执行一次最小结构化输出验证（chat_intent）",
)
parser.add_argument(
    "--max-tokens",
    type=int,
    default=4096,
    help="单次输出预算（需覆盖推理 Token）",
)
parser.add_argument(
    "--only",
    default="",
    help="仅执行指定步骤（逗号分隔，缺省执行全部）",
)
parser.add_argument(
    "--timeout",
    type=int,
    default=None,
    help="覆盖单次请求超时（秒）；缺省沿用 .env 的 LLM_TIMEOUT",
)
parser.add_argument(
    "--reasoning-effort",
    default=None,
    help="覆盖推理强度（如 high）；缺省沿用环境/.env 设置",
)
args = parser.parse_args()

from dotenv import dotenv_values  # noqa: E402

env = dotenv_values(ROOT.parent / ".env")
os.environ["APP_ENV"] = "development"
os.environ["LLM_MODE"] = "real"
# 命令行模型 ID 优先级高于 .env；本轮禁用自动重试，最多一次真实请求。
os.environ["LLM_MODEL"] = args.model
os.environ["LLM_MAX_RETRIES"] = "0"
os.environ["LLM_MAX_TOKENS"] = str(args.max_tokens)
for key in ("LLM_PROVIDER", "LLM_BASE_URL"):
    if env.get(key) and not os.environ.get(key):
        os.environ[key] = env[key]
os.environ["LLM_TIMEOUT"] = env.get("LLM_TIMEOUT", "120")
if args.timeout:
    # 命令行超时覆盖 .env；用于思考型模型的长推理请求。
    os.environ["LLM_TIMEOUT"] = str(args.timeout)
if args.reasoning_effort:
    # 命令行推理强度覆盖 .env；GLM-5.3 系列建议 high。
    os.environ["LLM_REASONING_EFFORT"] = args.reasoning_effort

from app.agents.nodes.intent import IntentResult  # noqa: E402
from app.ai.prompts import (  # noqa: E402
    CHAT_INTENT_SPEC,
    CHAT_REPLY_BOUNDARY,
    CHAT_REPLY_SPECS,
    PROFILE_ANALYSIS_SPEC,
    RESUME_PARSE_SPEC,
    ROADMAP_ADJUST_SPEC,
    ROADMAP_GENERATE_SPEC,
    PromptSpec,
)
from app.ai.service import AIService  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.llm import LLMClient, LLMError, LLMRateLimitError  # noqa: E402
from app.schemas.profile import ProfileAnalysisResult, ProfileData  # noqa: E402
from app.schemas.roadmap import RoadmapDraftLLM  # noqa: E402


class NullRepository:
    def record(self, **kwargs) -> None:  # noqa: ARG002
        return None


RESUME_TEXT = """姓名：林舟
目标岗位：数据分析师
学历：本科
专业：信息管理与信息系统
所在地：上海
毕业时间：2026
学校：虚构大学
技能：Python、SQL、Excel
项目：校园二手交易数据分析（Python 清洗 1.2 万条记录，产出可视化报告）
实习：虚构科技有限公司 数据分析实习生（整理销售数据，制作周报）
证书：无
"""

PROFILE = {
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

settings = get_settings()
client = LLMClient(settings=settings)
ai = AIService(llm_client=client, repository=NullRepository())
USER_ID = uuid4()


def _log(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _meta(step: str, meta, extra: dict | None = None) -> None:
    _log(
        {
            "step": step,
            "event": "ok",
            "request_model": settings.llm_model,
            "model": meta.model,
            "finish_reason": meta.finish_reason,
            "duration_ms": meta.duration_ms,
            "prompt_tokens": meta.usage.prompt_tokens,
            "completion_tokens": meta.usage.completion_tokens,
            "total_tokens": meta.usage.total_tokens,
            **(extra or {}),
        }
    )


def _fail(step: str, exc: LLMError, started: float) -> None:
    _log(
        {
            "step": step,
            "event": "failed",
            "code": exc.code,
            "message": str(exc)[:300],
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
        }
    )


def structured_step(name: str, prompt, schema, user_prompt: str):
    started = time.perf_counter()
    _log({"step": name, "event": "start", "request_model": settings.llm_model})
    try:
        value, meta = ai.structured(
            user_id=USER_ID,
            purpose=name,
            prompt=prompt,
            user_prompt=user_prompt,
            schema=schema,
        )
    except LLMRateLimitError as exc:
        # 限流立即终止全部验证，不做任何继续尝试。
        _fail(name, exc, started)
        raise SystemExit(2) from exc
    except LLMError as exc:
        # 单步失败只记录并跳过该步骤，其余业务链继续验证。
        _fail(name, exc, started)
        return None
    if meta.finish_reason == "length":
        _log(
            {
                "step": name,
                "event": "failed",
                "reason": "finish_reason=length：输出被 max_tokens 截断，判定失败",
                "finish_reason": meta.finish_reason,
                "duration_ms": meta.duration_ms,
            }
        )
        return None
    _meta(name, meta)
    return value


async def chat_reply_step() -> None:

    prompt = PromptSpec(
        key="chat_reply:career_planning",
        version="chat_reply@v1",
        system=f"{CHAT_REPLY_SPECS['career_planning']}\n{CHAT_REPLY_BOUNDARY}",
    )
    question_one = (
        "我目标是数据分析师，本科应届生，Python/SQL 有基础，"
        "帮我规划接下来 3 个月的求职准备。"
    )
    question_two = "如果我每周只能投入 10 小时，怎么调整优先级？"
    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt.system},
        {"role": "user", "content": question_one},
    ]
    started = time.perf_counter()
    _log({"step": "chat_reply_turn_1", "event": "start", "model": settings.llm_model})
    try:
        response = client.chat(messages)
    except LLMError as exc:
        _fail("chat_reply_turn_1", exc, started)
        raise SystemExit(2) from exc
    _log(
        {
            "step": "chat_reply_turn_1",
            "event": "ok",
            "request_model": settings.llm_model,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
            "total_tokens": response.usage.total_tokens,
            "chars": len(response.content),
            "summary": response.content[:160],
        }
    )
    messages.extend(
        [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": question_two},
        ]
    )
    started = time.perf_counter()
    _log({"step": "chat_reply_turn_2", "event": "start", "model": settings.llm_model})
    try:
        second = client.chat(messages)
    except LLMError as exc:
        _fail("chat_reply_turn_2", exc, started)
        raise SystemExit(2) from exc
    _log(
        {
            "step": "chat_reply_turn_2",
            "event": "ok",
            "request_model": settings.llm_model,
            "model": second.model,
            "finish_reason": second.finish_reason,
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
            "total_tokens": second.usage.total_tokens,
            "chars": len(second.content),
            "summary": second.content[:160],
        }
    )


async def main() -> None:
    _log(
        {
            "event": "config",
            "provider": settings.llm_provider,
            "request_model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "api_key_configured": bool(settings.llm_api_key),
            "mode": settings.llm_mode,
            "max_tokens": settings.llm_max_tokens,
            "max_retries": settings.llm_max_retries,
        }
    )
    if not settings.llm_api_key:
        _log({"event": "blocked", "reason": "LLM_API_KEY 未配置"})
        raise SystemExit(3)

    steps = {item.strip() for item in args.only.split(",") if item.strip()}

    def wanted(name: str) -> bool:
        return not steps or name in steps

    if args.minimal:
        if not wanted("chat_intent"):
            _log({"step": "chat_intent", "event": "skipped", "reason": "not in --only"})
            _log({"event": "done", "mode": "minimal", "steps": 0})
            return
        intent = structured_step(
            "chat_intent",
            CHAT_INTENT_SPEC,
            IntentResult,
            "当前用户消息：帮我规划接下来三个月的求职准备",
        )
        if intent is not None:
            _log({"step": "chat_intent", "event": "result", "intent": intent.intent})
        _log({"event": "done", "mode": "minimal", "steps": 1})
        return

    resume = None
    if wanted("resume_parse"):
        resume = structured_step(
            "resume_parse",
            RESUME_PARSE_SPEC,
            ProfileData,
            f"简历文本：\n{RESUME_TEXT}",
        )
        if resume is not None:
            _log(
                {
                    "step": "resume_parse",
                    "event": "result",
                    "name": resume.basic.name,
                    "target_role": resume.goals.target_role,
                    "skills": [item.name for item in resume.skills],
                    "projects": len(resume.projects),
                    "experiences": len(resume.experiences),
                }
            )

    if wanted("profile_analysis"):
        analysis = structured_step(
            "profile_analysis",
            PROFILE_ANALYSIS_SPEC,
            ProfileAnalysisResult,
            "已确认职业画像：" + json.dumps(PROFILE, ensure_ascii=False)[:4000],
        )
        if analysis is not None:
            _log(
                {
                    "step": "profile_analysis",
                    "event": "result",
                    "overview": analysis.overview[:160],
                    "strengths": len(analysis.strengths),
                    "gaps": len(analysis.gaps),
                    "directions": len(analysis.directions),
                }
            )

    if wanted("chat_intent"):
        intent = structured_step(
            "chat_intent",
            CHAT_INTENT_SPEC,
            IntentResult,
            "当前用户消息：帮我规划接下来三个月的求职准备",
        )
        if intent is not None:
            _log({"step": "chat_intent", "event": "result", "intent": intent.intent})

    if wanted("chat_reply"):
        await chat_reply_step()

    gap_snapshot = {
        "target_role": "数据分析师",
        "basis": "general",
        "reference_only": True,
        "matched": [],
        "to_improve": [
            {"name": "SQL", "market_count": 0, "market_share": 0.0, "priority": "high", "reason": "目标岗位常见要求"},
            {"name": "可视化", "market_count": 0, "market_share": 0.0, "priority": "medium", "reason": "展示分析结论"},
        ],
        "not_recorded": [],
        "profile_skills": [{"name": "Python", "proficiency": "熟练", "evidence": "", "source": "", "verification": ""}],
        "meta": {"sample_size": 0, "sample_sufficient": False, "dataset_kinds": [], "updated_at": None, "dataset_kind": "none", "warnings": []},
        "warnings": ["无市场样本，仅供通用建议"],
        "computed_at": "2026-11-26T00:00:00Z",
    }

    roadmap = None
    if wanted("roadmap_generate"):
        roadmap = structured_step(
            "roadmap_generate",
            ROADMAP_GENERATE_SPEC,
            RoadmapDraftLLM,
            json.dumps(
                {"target_role": "数据分析师", "profile": PROFILE, "skill_gap": gap_snapshot},
                ensure_ascii=False,
            )[:12000],
        )
        if roadmap is not None:
            _log(
                {
                    "step": "roadmap_generate",
                    "event": "result",
                    "title": roadmap.title,
                    "stages": len(roadmap.stages),
                    "tasks": sum(len(stage.tasks) for stage in roadmap.stages),
                }
            )

    if roadmap is not None and wanted("roadmap_adjust"):
        adjusted = structured_step(
            "roadmap_adjust",
            ROADMAP_ADJUST_SPEC,
            RoadmapDraftLLM,
            json.dumps(
                {
                    "target_role": "数据分析师",
                    "profile": PROFILE,
                    "skill_gap": gap_snapshot,
                    "current_roadmap": {
                        "version": 1,
                        "title": roadmap.title,
                        "summary": roadmap.summary,
                        "progress": {"total": 6, "completed": 1},
                        "stages": [stage.model_dump(mode="json") for stage in roadmap.stages],
                    },
                    "completed_tasks": [
                        {
                            "stage": roadmap.stages[0].title,
                            "title": roadmap.stages[0].tasks[0].title,
                            "acceptance_criteria": roadmap.stages[0].tasks[0].acceptance_criteria,
                            "outcome": "已完成并记录",
                            "completed_at": "2026-11-26T00:00:00Z",
                        }
                    ],
                },
                ensure_ascii=False,
            )[:16000],
        )
        if adjusted is not None:
            _log(
                {
                    "step": "roadmap_adjust",
                    "event": "result",
                    "title": adjusted.title,
                    "stages": len(adjusted.stages),
                    "tasks": sum(len(stage.tasks) for stage in adjusted.stages),
                    "kept_completed_title": any(
                        task.title == roadmap.stages[0].tasks[0].title
                        for stage in adjusted.stages
                        for task in stage.tasks
                    ),
                }
            )
    _log({"event": "done", "attempted": sorted(steps) or "all"})


if __name__ == "__main__":
    asyncio.run(main())
