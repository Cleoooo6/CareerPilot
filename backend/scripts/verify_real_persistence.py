"""Real-model persistence closure: test DB + real services + two synthetic users.

Usage (from backend/):
    .venv/Scripts/python.exe scripts/verify_real_persistence.py

Safety:
- Process-level env only (never touches .env or the Docker mock stack).
- Uses the isolated TEST_DATABASE_URL (must end with /careerpilot_test).
- LLM_MAX_RETRIES=0: exactly one real request per AI step (4 total).
- Aborts on 429 / rate limits. No fallback to mock.
- Cleans only the test DB tables at the end (TRUNCATE).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402

_env = dotenv_values(ROOT.parent / ".env")
TEST_URL = _env.get("TEST_DATABASE_URL", "")
assert TEST_URL.rstrip("/").endswith("careerpilot_test"), (
    "BLOCKED: TEST_DATABASE_URL must target careerpilot_test"
)

os.environ["APP_ENV"] = "development"
os.environ["LLM_MODE"] = "real"
os.environ["LLM_MODEL"] = os.environ.get("LLM_MODEL_OVERRIDE", "glm-5.3-flash")
os.environ["LLM_MAX_RETRIES"] = "0"
os.environ["LLM_MAX_TOKENS"] = os.environ.get("LLM_MAX_TOKENS_OVERRIDE", "16384")
os.environ["LLM_TIMEOUT"] = os.environ.get("LLM_TIMEOUT_OVERRIDE", "240")
os.environ["DATABASE_URL"] = TEST_URL
for _key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY"):
    if _env.get(_key) and not os.environ.get(_key):
        os.environ[_key] = _env[_key]

import psycopg  # noqa: E402

from app.ai.evaluation import (  # noqa: E402
    PROFILE_SAMPLES,
    RESUME_SAMPLES,
    ROADMAP_SAMPLES,
    evaluate_profile,
    evaluate_resume,
    evaluate_roadmap,
    summarize_checks,
)
from app.core.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.llm import LLMError, LLMRateLimitError  # noqa: E402
from app.db.pool import close_pool, open_pool  # noqa: E402
from app.db.profile_repositories import profile_repository  # noqa: E402
from app.db.repositories import user_repository  # noqa: E402
from app.schemas.profile import ProfileAnalysisResult, ProfileData  # noqa: E402
from app.schemas.roadmap import RoadmapTaskUpdateRequest  # noqa: E402
from app.services.profile_service import get_profile_service  # noqa: E402
from app.services.resume_service import get_resume_service  # noqa: E402
from app.services.roadmap_service import get_roadmap_service  # noqa: E402
from tests.resume_fixtures import make_docx  # noqa: E402

TRUNCATE_TABLES = (
    "roadmap_task, roadmap_stage, career_roadmap, profile_revision, "
    "market_job, market_import_batch, market_source, profile_analysis, "
    "resume_parse, ai_call_log, career_profile, agent_trace, agent_run, "
    "message, conversation, app_user, auth_session, auth_token, "
    "industry_pulse_article, industry_pulse_run, industry_feed_source"
)

RESULTS: list[dict] = []


def _log(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _step(step: str, passed: bool, detail: str = "") -> None:
    RESULTS.append({"step": step, "passed": passed, "detail": detail})
    _log({"event": "verify", "step": step, "passed": passed, "detail": detail})


async def main() -> int:
    settings = get_settings()
    _log(
        {
            "event": "config",
            "db": "careerpilot_test",
            "mode": settings.llm_mode,
            "model": settings.llm_model,
            "provider": settings.llm_provider,
            "api_key_configured": bool(settings.llm_api_key),
            "max_retries": settings.llm_max_retries,
            "max_tokens": settings.llm_max_tokens,
            "timeout": settings.llm_timeout,
        }
    )
    if not settings.llm_api_key:
        _log({"event": "blocked", "reason": "LLM_API_KEY 未配置"})
        return 3

    open_pool(settings)
    try:
        with psycopg.connect(TEST_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE")

        user_a = user_repository.ensure_test_user("persist-a")
        user_b = user_repository.ensure_test_user("persist-b")
        uid_a, uid_b = user_a["id"], user_b["id"]

        resume_service = get_resume_service()
        profile_service = get_profile_service()
        roadmap_service = get_roadmap_service()

        # -- 1. Resume upload (real call #1) --------------------------------
        sample_resume = RESUME_SAMPLES[0]
        try:
            row = await resume_service.upload(
                uid_a,
                filename="resume.docx",
                content_type=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                data=make_docx(sample_resume.text),
            )
        except LLMRateLimitError as exc:
            _log({"event": "rate_limited", "detail": str(exc)[:200]})
            return 2
        _step("resume_row_created", True, f"resume_id={row['id']}")
        _step(
            "resume_status_pending_review",
            row["status"] == "pending_review",
            f"status={row['status']}",
        )
        _step(
            "resume_prompt_version_v2",
            row.get("prompt_version") == "resume_parse@v2",
            f"prompt_version={row.get('prompt_version')}",
        )
        _step(
            "resume_content_hash_persisted",
            bool(row.get("content_hash")),
            f"hash={str(row.get('content_hash'))[:12]}…",
        )
        parsed = ProfileData.model_validate(row["parsed_data"])
        quality_pass, checks, failures = summarize_checks(
            evaluate_resume(sample_resume, parsed)
        )
        _step(
            "resume_quality_gates",
            quality_pass,
            json.dumps(
                [
                    c
                    for c in checks
                    if not c["passed"] or c["check_type"] == "semantic_heuristic"
                ][:6],
                ensure_ascii=False,
            ),
        )

        # -- 2. Confirm resume → profile merge (no AI call) -----------------
        confirmed = await resume_service.confirm(
            uid_a, row["id"], sections=["basic", "skills"], draft=None
        )
        _step("resume_confirm_merged", confirmed["data"] is not None)

        # -- 3. Save profile (no AI) -----------------------------------------
        sample_profile = PROFILE_SAMPLES[0]
        await profile_service.save_profile(
            uid_a, ProfileData(**sample_profile.profile)
        )
        revision_version = profile_repository.latest_revision_version(uid_a)
        # confirm(简历合并) 产生 v1，save_profile 产生 v2；分析须关联最新版本。
        _step(
            "profile_revision_created",
            revision_version == 2,
            f"version={revision_version} (confirm v1 + save v2)",
        )

        # -- 4. Profile analysis (real call #2) -------------------------------
        analysis = await profile_service.analyze(uid_a)
        _step(
            "analysis_row_created",
            True,
            f"analysis_id={analysis['id']}",
        )
        _step(
            "analysis_version_linkage",
            analysis.get("source_revision_version") == revision_version
            and analysis.get("prompt_version") == "profile_analysis@v2",
            f"rev={analysis.get('source_revision_version')} "
            f"prompt={analysis.get('prompt_version')}",
        )
        _step(
            "analysis_stale_false",
            analysis.get("stale") is False,
            f"stale={analysis.get('stale')}",
        )
        quality_pass, checks, failures = summarize_checks(
            evaluate_profile(
                sample_profile,
                ProfileAnalysisResult.model_validate(analysis["analysis"]),
            )
        )
        _step(
            "analysis_quality_gates",
            quality_pass,
            json.dumps(failures, ensure_ascii=False),
        )

        # -- 5. Roadmap generate (real call #3) --------------------------------
        roadmap, _reused = await roadmap_service.generate_draft(uid_a, None)
        _step(
            "roadmap_draft_created",
            roadmap.status == "draft",
            f"roadmap_id={roadmap.id} tasks={roadmap.task_total}",
        )
        quality_pass, checks, failures = summarize_checks(
            evaluate_roadmap(ROADMAP_SAMPLES[0], roadmap)
        )
        _step(
            "roadmap_quality_gates",
            quality_pass,
            json.dumps(failures, ensure_ascii=False),
        )

        active = await roadmap_service.confirm(uid_a, roadmap.id)
        _step("roadmap_confirmed_active", active.status == "active")

        first_task = active.stages[0].tasks[0]
        completed_title = first_task.title
        completed_criteria = first_task.acceptance_criteria
        await roadmap_service.update_task(
            uid_a,
            first_task.id,
            status=RoadmapTaskUpdateRequest(
                status="completed", outcome="已完成并记录"
            ).status,
            outcome="已完成并记录",
        )
        _step("roadmap_task_completed", True, f"title={completed_title[:24]}")

        # -- 6. Roadmap adjust (real call #4) ----------------------------------
        draft, _adj = await roadmap_service.adjust_draft(uid_a, active.id)
        _step(
            "adjust_draft_created",
            draft.status == "draft" and draft.id != active.id,
            f"draft_id={draft.id}",
        )
        draft_tasks = [
            (t.title.strip(), t.status, t.acceptance_criteria.strip())
            for stage in draft.stages
            for t in stage.tasks
        ]
        kept = [
            entry
            for entry in draft_tasks
            if entry[0] == completed_title.strip()
        ]
        _step(
            "adjust_completed_task_kept",
            bool(kept) and kept[0][1] == "completed",
            f"kept={kept[:1]}",
        )
        _step(
            "adjust_completed_criteria_kept",
            bool(kept) and kept[0][2] == completed_criteria.strip(),
            f"criteria={kept[0][2][:30] if kept else None!r}",
        )

        # -- 7. Persistence & audit assertions ---------------------------------
        with psycopg.connect(TEST_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT purpose, status, llm_mode, prompt_version, user_id
                    FROM ai_call_log WHERE user_id = %s ORDER BY created_at
                    """,
                    (uid_a,),
                )
                calls_a = cur.fetchall()
                cur.execute(
                    "SELECT count(*) FROM ai_call_log WHERE user_id = %s",
                    (uid_b,),
                )
                calls_b = cur.fetchone()[0]
                cur.execute(
                    "SELECT gap_snapshot FROM career_roadmap WHERE id = %s",
                    (draft.id,),
                )
                gap_snapshot = cur.fetchone()[0]
        expected_purposes = [
            "resume_parse",
            "profile_analysis",
            "roadmap_generate",
            "roadmap_adjust",
        ]
        purposes = [call[0] for call in calls_a]
        _step(
            "ai_call_log_user_a",
            purposes == expected_purposes
            and all(call[1] == "succeeded" and call[2] == "real" for call in calls_a),
            f"purposes={purposes}",
        )
        _step(
            "ai_call_log_versions",
            [call[3] for call in calls_a]
            == [
                "resume_parse@v2",
                "profile_analysis@v2",
                "roadmap_generate@v2",
                "roadmap_adjust@v2",
            ],
            f"versions={[call[3] for call in calls_a]}",
        )
        _step("ai_call_log_user_b_empty", calls_b == 0, f"count={calls_b}")
        _step(
            "adjust_gap_snapshot_has_basis",
            bool((gap_snapshot or {}).get("adjustment_basis")),
            "adjustment_basis present" if gap_snapshot else "no snapshot",
        )

        # -- 8. Cross-user isolation -------------------------------------------
        b_profile = await profile_service.get_profile(uid_b)
        _step("isolation_b_profile_empty", b_profile is None)
        b_roadmap = await roadmap_service.get_current(uid_b)
        _step("isolation_b_roadmap_empty", b_roadmap is None)
        try:
            await roadmap_service.get_roadmap(uid_b, roadmap.id)
            _step("isolation_b_read_a_roadmap", False, "unexpectedly readable")
        except AppError:
            _step("isolation_b_read_a_roadmap", True, "404 as expected")

        # -- 9. Failure must not fake success ----------------------------------
        try:
            await profile_service.analyze(uid_b)
            _step("failure_no_fake_success", False, "empty profile analyze passed")
        except AppError as exc:
            with psycopg.connect(TEST_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*) FROM profile_analysis WHERE user_id=%s",
                        (uid_b,),
                    )
                    b_analyses = cur.fetchone()[0]
            _step(
                "failure_no_fake_success",
                exc.status_code == 409 and b_analyses == 0,
                f"code={exc.code} analyses={b_analyses}",
            )
    finally:
        with psycopg.connect(TEST_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE")
        close_pool()

    passed = sum(1 for r in RESULTS if r["passed"])
    _log(
        {
            "event": "summary",
            "passed": passed,
            "failed": len(RESULTS) - passed,
            "real_calls": 4,
        }
    )
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except LLMError as exc:
        _log({"event": "llm_error", "code": exc.code, "message": str(exc)[:300]})
        raise SystemExit(2)
