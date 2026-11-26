from datetime import datetime
from typing import Any

from psycopg.rows import dict_row

from app.db.pool import get_pool


class IndustryTrendsRepository:
    """Read-only reads for deterministic industry trend aggregation."""

    def news_rows(self, since: datetime) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id::text, title, url, source_name,
                           COALESCE(published_at, fetched_at) AS observed_at,
                           industries
                    FROM industry_pulse_article
                    WHERE relevance_status = 'industry_relevant'
                      AND taxonomy_version = 2
                      AND COALESCE(published_at, fetched_at) >= %s
                    ORDER BY observed_at DESC, id
                    LIMIT 2000
                    """,
                    (since,),
                )
                return list(cur.fetchall())

    def job_rows(self, since: datetime) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (j.dedupe_hash)
                           j.id::text, j.title, j.industry, j.location, j.education,
                           j.experience, j.skills,
                           COALESCE(j.posted_at, j.fetched_at) AS observed_at,
                           s.dataset_kind, s.name AS source_name
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id
                    WHERE j.status = 'processed'
                      AND COALESCE(j.posted_at, j.fetched_at) >= %s
                    ORDER BY j.dedupe_hash, j.created_at
                    """,
                    (since,),
                )
                return list(cur.fetchall())


industry_trends_repository = IndustryTrendsRepository()