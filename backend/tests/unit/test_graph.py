import pytest

from app.agents.context import build_history
from app.agents.graph import NODE_INTENT, NODE_REPLY, build_graph
from app.agents.nodes.reply import build_reply_messages
from app.agents.state import initial_state


def _state(message: str, history: list[dict[str, str]] | None = None) -> dict:
    return initial_state(
        user_id="u1",
        conversation_id="c1",
        request_id="r1",
        user_message=message,
        history=history,
        llm_mode="mock",
    )


@pytest.mark.asyncio
async def test_greeting_workflow():
    graph = build_graph()
    result = await graph.ainvoke(_state("你好"))
    assert result["intent"] == "general_chat"
    assert result["error"] is None
    assert "Mock" in result["response"]
    assert result["metadata"]["mock"] is True
    assert result["tool_results"] == []


@pytest.mark.asyncio
async def test_resume_workflow_uses_intent_specific_mock_reply():
    graph = build_graph()
    result = await graph.ainvoke(_state("帮我分析技能画像"))
    assert result["intent"] == "resume"
    assert result["error"] is None
    assert "resume" in result["response"]
    assert "画像" in result["response"]


@pytest.mark.asyncio
async def test_stream_emits_intent_and_content_deltas():
    graph = build_graph()
    events = []
    async for mode, chunk in graph.astream(
        _state("你好"), stream_mode=["custom", "updates"]
    ):
        events.append((mode, chunk))

    custom = [chunk for mode, chunk in events if mode == "custom"]
    assert any(
        chunk.get("type") == "node_started" and chunk.get("node") == NODE_INTENT
        for chunk in custom
    )
    assert any(
        chunk.get("type") == "node_completed"
        and chunk.get("node") == NODE_REPLY
        and chunk.get("status") == "completed"
        for chunk in custom
    )
    deltas = [
        chunk.get("content", "")
        for chunk in custom
        if chunk.get("type") == "content_delta"
    ]
    assert deltas
    assert "Mock" in "".join(deltas)


def test_history_is_bounded_and_keeps_recent_messages():
    rows = [
        {"role": "system", "content": "ignored"},
        *[
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"m{index}"}
            for index in range(30)
        ],
    ]
    history = build_history(rows, max_messages=5, max_chars=20)
    assert len(history) <= 5
    assert sum(len(item["content"]) for item in history) <= 20
    assert history[-1]["content"] == "m29"


def test_reply_messages_include_history_and_current_message():
    state = _state(
        "继续说说",
        history=[
            {"role": "user", "content": "我想转行"},
            {"role": "assistant", "content": "你想转到什么方向？"},
        ],
    )
    messages = build_reply_messages(state)
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "我想转行"}
    assert messages[2] == {"role": "assistant", "content": "你想转到什么方向？"}
    assert messages[-1] == {"role": "user", "content": "继续说说"}

def test_profile_context_is_only_used_for_relevant_intents():
    state = _state("继续说说")
    state["profile_context"] = "目标岗位：数据分析师\n技能：Python"

    state["intent"] = "general_chat"
    general_messages = build_reply_messages(state)
    assert all("数据分析师" not in item["content"] for item in general_messages)

    state["intent"] = "resume"
    resume_messages = build_reply_messages(state)
    assert any("数据分析师" in item["content"] for item in resume_messages)
