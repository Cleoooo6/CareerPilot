from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.pool import get_pool


class MarketRepository:
    def upsert_source(
        self,
        *,
        name: str,
        source_type: str,
        dataset_kind: str,
        license_note: str,
        base_url: str | None,
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO market_source
                        (id, name, source_type, dataset_kind, license_note, base_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name)
                    DO UPDATE SET source_type = EXCLUDED.source_type,
                                  dataset_kind = EXCLUDED.dataset_kind,
                                  license_note = EXCLUDED.license_note,
                                  base_url = EXCLUDED.base_url,
                                  updated_at = NOW()
                    RETURNING id, name, source_type, dataset_kind, license_note, base_url,
                              created_at, updated_at
                    """,
                    (uuid4(), name, source_type, dataset_kind, license_note, base_url),
                )
                return cur.fetchone()

    def create_batch(self, source_id: UUID, total: int) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO market_import_batch (id, source_id, status, total)
                    VALUES (%s, %s, 'processing', %s)
                    RETURNING id, source_id, status, total, imported, duplicates, failed,
                              error_message, started_at, finished_at
                    """,
                    (uuid4(), source_id, total),
                )
                return cur.fetchone()

    def finish_batch(
        self,
        batch_id: UUID,
        *,
        status: str,
        imported: int,
        duplicates: int,
        failed: int,
        error_message: str | None = None,
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE market_import_batch
                    SET status = %s, imported = %s, duplicates = %s, failed = %s,
                        error_message = %s, finished_at = NOW()
                    WHERE id = %s
                    """,
                    (status, imported, duplicates, failed, error_message, batch_id),
                )

    def find_duplicate(self, dedupe_hash: str) -> UUID | None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM market_job
                    WHERE dedupe_hash = %s AND status = 'processed'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (dedupe_hash,),
                )
                row = cur.fetchone()
                return row[0] if row else None

    def insert_job(
        self,
        *,
        source_id: UUID,
        batch_id: UUID,
        clean: dict[str, Any],
        status: str = "processed",
        error_message: str | None = None,
        duplicate_of: UUID | None = None,
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO market_job
                        (id, source_id, batch_id, external_id, dedupe_hash,
                         raw_payload, status, error_message, duplicate_of,
                         title_raw, title, company, industry, location, education,
                         experience, salary, skills, source_url, posted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, status
                    """,
                    (
                        uuid4(),
                        source_id,
                        batch_id,
                        clean.get("external_id"),
                        clean["dedupe_hash"],
                        Jsonb(clean["raw_payload"]),
                        status,
                        error_message,
                        duplicate_of,
                        clean["title_raw"],
                        clean["title"],
                        clean["company"],
                        clean["industry"],
                        clean["location"],
                        clean["education"],
                        clean["experience"],
                        clean.get("salary"),
                        Jsonb(clean["skills"]),
                        clean.get("source_url"),
                        clean.get("posted_at"),
                    ),
                )
                return cur.fetchone()

    def sources(self) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT name, source_type, dataset_kind, license_note, base_url
                    FROM market_source
                    ORDER BY name
                    """
                )
                return list(cur.fetchall())

    def _where(
        self,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        *,
        table_alias: str = "j",
    ) -> tuple[str, list[Any]]:
        clauses = [f"{table_alias}.status = 'processed'"]
        params: list[Any] = []
        if role:
            clauses.append(f"{table_alias}.title = %s")
            params.append(role)
        if location:
            clauses.append(f"{table_alias}.location = %s")
            params.append(location)
        if dataset_kind in {"real", "synthetic"}:
            clauses.append("s.dataset_kind = %s")
            params.append(dataset_kind)
        return " AND ".join(clauses), params

    def aggregate(
        self, role: str | None, location: str | None, dataset_kind: str
    ) -> dict[str, Any]:
        where, params = self._where(role, location, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT count(*)::int AS total_jobs,
                           count(DISTINCT j.company)::int AS total_companies,
                           count(DISTINCT j.title)::int AS total_roles,
                           count(DISTINCT j.location)::int AS total_locations,
                           min(COALESCE(j.posted_at, j.fetched_at)) AS period_start,
                           max(COALESCE(j.posted_at, j.fetched_at)) AS period_end,
                           max(j.fetched_at) AS updated_at
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id
                    WHERE {where}
                    """,
                    params,
                )
                return cur.fetchone()

    def top_counts(
        self,
        column: str,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if column not in {"title", "company", "location", "education", "experience"}:
            raise ValueError("unsupported column")
        where, params = self._where(role, location, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT j.{column} AS name, count(*)::int AS count
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id
                    WHERE {where}
                    GROUP BY j.{column}
                    ORDER BY count DESC, name
                    LIMIT %s
                    """,
                    [*params, limit],
                )
                return list(cur.fetchall())

    def top_skills(
        self,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        where, params = self._where(role, location, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT skill AS name, count(*)::int AS count
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id,
                         LATERAL jsonb_array_elements_text(j.skills) AS skill
                    WHERE {where}
                    GROUP BY skill
                    ORDER BY count DESC, name
                    LIMIT %s
                    """,
                    [*params, limit],
                )
                return list(cur.fetchall())

    def role_skills(
        self,
        roles: list[str],
        location: str | None,
        dataset_kind: str,
    ) -> dict[str, list[dict[str, Any]]]:
        result = {}
        for role in roles:
            result[role] = self.top_skills(role, location, dataset_kind, limit=5)
        return result

    def distribution(
        self,
        dimension: str,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        return self.top_counts(dimension, role, location, dataset_kind, limit)

    def trends(
        self,
        role: str | None,
        location: str | None,
        dataset_kind: str,
        months: int = 6,
    ) -> list[dict[str, Any]]:
        where, params = self._where(role, location, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT to_char(date_trunc('month', COALESCE(j.posted_at, j.fetched_at)),
                                   'YYYY-MM') AS period,
                           count(*)::int AS count
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id
                    WHERE {where}
                    GROUP BY date_trunc('month', COALESCE(j.posted_at, j.fetched_at))
                    ORDER BY date_trunc('month', COALESCE(j.posted_at, j.fetched_at))
                    LIMIT %s
                    """,
                    [*params, months],
                )
                return list(cur.fetchall())

    def roles(self, dataset_kind: str, limit: int = 30) -> list[str]:
        where, params = self._where(None, None, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT j.title AS name, count(*)::int AS count
                    FROM market_job j
                    JOIN market_source s ON s.id = j.source_id
                    WHERE {where}
                    GROUP BY j.title
                    ORDER BY count DESC, name
                    LIMIT %s
                    """,
                    [*params, limit],
                )
                return [row["name"] for row in cur.fetchall()]

    def matching_sources(
        self, role: str | None, location: str | None, dataset_kind: str
    ) -> list[dict[str, Any]]:
        where, params = self._where(role, location, dataset_kind)
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT s.name, s.source_type, s.dataset_kind,
                                    s.license_note, s.base_url
                    FROM market_source s
                    JOIN market_job j ON j.source_id = s.id
                    WHERE {where}
                    ORDER BY s.name
                    """,
                    params,
                )
                return list(cur.fetchall())


market_repository = MarketRepository()
