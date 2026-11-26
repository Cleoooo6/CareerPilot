"""Resume temporary-file TTL cleanup."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.services.resume_cleanup import purge_expired_resume_files
from app.services.resume_service import ResumeStorage

pytestmark = pytest.mark.integration

TEST_URL = os.environ["TEST_DATABASE_URL"]


def _insert(user_id, stored_name: str, status: str, created_at: datetime) -> uuid.UUID:
    resume_id = uuid.uuid4()
    with psycopg.connect(TEST_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO resume_parse (id, user_id, original_filename, "
                "stored_filename, file_size, mime_type, status, parse_mode, "
                "provider, model, created_at) VALUES "
                "(%s, %s, 'cv.pdf', %s, 8, 'application/pdf', %s, 'mock', "
                "'mock', 'mock', %s)",
                (resume_id, user_id, stored_name, status, created_at),
            )
    return resume_id


def _stored(conn, resume_id: uuid.UUID) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stored_filename FROM resume_parse WHERE id = %s", (resume_id,)
        )
        return cur.fetchone()[0]


def test_purges_only_stale_transient_resume_files(client):
    storage = ResumeStorage()
    old = datetime.now(UTC) - timedelta(hours=48)
    fresh = datetime.now(UTC) - timedelta(hours=1)

    user_id = uuid.uuid4()
    with psycopg.connect(TEST_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_user (id, external_id, display_name) "
                "VALUES (%s, %s, 'TTL')",
                (user_id, f"ttl-{user_id}"),
            )

    stale_processing = storage.save(b"stale-processing", ".pdf")
    stale_discarded = storage.save(b"stale-discarded", ".pdf")
    stale_review = storage.save(b"stale-review", ".pdf")
    fresh_processing = storage.save(b"fresh-processing", ".pdf")

    stale_id = _insert(user_id, stale_processing, "processing", old)
    discarded_id = _insert(user_id, stale_discarded, "discarded", old)
    review_id = _insert(user_id, stale_review, "pending_review", old)
    fresh_id = _insert(user_id, fresh_processing, "processing", fresh)

    removed = purge_expired_resume_files(24)

    assert removed == 2
    assert not (storage.base / stale_processing).exists()
    assert not (storage.base / stale_discarded).exists()
    assert (storage.base / stale_review).exists()
    assert (storage.base / fresh_processing).exists()

    with psycopg.connect(TEST_URL) as conn:
        assert _stored(conn, stale_id) == ""
        assert _stored(conn, discarded_id) == ""
        assert _stored(conn, review_id) == stale_review
        assert _stored(conn, fresh_id) == fresh_processing


def test_cleanup_is_idempotent(client):
    assert purge_expired_resume_files(24) == 0
    assert purge_expired_resume_files(24) == 0
