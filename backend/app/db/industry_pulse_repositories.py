from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.pool import get_pool
from app.industry_pulse.sources import FeedSource


class IndustryPulseRepository:
    def sync_source(self, source: FeedSource) -> UUID:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO industry_feed_source
                        (id, key, name, industry, industries, region, content_policy,
                         feed_url, homepage_url, license_note, enabled,
                         blocked_reason, last_status, last_error,
                         legacy_industry, taxonomy_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,2)
                    ON CONFLICT (key) DO UPDATE SET
                        name=EXCLUDED.name, industry=EXCLUDED.industry,
                        industries=EXCLUDED.industries, region=EXCLUDED.region,
                        content_policy=EXCLUDED.content_policy,
                        feed_url=EXCLUDED.feed_url, homepage_url=EXCLUDED.homepage_url,
                        license_note=EXCLUDED.license_note, enabled=EXCLUDED.enabled,
                        blocked_reason=EXCLUDED.blocked_reason,
                        taxonomy_version=EXCLUDED.taxonomy_version,
                        last_status=CASE WHEN EXCLUDED.enabled
                            THEN industry_feed_source.last_status ELSE 'blocked' END,
                        last_error=CASE WHEN EXCLUDED.enabled
                            THEN industry_feed_source.last_error ELSE EXCLUDED.blocked_reason END,
                        updated_at=NOW()
                    RETURNING id
                    """,
                    (
                        uuid4(), source.key, source.name, source.industry,
                        Jsonb(list(source.industries or (source.industry,))),
                        source.region, source.content_policy, source.feed_url,
                        source.homepage_url, source.license_note, source.enabled,
                        source.blocked_reason,
                        "never" if source.enabled else "blocked",
                        "" if source.enabled else source.blocked_reason,
                        None,
                    ),
                )
                return cur.fetchone()[0]

    def update_source_status(self, source_id: UUID, *, status: str, error: str = "") -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE industry_feed_source
                    SET last_status=%s, last_error=%s, last_fetched_at=NOW(), updated_at=NOW()
                    WHERE id=%s
                    """,
                    (status, error[:2000], source_id),
                )

    def start_run(self, sources_total: int) -> UUID:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO industry_pulse_run (id,status,sources_total,details) "
                    "VALUES (%s,'running',%s,%s) RETURNING id",
                    (uuid4(), sources_total, Jsonb([])),
                )
                return cur.fetchone()[0]

    def finish_run(
        self, run_id: UUID, *, status: str, sources_ok: int, sources_failed: int,
        articles_fetched: int, articles_inserted: int, articles_duplicates: int,
        error_message: str, details: list[dict[str, Any]],
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE industry_pulse_run
                    SET status=%s, sources_ok=%s, sources_failed=%s,
                        articles_fetched=%s, articles_inserted=%s, articles_duplicates=%s,
                        error_message=%s, details=%s, finished_at=NOW()
                    WHERE id=%s
                    """,
                    (
                        status, sources_ok, sources_failed, articles_fetched,
                        articles_inserted, articles_duplicates, error_message[:2000],
                        Jsonb(details), run_id,
                    ),
                )

    def insert_article(
        self, *, source: FeedSource, source_id: UUID, title: str, url: str,
        canonical_url: str, summary: str, published_at: datetime | None,
        content_hash: str, primary_industry: str | None, industries: list[str],
        relevance_status: str, classification_basis: dict[str, Any],
        tags: list[str],
    ) -> bool:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO industry_pulse_article
                        (id, source_id, source_name, source_url, industry,
                         primary_industry, industries, region, content_policy,
                         title, url, canonical_url, summary, published_at,
                         content_hash, analysis_status, tags, analysis_details,
                         relevance_status, classification_basis, taxonomy_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            'pending',%s,%s,%s,%s,2)
                    ON CONFLICT (canonical_url) DO NOTHING
                    RETURNING id
                    """,
                    (
                        uuid4(), source_id, source.name, source.homepage_url,
                        primary_industry, primary_industry, Jsonb(industries),
                        source.region, source.content_policy, title, url,
                        canonical_url, summary, published_at, content_hash,
                        Jsonb(tags), Jsonb({}), relevance_status,
                        Jsonb(classification_basis),
                    ),
                )
                return cur.fetchone() is not None

    def _where(self, industry: str | None, region: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = [
            "relevance_status = 'industry_relevant'",
            "taxonomy_version = 2",
        ]
        params: list[Any] = []
        if industry:
            clauses.append("industries @> %s::jsonb")
            params.append(Jsonb([industry]))
        if region:
            clauses.append("region = %s")
            params.append(region)
        return "WHERE " + " AND ".join(clauses), params

    def list_articles(
        self, *, industry: str | None, region: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        where, params = self._where(industry, region)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT count(*)::int AS total FROM industry_pulse_article {where}",
                    params,
                )
                total = cur.fetchone()["total"]
                cur.execute(
                    f"""
                    SELECT id, source_id, source_name, source_url, industry,
                           primary_industry, industries, region, content_policy,
                           title, url, canonical_url, summary, published_at,
                           fetched_at, ai_summary, career_impact, tags,
                           analysis_status, analysis_error, analysis_details,
                           analysis_model, analyzed_at, relevance_status,
                           classification_basis, legacy_industry,
                           taxonomy_version, created_at, updated_at
                    FROM industry_pulse_article
                    {where}
                    ORDER BY published_at DESC NULLS LAST, fetched_at DESC, id
                    LIMIT %s OFFSET %s
                    """,
                    [*params, limit, offset],
                )
                return list(cur.fetchall()), total

    def get_article(self, article_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, source_id, source_name, source_url, industry,
                           primary_industry, industries, region, content_policy,
                           title, url, canonical_url, summary, published_at,
                           fetched_at, ai_summary, career_impact, tags,
                           analysis_status, analysis_error, analysis_details,
                           analysis_model, analyzed_at, relevance_status,
                           classification_basis, legacy_industry,
                           taxonomy_version, created_at, updated_at
                    FROM industry_pulse_article WHERE id=%s
                    """,
                    (article_id,),
                )
                return cur.fetchone()

    def update_analysis(
        self, article_id: UUID, *, status: str, ai_summary: str = "",
        career_impact: str = "", tags: list[str] | None = None,
        details: dict[str, Any] | None = None, model: str = "", error: str = "",
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE industry_pulse_article
                    SET analysis_status=%s, ai_summary=%s, career_impact=%s,
                        tags=%s, analysis_details=%s, analysis_model=%s,
                        analysis_error=%s,
                        analyzed_at=CASE WHEN %s='analyzed' THEN NOW() ELSE analyzed_at END,
                        updated_at=NOW()
                    WHERE id=%s
                    RETURNING id, source_id, source_name, source_url, industry,
                              primary_industry, industries, region, content_policy,
                              title, url, canonical_url, summary, published_at,
                              fetched_at, ai_summary, career_impact, tags,
                              analysis_status, analysis_error, analysis_details,
                              analysis_model, analyzed_at, relevance_status,
                              classification_basis, legacy_industry,
                              taxonomy_version, created_at, updated_at
                    """,
                    (
                        status, ai_summary, career_impact, Jsonb(tags or []),
                        Jsonb(details or {}), model, error[:2000], status, article_id,
                    ),
                )
                return cur.fetchone()

    def sources(self) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT key, name, industry, industries, region, content_policy,
                           feed_url, homepage_url, license_note, enabled,
                           blocked_reason, last_status, last_error, last_fetched_at,
                           legacy_industry, taxonomy_version
                    FROM industry_feed_source ORDER BY region, industry, name
                    """
                )
                return list(cur.fetchall())

    def article_counts_by_industry(self) -> dict[str, int]:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value AS industry, count(*)::int FROM industry_pulse_article, "
                    "LATERAL jsonb_array_elements_text(industries) AS x(value) "
                    "WHERE relevance_status = 'industry_relevant' "
                    "AND taxonomy_version = 2 "
                    "GROUP BY value"
                )
                return {row[0]: row[1] for row in cur.fetchall()}

    def preview_articles(self) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, title, summary, industry, primary_industry,
                           industries, relevance_status, taxonomy_version, fetched_at
                    FROM industry_pulse_article
                    ORDER BY fetched_at, id
                    """
                )
                return list(cur.fetchall())

    def latest_run(self) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, status, started_at, finished_at, sources_total,
                           sources_ok, sources_failed, articles_fetched,
                           articles_inserted, articles_duplicates, error_message,
                           details, created_at
                    FROM industry_pulse_run ORDER BY started_at DESC LIMIT 1
                    """
                )
                return cur.fetchone()


industry_pulse_repository = IndustryPulseRepository()