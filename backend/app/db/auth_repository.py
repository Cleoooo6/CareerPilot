"""Auth persistence: accounts, sessions and one-time tokens."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row

from app.db.pool import get_pool

USER_COLUMNS = (
    "id, external_id, display_name, email, password_hash, status, "
    "email_verified_at, is_demo, created_at, updated_at"
)
_USER_SELECT = ", ".join(f"u.{column.strip()}" for column in USER_COLUMNS.split(","))


class AuthRepository:
    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> dict[str, Any]:
        user_id = uuid4()
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    INSERT INTO app_user
                        (id, external_id, display_name, email, password_hash,
                         status, is_demo)
                    VALUES (%s, %s, %s, %s, %s, 'active', false)
                    RETURNING {USER_COLUMNS}
                    """,
                    (user_id, str(user_id), display_name, email, password_hash),
                )
                return cur.fetchone()

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT {USER_COLUMNS} FROM app_user "
                    "WHERE lower(email) = lower(%s) AND email IS NOT NULL",
                    (email,),
                )
                return cur.fetchone()

    def get_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT {USER_COLUMNS} FROM app_user WHERE id = %s",
                    (user_id,),
                )
                return cur.fetchone()

    def get_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT {USER_COLUMNS} FROM app_user WHERE external_id = %s",
                    (external_id,),
                )
                return cur.fetchone()

    def create_session(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        session_id = uuid4()
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO auth_session
                        (id, user_id, token_hash, expires_at, user_agent, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, user_id, created_at, expires_at, revoked_at
                    """,
                    (session_id, user_id, token_hash, expires_at, user_agent, ip_address),
                )
                return cur.fetchone()

    def get_session_user(self, token_hash: str) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT s.id AS session_id, s.expires_at, s.last_seen_at,
                           {_USER_SELECT}
                    FROM auth_session s
                    JOIN app_user u ON u.id = s.user_id
                    WHERE s.token_hash = %s
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.status = 'active'
                    """,
                    (token_hash,),
                )
                return cur.fetchone()

    def touch_session(self, session_id: UUID) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE auth_session SET last_seen_at = now() WHERE id = %s",
                    (session_id,),
                )

    def revoke_session(self, token_hash: str) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE auth_session SET revoked_at = now() "
                    "WHERE token_hash = %s AND revoked_at IS NULL",
                    (token_hash,),
                )

    def revoke_all_sessions(self, user_id: UUID) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE auth_session SET revoked_at = now() "
                    "WHERE user_id = %s AND revoked_at IS NULL",
                    (user_id,),
                )

    def create_token(
        self,
        *,
        user_id: UUID,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_token
                        (id, user_id, purpose, token_hash, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (uuid4(), user_id, purpose, token_hash, expires_at),
                )

    def consume_token(self, token_hash: str, purpose: str) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE auth_token
                    SET consumed_at = now()
                    WHERE token_hash = %s
                      AND purpose = %s
                      AND consumed_at IS NULL
                      AND expires_at > now()
                    RETURNING id, user_id, purpose
                    """,
                    (token_hash, purpose),
                )
                return cur.fetchone()

    def set_password(self, user_id: UUID, password_hash: str) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_user SET password_hash = %s, updated_at = now() "
                    "WHERE id = %s",
                    (password_hash, user_id),
                )

    def mark_email_verified(self, user_id: UUID) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_user SET email_verified_at = now(), updated_at = now() "
                    "WHERE id = %s",
                    (user_id,),
                )

    def set_status(self, user_id: UUID, status: str) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_user SET status = %s, updated_at = now() WHERE id = %s",
                    (status, user_id),
                )

    def export_user(self, user_id: UUID) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(f"SELECT {USER_COLUMNS} FROM app_user WHERE id = %s", (user_id,))
                user = cur.fetchone() or {}
                user.pop("password_hash", None)
                cur.execute(
                    "SELECT id, data, created_at, updated_at FROM career_profile WHERE user_id = %s",
                    (user_id,),
                )
                profile = cur.fetchone()
                cur.execute(
                    "SELECT id, version, change_source, data, created_at "
                    "FROM profile_revision WHERE user_id = %s ORDER BY version",
                    (user_id,),
                )
                revisions = list(cur.fetchall())
                cur.execute(
                    "SELECT id, title, created_at, updated_at FROM conversation "
                    "WHERE user_id = %s ORDER BY created_at",
                    (user_id,),
                )
                conversations = list(cur.fetchall())
                cur.execute(
                    "SELECT m.id, m.conversation_id, m.role, m.content, m.created_at "
                    "FROM message m JOIN conversation c ON c.id = m.conversation_id "
                    "WHERE c.user_id = %s ORDER BY m.created_at",
                    (user_id,),
                )
                messages = list(cur.fetchall())
                cur.execute(
                    "SELECT id, provider, model, llm_mode, analysis, created_at "
                    "FROM profile_analysis WHERE user_id = %s ORDER BY created_at",
                    (user_id,),
                )
                analyses = list(cur.fetchall())
                cur.execute(
                    "SELECT id, target_role, status, version, title, summary, "
                    "gap_snapshot, generation_mode, provider, model, created_at, "
                    "confirmed_at FROM career_roadmap WHERE user_id = %s ORDER BY created_at",
                    (user_id,),
                )
                roadmaps = list(cur.fetchall())
                cur.execute(
                    "SELECT id, original_filename, file_size, mime_type, status, "
                    "parse_mode, provider, model, created_at FROM resume_parse "
                    "WHERE user_id = %s ORDER BY created_at",
                    (user_id,),
                )
                resumes = list(cur.fetchall())
                return {
                    "user": user,
                    "profile": profile,
                    "profile_revisions": revisions,
                    "conversations": conversations,
                    "messages": messages,
                    "profile_analyses": analyses,
                    "roadmaps": roadmaps,
                    "resumes": resumes,
                }

    def resume_files_for_user(self, user_id: UUID) -> list[str]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT stored_filename FROM resume_parse "
                    "WHERE user_id = %s AND stored_filename IS NOT NULL",
                    (user_id,),
                )
                return [row["stored_filename"] for row in cur.fetchall()]

    def delete_user(self, user_id: UUID) -> bool:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM app_user WHERE id = %s RETURNING id", (user_id,))
                return cur.fetchone() is not None

    def expired_sessions(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM auth_session WHERE expires_at <= %s OR revoked_at IS NOT NULL",
                    (now,),
                )
                return cur.rowcount
