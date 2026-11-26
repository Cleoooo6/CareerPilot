"""pytest 配置：所有集成测试只使用独立测试库。"""
import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
_ENV = dotenv_values(PROJECT_ROOT / ".env")
_TEST_URL = os.getenv("TEST_DATABASE_URL") or _ENV.get("TEST_DATABASE_URL")

if not _TEST_URL:
    raise RuntimeError("缺少 TEST_DATABASE_URL；测试必须使用独立测试库")
if not _TEST_URL.rstrip("/").endswith("/careerpilot_test"):
    raise RuntimeError("拒绝运行：TEST_DATABASE_URL 不是 careerpilot_test")

os.environ["DATABASE_URL"] = _TEST_URL
os.environ["TEST_DATABASE_URL"] = _TEST_URL
os.environ["APP_ENV"] = "test"
os.environ["LLM_MODE"] = "mock"
os.environ["LLM_API_KEY"] = ""
# Explicit test-only identity/transport compatibility for the isolated harness.
os.environ["AUTH_TEST_MODE"] = "true"
os.environ["AUTH_COOKIE_SECURE"] = "false"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated_db() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-x",
            f"db_url={_TEST_URL}",
            "upgrade",
            "head",
        ],
        cwd=BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def clean_db(migrated_db: None) -> None:
    with psycopg.connect(_TEST_URL) as conn:
        if not conn.info.dbname.endswith("_test"):
            raise RuntimeError("拒绝在非测试库执行 TRUNCATE")
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE roadmap_task, roadmap_stage, career_roadmap, "
                "profile_revision, market_job, market_import_batch, "
                "market_source, profile_analysis, resume_parse, career_profile, "
                "agent_trace, agent_run, message, conversation, app_user, "
                "auth_session, auth_token, "
                "industry_pulse_article, industry_pulse_run, industry_feed_source "
                "RESTART IDENTITY CASCADE"
            )


@pytest.fixture()
def client(clean_db: None):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
