"""CareerState：阶段一最小单 Agent 工作流状态。"""
from typing import Any, TypedDict


class CareerState(TypedDict):
    user_id: str
    conversation_id: str
    request_id: str
    user_message: str
    intent: str
    context: dict[str, Any]
    response: str
    error: str | None
    metadata: dict[str, Any]
    tool_results: list[dict[str, Any]]


def initial_state(
    *,
    user_id: str,
    conversation_id: str,
    request_id: str,
    user_message: str,
) -> CareerState:
    return CareerState(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
        user_message=user_message,
        intent="",
        context={},
        response="",
        error=None,
        metadata={"stage": "stage-1", "llm_mode": "mock"},
        tool_results=[],
    )
