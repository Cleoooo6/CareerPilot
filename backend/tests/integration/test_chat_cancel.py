import asyncio
from uuid import UUID

import psycopg
import pytest

from app.core.config import get_settings
from app.db.repositories import user_repository
from app.services.chat_service import ChatService
from app.tracing.tracer import DatabaseTracer

pytestmark = pytest.mark.integration


class SlowGraph:
    async def astream(self, state, stream_mode=None):
        await asyncio.sleep(30)
        yield "custom", {
            "type": "node_started",
            "node": "REPLY",
            "started_at": "2026-11-23T00:00:00+00:00",
        }
        yield "updates", {"REPLY": {"response": "late"}}


def _run_row(run_id: UUID) -> tuple[str, str | None]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        if not conn.info.dbname.endswith("_test"):
            raise RuntimeError("拒绝在非测试库执行查询")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, error_type FROM agent_run WHERE id = %s",
                (run_id,),
            )
            row = cur.fetchone()
    assert row is not None
    return row


def test_cancelled_stream_marks_run_failed_and_releases(client):
    async def scenario():
        user = await asyncio.to_thread(user_repository.ensure_test_user, "cancel-user")
        user_id = str(user["id"])
        service = ChatService(graph=SlowGraph(), tracer=DatabaseTracer())
        conversation = await service.create_conversation(user_id)
        conversation_id = UUID(str(conversation["id"]))
        events = []
        started = asyncio.Event()

        async def consume():
            async for event in service.stream_turn(
                user_external_id=user_id,
                conversation_id=conversation_id,
                content="你好",
                request_id="cancel-request",
            ):
                events.append(event)
                if event.event == "task_started":
                    started.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return events

    events = asyncio.run(scenario())
    task_started = next(event for event in events if event.event == "task_started")
    run_id = UUID(task_started.task_id)
    status, error_type = _run_row(run_id)
    assert status == "failed"
    assert error_type == "client_disconnected"
