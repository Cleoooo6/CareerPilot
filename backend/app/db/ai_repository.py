"""AI call audit log persistence."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row

from app.core.llm import LLMUsage
from app.db.pool import get_pool

logger = logging.getLogger(__name__)


class AIRepository:
    def record(
        self,
        *,
        user_id: UUID,
        purpose: str,
        provider: str,
        model: str,
        llm_mode: str,
        prompt_version: str,
        status: str,
        error_code: str | None = None,
        duration_ms: int | None = None,
        usage: LLMUsage | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
    ) -> None:
        try:
            with get_pool().connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ai_call_log
                            (id, user_id, purpose, provider, model, llm_mode,
                             prompt_version, status, error_code, duration_ms,
                             prompt_tokens, completion_tokens, total_tokens,
                             source_type, source_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid4(),
                            user_id,
                            purpose[:64],
                            provider[:32],
                            model[:80],
                            llm_mode,
                            prompt_version[:64],
                            status[:16],
                            (error_code or "")[:64] or None,
                            duration_ms,
                            usage.prompt_tokens if usage else None,
                            usage.completion_tokens if usage else None,
                            usage.total_tokens if usage else None,
                            (source_type or "")[:32] or None,
                            source_id,
                        ),
                    )
        except Exception:
            # Auditing must never break the business path.
            logger.warning("ai_call_record_failed purpose=%s", purpose, exc_info=True)

    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        with get_pool().connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, purpose, provider, model, llm_mode, prompt_version,
                           status, error_code, duration_ms, prompt_tokens,
                           completion_tokens, total_tokens, source_type,
                           source_id, created_at
                    FROM ai_call_log
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, min(max(limit, 1), 200)),
                )
                return list(cur.fetchall())


ai_repository = AIRepository()
