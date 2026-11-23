import psycopg
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.integration


def _connect():
    settings = get_settings()
    if not settings.database_url.rstrip("/").endswith("/careerpilot_test"):
        raise RuntimeError("拒绝连接非测试库")
    return psycopg.connect(settings.database_url)


def test_alembic_version_is_head(migrated_db):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            assert cur.fetchone()[0] == "0001_initial"


def test_stage_one_tables_exist(migrated_db):
    expected = {"app_user", "conversation", "message", "agent_run", "agent_trace"}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cur.fetchall()}
    assert expected.issubset(tables)


def test_trace_columns_cover_required_fields(migrated_db):
    required = {
        "run_id",
        "user_id",
        "conversation_id",
        "node_name",
        "status",
        "started_at",
        "finished_at",
        "error_type",
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agent_trace'"
            )
            columns = {row[0] for row in cur.fetchall()}
    assert required.issubset(columns)


def test_user_ownership_columns_and_foreign_keys(migrated_db):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'conversation'"
            )
            assert "user_id" in {row[0] for row in cur.fetchall()}
            cur.execute(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'agent_trace'::regclass"
            )
            constraints = {row[0] for row in cur.fetchall()}
    assert "fk_agent_trace_run" in constraints
    assert "fk_agent_trace_user" in constraints
    assert "fk_agent_trace_conversation" in constraints


def test_jsonb_defaults(migrated_db):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'agent_run' "
                "AND column_name = 'metadata'"
            )
            assert "jsonb" in str(cur.fetchone()[0])
