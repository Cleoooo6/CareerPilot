"""最小数据访问层。全部使用参数化 SQL，并按 user_id 做归属过滤。"""
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.pool import get_pool


class UserRepository:
    def ensure_user(self, external_id: str, display_name: str = "Demo User") -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO app_user (id, external_id, display_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (external_id)
                    DO UPDATE SET display_name = EXCLUDED.display_name
                    RETURNING id, external_id, display_name, created_at
                    """,
                    (uuid4(), external_id, display_name),
                )
                return cur.fetchone()


class ConversationRepository:
    def create(self, user_id: UUID, title: str | None = None) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO conversation (id, user_id, title)
                    VALUES (%s, %s, %s)
                    RETURNING id, user_id, title, created_at, updated_at
                    """,
                    (uuid4(), user_id, title or "新的职业咨询"),
                )
                return cur.fetchone()

    def get(self, conversation_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, title, created_at, updated_at
                    FROM conversation
                    WHERE id = %s AND user_id = %s
                    """,
                    (conversation_id, user_id),
                )
                return cur.fetchone()

    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, title, created_at, updated_at
                    FROM conversation
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                return list(cur.fetchall())

    def touch(self, conversation_id: UUID, user_id: UUID) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversation SET updated_at = NOW() WHERE id = %s AND user_id = %s",
                    (conversation_id, user_id),
                )


class MessageRepository:
    def append(
        self, conversation_id: UUID, user_id: UUID, role: str, content: str
    ) -> dict[str, Any]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO message (id, conversation_id, role, content)
                    SELECT %s, %s, %s, %s
                    WHERE EXISTS (
                        SELECT 1 FROM conversation WHERE id = %s AND user_id = %s
                    )
                    RETURNING id, conversation_id, role, content, created_at
                    """,
                    (uuid4(), conversation_id, role, content, conversation_id, user_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise PermissionError("会话不存在或不属于当前用户")
                return row

    def list_for_conversation(
        self, conversation_id: UUID, user_id: UUID, limit: int = 100
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
                    FROM message m
                    JOIN conversation c ON c.id = m.conversation_id
                    WHERE m.conversation_id = %s AND c.user_id = %s
                    ORDER BY m.created_at ASC, m.id ASC
                    LIMIT %s
                    """,
                    (conversation_id, user_id, limit),
                )
                return list(cur.fetchall())

    def list_recent_for_conversation(
        self, conversation_id: UUID, user_id: UUID, limit: int = 12
    ) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
                    FROM message m
                    JOIN conversation c ON c.id = m.conversation_id
                    WHERE m.conversation_id = %s AND c.user_id = %s
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT %s
                    """,
                    (conversation_id, user_id, limit),
                )
                rows = list(cur.fetchall())
                rows.reverse()
                return rows


class RunRepository:
    def create(
        self,
        conversation_id: UUID,
        user_id: UUID,
        request_id: str,
        metadata: dict[str, Any] | None = None,
        run_id: UUID | None = None,
    ) -> UUID:
        run_id = run_id or uuid4()
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_run
                        (id, conversation_id, user_id, status, request_id, metadata)
                    VALUES (%s, %s, %s, 'running', %s, %s)
                    """,
                    (run_id, conversation_id, user_id, request_id, Jsonb(metadata or {})),
                )
        return run_id

    def finish(
        self,
        run_id: UUID,
        status: str,
        error_type: str | None = None,
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_run
                    SET status = %s, error_type = %s, finished_at = NOW()
                    WHERE id = %s
                    """,
                    (status, error_type, run_id),
                )

    def get(self, run_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, conversation_id, user_id, status, request_id,
                           started_at, finished_at, error_type, metadata
                    FROM agent_run
                    WHERE id = %s AND user_id = %s
                    """,
                    (run_id, user_id),
                )
                return cur.fetchone()


class TraceRepository:
    def record(
        self,
        run_id: UUID,
        user_id: UUID,
        conversation_id: UUID,
        node_name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        error_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_trace
                        (id, run_id, user_id, conversation_id, node_name, status,
                         started_at, finished_at, error_type, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        run_id,
                        user_id,
                        conversation_id,
                        node_name,
                        status,
                        started_at,
                        finished_at,
                        error_type,
                        Jsonb(payload or {}),
                    ),
                )

    def list_for_run(self, run_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, run_id, user_id, conversation_id, node_name, status,
                           started_at, finished_at, error_type, payload
                    FROM agent_trace
                    WHERE run_id = %s AND user_id = %s
                    ORDER BY started_at ASC, id ASC
                    """,
                    (run_id, user_id),
                )
                return list(cur.fetchall())


user_repository = UserRepository()
conversation_repository = ConversationRepository()
message_repository = MessageRepository()
run_repository = RunRepository()
trace_repository = TraceRepository()
