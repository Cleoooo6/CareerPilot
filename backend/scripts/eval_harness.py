"""Evaluation Harness v0 runner.

Runs fixed synthetic samples through the unified AIService against one or
more real models, scoring schema validation and content quality separately.

Usage (real, controlled):
    .venv/Scripts/python.exe scripts/eval_harness.py \
        --models glm-4.7-flash,glm-5.3-flash --chains profile,roadmap \
        --max-tokens 8192 --timeout 240

Safety:
- Process-level env only; never touches .env or the running Docker stack.
- LLM_MAX_RETRIES=0: exactly one request per (model, chain, sample).
- Rate limit (429) aborts the remaining experiments for that model only.
- No retries on schema failure, timeout, or truncation.
- Results append to docs/eval/results.jsonl (machine readable).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser(description="Model/prompt evaluation harness")
parser.add_argument("--models", default="glm-4.7-flash,glm-5.3-flash")
parser.add_argument("--chains", default="profile,roadmap")
parser.add_argument("--samples", default="A,B", help="每个链路使用的样本编号")
parser.add_argument("--max-tokens", type=int, default=8192)
parser.add_argument("--timeout", type=int, default=240)
parser.add_argument("--reasoning-effort", default=None)
args = parser.parse_args()

from dotenv import dotenv_values  # noqa: E402

env = dotenv_values(ROOT.parent / ".env")
os.environ["APP_ENV"] = "development"
os.environ["LLM_MODE"] = "real"
os.environ["LLM_MAX_RETRIES"] = "0"
os.environ["LLM_MAX_TOKENS"] = str(args.max_tokens)
for key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY"):
    if env.get(key) and not os.environ.get(key):
        os.environ[key] = env[key]
os.environ["LLM_TIMEOUT"] = str(args.timeout)
if args.reasoning_effort:
    os.environ["LLM_REASONING_EFFORT"] = args.reasoning_effort

from pydantic import ValidationError  # noqa: E402

from app.ai.evaluation import (  # noqa: E402
    ADJUST_SAMPLES,
    EVALUATORS,
    HARNESS_VERSION,
    PROFILE_SAMPLES,
    RESUME_SAMPLES,
    ROADMAP_SAMPLES,
    EvaluationRecord,
    summarize_checks,
)
from app.ai.prompts import (  # noqa: E402
    PROFILE_ANALYSIS_SPEC,
    RESUME_PARSE_SPEC,
    ROADMAP_ADJUST_SPEC,
    ROADMAP_GENERATE_SPEC,
)
from app.ai.service import AIService  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.llm import LLMClient, LLMError, LLMRateLimitError  # noqa: E402
from app.schemas.profile import ProfileAnalysisResult, ProfileData  # noqa: E402
from app.schemas.roadmap import RoadmapDraftLLM  # noqa: E402

RESULT_DIR = ROOT.parent / "docs" / "eval"
RESULT_FILE = RESULT_DIR / "results.jsonl"

CHAIN_CONFIG = {
    "resume": {
        "purpose": "resume_parse",
        "spec": RESUME_PARSE_SPEC,
        "schema": ProfileData,
        "samples": RESUME_SAMPLES,
        "user_prompt": lambda sample: f"简历文本：\n{sample.text}",
    },
    "profile": {
        "purpose": "profile_analysis",
        "spec": PROFILE_ANALYSIS_SPEC,
        "schema": ProfileAnalysisResult,
        "samples": PROFILE_SAMPLES,
        "user_prompt": lambda sample: (
            "已确认职业画像："
            + json.dumps(sample.profile, ensure_ascii=False)[:4000]
        ),
    },
    "roadmap": {
        "purpose": "roadmap_generate",
        "spec": ROADMAP_GENERATE_SPEC,
        "schema": RoadmapDraftLLM,
        "samples": ROADMAP_SAMPLES,
        "user_prompt": lambda sample: json.dumps(
            sample.payload, ensure_ascii=False
        )[:12000],
    },
    "adjust": {
        "purpose": "roadmap_adjust",
        "spec": ROADMAP_ADJUST_SPEC,
        "schema": RoadmapDraftLLM,
        "samples": ADJUST_SAMPLES,
        "user_prompt": lambda sample: json.dumps(
            sample.payload, ensure_ascii=False
        )[:16000],
    },
}


class NullRepository:
    def record(self, **kwargs) -> None:  # noqa: ARG002
        return None


def _log(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _chain_summary(chain: str, value) -> dict:
    if chain == "resume":
        return {
            "name": value.basic.name,
            "target_role": value.goals.target_role,
            "skills": [item.name for item in value.skills],
            "projects": len(value.projects),
            "experiences": len(value.experiences),
        }
    if chain == "profile":
        return {
            "overview": str(value.overview)[:200],
            "strengths": len(value.strengths),
            "gaps": len(value.gaps),
            "directions": len(value.directions),
        }
    return {
        "title": value.title,
        "stages": len(value.stages),
        "tasks": sum(len(stage.tasks) for stage in value.stages),
    }


def _sample_for(chain: str, letter: str):
    samples = CHAIN_CONFIG[chain]["samples"]
    for sample in samples:
        if sample.sample_id.endswith(f"_{letter}"):
            return sample
    raise SystemExit(f"sample {chain}_{letter} not found")


async def run_model(model: str, chains: list[str], letters: list[str]) -> list[dict]:
    # 每个模型切换前清空 settings 缓存，确保 LLMClient 读取到当前模型。
    os.environ["LLM_MODEL"] = model
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.llm_model == model
    client = LLMClient(settings=settings)
    ai = AIService(llm_client=client, repository=NullRepository())
    user_id = uuid4()
    records: list[dict] = []
    aborted = False

    for chain in chains:
        if aborted:
            break
        config = CHAIN_CONFIG[chain]
        for letter in letters:
            if aborted:
                break
            sample = _sample_for(chain, letter)
            sample_id = f"{chain}_{letter}"
            record = EvaluationRecord(
                recorded_at=datetime.now(UTC).isoformat(),
                harness_version=HARNESS_VERSION,
                mode="real",
                model=model,
                chain=config["purpose"],
                sample_id=sample_id,
                prompt_key=config["spec"].key,
                prompt_version=config["spec"].version,
            )
            _log(
                {
                    "event": "start",
                    "model": model,
                    "chain": config["purpose"],
                    "sample": sample_id,
                    "prompt_version": config["spec"].version,
                }
            )
            started = time.perf_counter()
            value = None
            try:
                value, meta = await asyncio.to_thread(
                    ai.structured,
                    user_id=user_id,
                    purpose=f"eval_{config['purpose']}",
                    prompt=config["spec"],
                    user_prompt=config["user_prompt"](sample),
                    schema=config["schema"],
                )
                record.duration_ms = meta.duration_ms
                record.prompt_tokens = meta.usage.prompt_tokens
                record.completion_tokens = meta.usage.completion_tokens
                record.total_tokens = meta.usage.total_tokens
                record.finish_reason = meta.finish_reason
                record.schema_pass = True
            except LLMRateLimitError as exc:
                record.error_code = exc.code or "LLM_RATE_LIMIT"
                record.duration_ms = max(
                    0, int((time.perf_counter() - started) * 1000)
                )
                record.failure_reasons.append("rate_limited")
                records.append(record.to_json())
                _log({"event": "rate_limited", "model": model, "detail": str(exc)[:200]})
                aborted = True
                break
            except LLMError as exc:
                record.error_code = exc.code
                record.duration_ms = max(
                    0, int((time.perf_counter() - started) * 1000)
                )
                record.failure_reasons.append("llm_error")
                records.append(record.to_json())
                _log(
                    {
                        "event": "llm_error",
                        "model": model,
                        "chain": config["purpose"],
                        "sample": sample_id,
                        "code": exc.code,
                        "message": str(exc)[:200],
                    }
                )
                continue
            except ValidationError as exc:
                record.error_code = "LLM_SCHEMA_ERROR"
                record.schema_errors = [str(exc)[:400]]
                record.failure_reasons.append("schema_error")
                records.append(record.to_json())
                continue

            if record.finish_reason == "length":
                record.error_code = "LLM_OUTPUT_TRUNCATED"
                record.failure_reasons.append("truncated")
                records.append(record.to_json())
                _log(
                    {
                        "event": "truncated",
                        "model": model,
                        "chain": config["purpose"],
                        "sample": sample_id,
                    }
                )
                continue

            evaluator = EVALUATORS[config["purpose"]]
            quality_pass, checks, failures = summarize_checks(evaluator(sample, value))
            record.quality_pass = quality_pass
            record.quality_checks = checks
            record.failure_reasons.extend(failures)
            record.summary = _chain_summary(chain, value)
            record.output = _chain_summary(chain, value)
            records.append(record.to_json())
            _log(
                {
                    "event": "evaluated",
                    "model": model,
                    "chain": config["purpose"],
                    "sample": sample_id,
                    "schema_pass": record.schema_pass,
                    "quality_pass": quality_pass,
                    "failures": failures,
                    "duration_ms": record.duration_ms,
                    "total_tokens": record.total_tokens,
                }
            )
    return records


async def main() -> int:
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    chains = [c.strip() for c in args.chains.split(",") if c.strip()]
    letters = [s.strip().upper() for s in args.samples.split(",") if s.strip()]
    for chain in chains:
        if chain not in CHAIN_CONFIG:
            raise SystemExit(f"unknown chain: {chain}")
    settings = get_settings()
    _log(
        {
            "event": "harness_config",
            "provider": settings.llm_provider,
            "base_url": settings.llm_base_url,
            "api_key_configured": bool(settings.llm_api_key),
            "models": models,
            "chains": chains,
            "samples": letters,
            "max_tokens": args.max_tokens,
            "timeout": args.timeout,
            "max_retries": 0,
            "harness_version": HARNESS_VERSION,
        }
    )
    if not settings.llm_api_key:
        _log({"event": "blocked", "reason": "LLM_API_KEY 未配置"})
        return 3

    all_records: list[dict] = []
    for model in models:
        records = await run_model(model, chains, letters)
        all_records.extend(records)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with RESULT_FILE.open("a", encoding="utf-8") as handle:
        for record in all_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    _log(
        {
            "event": "summary",
            "results_file": str(RESULT_FILE),
            "records": len(all_records),
            "pass_both": sum(
                1 for r in all_records if r["schema_pass"] and r["quality_pass"]
            ),
            "schema_only": sum(
                1 for r in all_records if r["schema_pass"] and not r["quality_pass"]
            ),
            "failed": sum(1 for r in all_records if not r["schema_pass"]),
        }
    )
    for record in all_records:
        _log(
            {
                "event": "record",
                "model": record["model"],
                "chain": record["chain"],
                "sample": record["sample_id"],
                "schema_pass": record["schema_pass"],
                "quality_pass": record["quality_pass"],
                "error_code": record["error_code"],
                "failure_reasons": record["failure_reasons"],
                "duration_ms": record["duration_ms"],
                "total_tokens": record["total_tokens"],
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
