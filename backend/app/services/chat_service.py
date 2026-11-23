"""Chat 编排：上下文、工作流、SSE、消息与 Trace 持久化。"""
import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from app.agents.context import (
    build_chat_profile_context,
    build_history,
    should_use_profile,
)
from app.agents.graph import get_default_graph
from app.agents.runner import ContentDelta, NodeExecution, WorkflowRun
from app.agents.state import initial_state
from app.api.sse import EventEmitter
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.db.profile_repositories import profile_repository
from app.db.repositories import (
    conversation_repository,
    message_repository,
    user_repository,
)
from app.tracing.tracer import DatabaseTracer, Tracer

logger = logging.getLogger(__name__)

CONTEXT_MESSAGE_LIMIT = 12
CONTEXT_MESSAGE_COUNT = 10
CONTEXT_CHAR_LIMIT = 6000
TRACE_METADATA_KEYS = (
    "intent",
    "intent_source",
    "intent_model",
    "intent_usage",
    "intent_finish_reason",
    "provider",
    "model",
    "llm_mode",
    "usage",
    "finish_reason",
    "truncated",
    "streamed",
    "mock",
    "profile_used",
    "market_used",
    "market_tools",
    "market_sample_size",
    "market_dataset_kinds",
    "roadmap_used",
    "roadmap_action",
    "roadmap_draft_id",
    "roadmap_draft_version",
    "roadmap_current_version",
    "roadmap_has_draft",
    "roadmap_tool_errors",
)


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

        recent = await asyncio.to_thread(
            message_repository.list_recent_for_conversation,
            conversation_id,
            user_id,
            CONTEXT_MESSAGE_LIMIT,
        )
        history = build_history(
            recent,
            max_messages=CONTEXT_MESSAGE_COUNT,
            max_chars=CONTEXT_CHAR_LIMIT,
        )
        profile_data = await asyncio.to_thread(profile_repository.get_data, user_id)
        profile_context = build_chat_profile_context(profile_data)
        target_role = ""
        if profile_data:
            target_role = str(
                (profile_data.get("goals") or {}).get("target_role") or ""
            )

        await asyncio.to_thread(
            message_repository.append, conversation_id, user_id, "user", content
        )
        run_id = uuid4()
        emitter = EventEmitter(str(run_id))
        yield emitter.next(
            "task_started",
            {"conversation_id": str(conversation_id), "status": "started"},
        )

        settings = get_settings()
        finished = False
        node_name: str | None = None
        workflow: WorkflowRun | None = None
        try:
            await asyncio.to_thread(
                self.tracer.start_run,
                conversation_id,
                user_id,
                request_id,
                run_id,
                {
                    "llm_mode": settings.llm_mode,
                    "provider": settings.llm_provider,
                    "model": settings.llm_model,
                },
            )
            workflow = WorkflowRun(
                self.graph,
                initial_state(
                    user_id=str(user_id),
                    conversation_id=str(conversation_id),
                    request_id=request_id,
                    user_message=content,
                    history=history,
                    profile_context=profile_context,
                    target_role=target_role,
                    llm_mode=settings.llm_mode,
                ),
            )

            async for event in workflow.events():
                if isinstance(event, ContentDelta):
                    yield emitter.next("content_delta", {"content": event.content})
                    continue

                execution: NodeExecution = event
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
                    _trace_payload(execution),
                )
                completion = {
                    "node": execution.node,
                    "status": execution.status,
                }
                if execution.error_type:
                    completion["error_code"] = execution.error_type
                yield emitter.next("node_completed", completion)

                if execution.node == "INTENT" and execution.status == "completed":
                    intent = execution.payload.get("intent")
                    if intent:
                        yield emitter.next(
                            "intent_detected",
                            {
                                "intent": str(intent),
                                "profile_used": bool(profile_context)
                                and should_use_profile(str(intent)),
                            },
                        )

            final_state = workflow.final_state
            error = final_state.get("error")
            if error:
                error_code = str(final_state.get("error_code") or "WORKFLOW_FAILED")
                partial = str(final_state.get("response") or "").strip()
                await asyncio.to_thread(
                    message_repository.append,
                    conversation_id,
                    user_id,
                    "assistant",
                    partial or "本次执行失败，请稍后重试。",
                )
                await asyncio.to_thread(
                    conversation_repository.touch, conversation_id, user_id
                )
                await asyncio.to_thread(
                    self.tracer.finish_run, run_id, "failed", error_code
                )
                finished = True
                yield emitter.next(
                    "task_failed",
                    {
                        "code": error_code,
                        "message": str(error),
                        "node": node_name or "unknown",
                    },
                )
                return

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
                {
                    "status": "completed",
                    "run_id": str(run_id),
                    "profile_used": bool(
                        final_state.get("metadata", {}).get("profile_used")
                    ),
                    "market_used": bool(
                        final_state.get("metadata", {}).get("market_used")
                    ),
                    "roadmap_used": bool(
                        final_state.get("metadata", {}).get("roadmap_used")
                    ),
                    "roadmap_draft_id": final_state.get("metadata", {}).get(
                        "roadmap_draft_id"
                    ),
                },
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
                partial = ""
                if workflow is not None:
                    partial = str(workflow.final_state.get("response") or "").strip()
                try:
                    await asyncio.to_thread(
                        message_repository.append,
                        conversation_id,
                        user_id,
                        "assistant",
                        partial or "本次执行失败，请稍后重试。",
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


def _trace_payload(execution: NodeExecution) -> dict[str, Any]:
    duration_ms = max(
        0,
        int((execution.finished_at - execution.started_at).total_seconds() * 1000),
    )
    payload: dict[str, Any] = {
        "output_keys": sorted(execution.payload.keys()),
        "duration_ms": duration_ms,
    }
    metadata = execution.payload.get("metadata")
    if isinstance(metadata, dict):
        for key in TRACE_METADATA_KEYS:
            if key in metadata and metadata[key] is not None:
                payload[key] = metadata[key]
    intent = execution.payload.get("intent")
    if intent:
        payload["intent"] = str(intent)
    return payload


_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ChatService()
    return _SERVICE


def reset_chat_service() -> None:
    global _SERVICE
    _SERVICE = None
