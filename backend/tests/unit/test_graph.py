from app.agents.graph import build_graph
from app.agents.state import initial_state


def _state(message: str) -> dict:
    return initial_state(
        user_id="u1",
        conversation_id="c1",
        request_id="r1",
        user_message=message,
    )


def test_greeting_workflow():
    graph = build_graph()
    result = graph.invoke(_state("你好"))
    assert result["intent"] == "greeting"
    assert result["error"] is None
    assert "CareerPilot" in result["response"]
    assert result["tool_results"] == []


def test_general_chat_uses_mock_tool():
    graph = build_graph()
    result = graph.invoke(_state("今天天气不错"))
    assert result["intent"] == "general_chat"
    assert result["error"] is None
    assert result["metadata"]["mock_tool_used"] is True
    assert result["tool_results"][0]["tool"] == "mock_echo"
    assert "Mock" in result["response"]


def test_profile_request_does_not_fake_business_result():
    graph = build_graph()
    result = graph.invoke(_state("帮我分析技能画像"))
    assert result["intent"] == "profile"
    assert "阶段三" in result["response"]
    assert result["metadata"]["business_capability"] == "not_implemented"
    assert result["tool_results"] == []
