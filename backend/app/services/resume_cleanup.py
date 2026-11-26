"""TTL cleanup for temporary resume files.

Only abandoned/transient rows are purged. Records awaiting user review or
already confirmed keep their metadata; the stored file is removed and the
column is blanked so the row stays valid.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from psycopg.rows import dict_row

from app.db.pool import get_pool
from app.services.resume_service import ResumeStorage

logger = logging.getLogger(__name__)

STALE_STATUSES = ("processing", "discarded", "failed")


def purge_expired_resume_files(ttl_hours: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=ttl_hours)
    with get_pool().connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, stored_filename FROM resume_parse "
                "WHERE stored_filename <> '' AND status = ANY(%s) "
                "AND created_at < %s FOR UPDATE",
                (list(STALE_STATUSES), cutoff),
            )
            rows = cur.fetchall()
            if not rows:
                return 0
            cur.execute(
                "UPDATE resume_parse SET stored_filename = '', updated_at = now() "
                "WHERE id = ANY(%s)",
                ([row["id"] for row in rows],),
            )
            names = [row["stored_filename"] for row in rows]
    storage = ResumeStorage()
    for name in names:
        storage.delete(name)
    logger.info("resume_ttl_cleanup removed=%d", len(names))
    return len(names)
