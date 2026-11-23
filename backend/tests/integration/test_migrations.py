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
            assert cur.fetchone()[0] == "0006_roadmap_concurrency"


def test_stage_three_tables_exist(migrated_db):
    expected = {"career_profile", "resume_parse", "profile_analysis"}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cur.fetchall()}
    assert expected.issubset(tables)


def test_stage_four_market_tables_exist(migrated_db):
    expected = {"market_source", "market_import_batch", "market_job"}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cur.fetchall()}
    assert expected.issubset(tables)


def test_stage_four_market_job_columns(migrated_db):
    required = {
        "source_id",
        "batch_id",
        "external_id",
        "title",
        "company",
        "location",
        "skills",
        "raw_payload",
        "dedupe_hash",
        "status",
        "duplicate_of",
        "posted_at",
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'market_job'"
            )
            columns = {row[0] for row in cur.fetchall()}
    assert required.issubset(columns)


def test_stage_four_point_five_profile_revision_table(migrated_db):
    required = {
        "id",
        "user_id",
        "profile_id",
        "version",
        "data",
        "change_source",
        "created_at",
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'profile_revision'"
            )
            columns = {row[0] for row in cur.fetchall()}
    assert required.issubset(columns)


def test_stage_five_roadmap_tables_exist(migrated_db):
    expected = {"career_roadmap", "roadmap_stage", "roadmap_task"}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cur.fetchall()}
    assert expected.issubset(tables)


def test_stage_five_roadmap_columns(migrated_db):
    required = {
        "career_roadmap": {
            "user_id",
            "target_role",
            "status",
            "version",
            "gap_snapshot",
            "generation_mode",
            "provider",
            "model",
            "confirmed_at",
        },
        "roadmap_stage": {
            "roadmap_id",
            "position",
            "title",
            "goal",
            "duration",
            "priority",
        },
        "roadmap_task": {
            "roadmap_id",
            "stage_id",
            "position",
            "title",
            "description",
            "task_type",
            "priority",
            "estimated_time",
            "acceptance_criteria",
            "status",
            "completed_at",
            "outcome",
        },
    }
    with _connect() as conn:
        with conn.cursor() as cur:
            for table, columns in required.items():
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s",
                    (table,),
                )
                actual = {row[0] for row in cur.fetchall()}
                assert columns.issubset(actual)


def test_stage_five_single_active_roadmap_index(migrated_db):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'career_roadmap'"
            )
            indexes = {row[0] for row in cur.fetchall()}
    assert "uq_career_roadmap_active" in indexes


def test_stage_five_point_one_single_draft_index(migrated_db):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'career_roadmap'"
            )
            indexes = {row[0] for row in cur.fetchall()}
    assert "uq_career_roadmap_draft" in indexes


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
