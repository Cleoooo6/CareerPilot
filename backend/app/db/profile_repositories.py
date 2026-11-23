from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.pool import get_pool


class ProfileRepository:
    def get(self, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, data, created_at, updated_at
                    FROM career_profile
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return cur.fetchone()

    def get_data(self, user_id: UUID) -> dict[str, Any] | None:
        profile = self.get(user_id)
        return profile["data"] if profile else None

    def upsert(
        self,
        user_id: UUID,
        data: dict[str, Any],
        change_source: str = "manual",
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO career_profile (id, user_id, data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    RETURNING id, user_id, data, created_at, updated_at
                    """,
                    (uuid4(), user_id, Jsonb(data)),
                )
                profile = cur.fetchone()
                cur.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1 AS version
                    FROM profile_revision
                    WHERE profile_id = %s
                    """,
                    (profile["id"],),
                )
                version = cur.fetchone()["version"]
                cur.execute(
                    """
                    INSERT INTO profile_revision
                        (id, user_id, profile_id, version, data, change_source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        user_id,
                        profile["id"],
                        version,
                        Jsonb(data),
                        change_source,
                    ),
                )
                return profile

    def list_revisions(
        self, user_id: UUID, limit: int = 20
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, profile_id, version, change_source, created_at
                    FROM profile_revision
                    WHERE user_id = %s
                    ORDER BY version DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return list(cur.fetchall())

    def get_revision(
        self, user_id: UUID, revision_id: UUID
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, profile_id, version, data, change_source,
                           created_at
                    FROM profile_revision
                    WHERE id = %s AND user_id = %s
                    """,
                    (revision_id, user_id),
                )
                return cur.fetchone()

    def delete(self, user_id: UUID) -> bool:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM career_profile WHERE user_id = %s RETURNING id",
                    (user_id,),
                )
                return cur.fetchone() is not None

    def create_analysis(
        self,
        user_id: UUID,
        profile_id: UUID,
        provider: str,
        model: str,
        llm_mode: str,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO profile_analysis
                        (id, user_id, profile_id, provider, model, llm_mode, analysis)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, user_id, profile_id, provider, model, llm_mode,
                              analysis, created_at
                    """,
                    (
                        uuid4(),
                        user_id,
                        profile_id,
                        provider,
                        model,
                        llm_mode,
                        Jsonb(analysis),
                    ),
                )
                return cur.fetchone()

    def list_analyses(
        self, user_id: UUID, limit: int = 20
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, profile_id, provider, model, llm_mode,
                           analysis, created_at
                    FROM profile_analysis
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return list(cur.fetchall())

    def get_analysis(
        self, user_id: UUID, analysis_id: UUID
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, profile_id, provider, model, llm_mode,
                           analysis, created_at
                    FROM profile_analysis
                    WHERE id = %s AND user_id = %s
                    """,
                    (analysis_id, user_id),
                )
                return cur.fetchone()


class ResumeRepository:
    def create(
        self,
        user_id: UUID,
        *,
        original_filename: str,
        stored_filename: str,
        file_size: int,
        mime_type: str,
        parse_mode: str,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO resume_parse
                        (id, user_id, original_filename, stored_filename, file_size,
                         mime_type, status, parse_mode, provider, model)
                    VALUES (%s, %s, %s, %s, %s, %s, 'processing', %s, %s, %s)
                    RETURNING id, user_id, original_filename, stored_filename,
                              file_size, mime_type, status, parse_mode, provider,
                              model, parsed_data, text_length, error_type,
                              error_message, created_at, updated_at
                    """,
                    (
                        uuid4(),
                        user_id,
                        original_filename,
                        stored_filename,
                        file_size,
                        mime_type,
                        parse_mode,
                        provider,
                        model,
                    ),
                )
                return cur.fetchone()

    def get(self, user_id: UUID, resume_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, original_filename, stored_filename, file_size,
                           mime_type, status, parse_mode, provider, model,
                           parsed_data, text_length, error_type, error_message,
                           created_at, updated_at
                    FROM resume_parse
                    WHERE id = %s AND user_id = %s
                    """,
                    (resume_id, user_id),
                )
                return cur.fetchone()

    def list_for_user(
        self, user_id: UUID, limit: int = 20
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, original_filename, file_size, mime_type,
                           status, parse_mode, provider, model, parsed_data,
                           text_length, error_type, error_message,
                           created_at, updated_at
                    FROM resume_parse
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return list(cur.fetchall())

    def update_parsed(
        self,
        user_id: UUID,
        resume_id: UUID,
        parsed_data: dict[str, Any],
        text_length: int,
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE resume_parse
                    SET parsed_data = %s, text_length = %s, status = 'pending_review',
                        error_type = NULL, error_message = NULL, updated_at = NOW()
                    WHERE id = %s AND user_id = %s AND status = 'processing'
                    RETURNING id, user_id, original_filename, stored_filename,
                              file_size, mime_type, status, parse_mode, provider,
                              model, parsed_data, text_length, error_type,
                              error_message, created_at, updated_at
                    """,
                    (Jsonb(parsed_data), text_length, resume_id, user_id),
                )
                return cur.fetchone()

    def update_draft(
        self, user_id: UUID, resume_id: UUID, parsed_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE resume_parse
                    SET parsed_data = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s AND status = 'pending_review'
                    RETURNING id, user_id, original_filename, stored_filename,
                              file_size, mime_type, status, parse_mode, provider,
                              model, parsed_data, text_length, error_type,
                              error_message, created_at, updated_at
                    """,
                    (Jsonb(parsed_data), resume_id, user_id),
                )
                return cur.fetchone()

    def mark_failed(
        self, user_id: UUID, resume_id: UUID, error_type: str, error_message: str
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE resume_parse
                    SET status = 'failed', error_type = %s, error_message = %s,
                        updated_at = NOW()
                    WHERE id = %s AND user_id = %s AND status = 'processing'
                    """,
                    (error_type, error_message, resume_id, user_id),
                )

    def set_status(
        self, user_id: UUID, resume_id: UUID, status: str
    ) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE resume_parse
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s AND status = 'pending_review'
                    RETURNING id, user_id, original_filename, stored_filename,
                              file_size, mime_type, status, parse_mode, provider,
                              model, parsed_data, text_length, error_type,
                              error_message, created_at, updated_at
                    """,
                    (status, resume_id, user_id),
                )
                return cur.fetchone()


profile_repository = ProfileRepository()
resume_repository = ResumeRepository()
