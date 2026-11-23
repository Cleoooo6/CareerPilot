from typing import Any, TypedDict


class CareerState(TypedDict):
    user_id: str
    conversation_id: str
    request_id: str
    user_message: str
    history: list[dict[str, str]]
    profile_context: str
    target_role: str
    intent: str
    context: dict[str, Any]
    response: str
    error: str | None
    error_code: str | None
    metadata: dict[str, Any]
    tool_results: list[dict[str, Any]]


def initial_state(
    *,
    user_id: str,
    conversation_id: str,
    request_id: str,
    user_message: str,
    history: list[dict[str, str]] | None = None,
    profile_context: str = "",
    target_role: str = "",
    llm_mode: str = "mock",
) -> CareerState:
    return CareerState(
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
        user_message=user_message,
        history=list(history or []),
        profile_context=profile_context,
        target_role=target_role,
        intent="",
        context={},
        response="",
        error=None,
        error_code=None,
        metadata={"stage": "stage-2", "llm_mode": llm_mode},
        tool_results=[],
    )
