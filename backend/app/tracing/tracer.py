"""执行追踪接口与 PostgreSQL 实现。

Trace 是最小执行记录，不等于 LangGraph Checkpoint；Checkpoint 持久化见
`app/agents/checkpoint.py` 与 DEVELOPMENT_STATUS.md 的未实现声明。
"""
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from app.db.repositories import run_repository, trace_repository

logger = logging.getLogger(__name__)


class Tracer(Protocol):
    def start_run(
        self,
        conversation_id: UUID,
        user_id: UUID,
        request_id: str,
        run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID: ...

    def finish_run(
        self, run_id: UUID, status: str, error_type: str | None = None
    ) -> None: ...

    def record_node(
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
    ) -> None: ...


class NullTracer:
    def start_run(
        self,
        conversation_id: UUID,
        user_id: UUID,
        request_id: str,
        run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        from uuid import uuid4

        return run_id or uuid4()

    def finish_run(self, run_id: UUID, status: str, error_type: str | None = None) -> None:
        return None

    def record_node(
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
        return None


class DatabaseTracer:
    def start_run(
        self,
        conversation_id: UUID,
        user_id: UUID,
        request_id: str,
        run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        payload = {"source": "api.chat"}
        if metadata:
            payload.update(metadata)
        return run_repository.create(
            conversation_id,
            user_id,
            request_id,
            metadata=payload,
            run_id=run_id,
        )

    def finish_run(self, run_id: UUID, status: str, error_type: str | None = None) -> None:
        try:
            run_repository.finish(run_id, status, error_type)
        except Exception:
            logger.exception("trace_finish_run_failed", extra={"run_id": str(run_id)})

    def record_node(
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
        try:
            trace_repository.record(
                run_id,
                user_id,
                conversation_id,
                node_name,
                status,
                started_at,
                finished_at,
                error_type,
                payload,
            )
        except Exception:
            logger.exception(
                "trace_record_node_failed",
                extra={"run_id": str(run_id), "node_name": node_name},
            )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
