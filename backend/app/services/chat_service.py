"""Chat 编排：会话持久化、工作流执行、Trace 与 SSE。"""
import asyncio
import logging
from uuid import UUID, uuid4

from app.agents.graph import get_default_graph
from app.agents.runner import WorkflowRun
from app.agents.state import initial_state
from app.api.sse import EventEmitter
from app.core.errors import AppError, NotFoundError
from app.db.repositories import (
    conversation_repository,
    message_repository,
    user_repository,
)
from app.tracing.tracer import DatabaseTracer, Tracer

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, graph=None, tracer: Tracer | None = None) -> None:
        self.graph = graph or get_default_graph()
        self.tracer = tracer or DatabaseTracer()

    async def ensure_user(self, external_id: str) -> UUID:
        user = await asyncio.to_thread(user_repository.ensure_user, external_id)
        return user["id"]

    async def create_conversation(
        self, user_external_id: str, title: str | None = None
    ) -> dict:
        user_id = await self.ensure_user(user_external_id)
        return await asyncio.to_thread(conversation_repository.create, user_id, title)

    async def list_conversations(self, user_external_id: str) -> list[dict]:
        user_id = await self.ensure_user(user_external_id)
        return await asyncio.to_thread(conversation_repository.list_for_user, user_id)

    async def get_conversation(
        self, user_external_id: str, conversation_id: UUID
    ) -> dict:
        user_id = await self.ensure_user(user_external_id)
        conversation = await asyncio.to_thread(
            conversation_repository.get, conversation_id, user_id
        )
        if conversation is None:
            raise NotFoundError("会话不存在或不属于当前用户")
        return conversation

    async def list_messages(
        self, user_external_id: str, conversation_id: UUID
    ) -> list[dict]:
        user_id = await self.ensure_user(user_external_id)
        conversation = await asyncio.to_thread(
            conversation_repository.get, conversation_id, user_id
        )
        if conversation is None:
            raise NotFoundError("会话不存在或不属于当前用户")
        return await asyncio.to_thread(
            message_repository.list_for_conversation, conversation_id, user_id
        )

    async def stream_turn(
        self,
        *,
        user_external_id: str,
        conversation_id: UUID,
        content: str,
        request_id: str,
    ):
        user_id = await self.ensure_user(user_external_id)
        conversation = await asyncio.to_thread(
            conversation_repository.get, conversation_id, user_id
        )
        if conversation is None:
            raise NotFoundError("会话不存在或不属于当前用户")

        await asyncio.to_thread(
            message_repository.append, conversation_id, user_id, "user", content
        )
        run_id = uuid4()
        emitter = EventEmitter(str(run_id))
        yield emitter.next(
            "task_started",
            {"conversation_id": str(conversation_id), "status": "started"},
        )

        finished = False
        node_name: str | None = None
        try:
            await asyncio.to_thread(
                self.tracer.start_run,
                conversation_id,
                user_id,
                request_id,
                run_id,
            )
            workflow = WorkflowRun(
                self.graph,
                initial_state(
                    user_id=str(user_id),
                    conversation_id=str(conversation_id),
                    request_id=request_id,
                    user_message=content,
                ),
            )
            async for execution in workflow.events():
                node_name = execution.node
                if execution.status == "started":
                    yield emitter.next(
                        "node_started",
                        {"node": execution.node, "status": "started"},
                    )
                    continue
                await asyncio.to_thread(
                    self.tracer.record_node,
                    run_id,
                    user_id,
                    conversation_id,
                    execution.node,
                    execution.status,
                    execution.started_at,
                    execution.finished_at,
                    execution.error_type,
                    {"output_keys": sorted(execution.payload.keys())},
                )
                yield emitter.next(
                    "node_completed",
                    {"node": execution.node, "status": execution.status},
                )

            final_state = workflow.final_state
            if final_state.get("error"):
                raise AppError(
                    "WORKFLOW_FAILED",
                    str(final_state["error"]),
                    status_code=500,
                )
            response = str(final_state.get("response") or "").strip()
            if not response:
                raise AppError("EMPTY_RESPONSE", "Agent 未产生响应", status_code=500)

            await asyncio.to_thread(
                message_repository.append,
                conversation_id,
                user_id,
                "assistant",
                response,
            )
            await asyncio.to_thread(
                conversation_repository.touch, conversation_id, user_id
            )
            await asyncio.to_thread(self.tracer.finish_run, run_id, "completed")
            finished = True
            yield emitter.next(
                "assistant_message",
                {"role": "assistant", "content": response},
            )
            yield emitter.next(
                "task_completed",
                {"status": "completed", "run_id": str(run_id)},
            )
        except asyncio.CancelledError:
            if not finished:
                await asyncio.to_thread(
                    self.tracer.finish_run, run_id, "failed", "client_disconnected"
                )
            raise
        except Exception as exc:
            if not finished:
                await asyncio.to_thread(
                    self.tracer.finish_run,
                    run_id,
                    "failed",
                    exc.code if isinstance(exc, AppError) else type(exc).__name__,
                )
                try:
                    await asyncio.to_thread(
                        message_repository.append,
                        conversation_id,
                        user_id,
                        "assistant",
                        "本次执行失败，请稍后重试。",
                    )
                except Exception:
                    logger.exception("failure_message_persist_failed")
            logger.exception(
                "chat_turn_failed",
                extra={"node_name": node_name or "unknown", "run_id": str(run_id)},
            )
            code = exc.code if isinstance(exc, AppError) else "INTERNAL_ERROR"
            message = (
                exc.message if isinstance(exc, AppError) else "执行失败，请稍后重试"
            )
            yield emitter.next(
                "task_failed",
                {"code": code, "message": message, "node": node_name or "unknown"},
            )


_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ChatService()
    return _SERVICE


def reset_chat_service() -> None:
    """测试用：允许替换 graph/tracer 后重建服务。"""
    global _SERVICE
    _SERVICE = None
