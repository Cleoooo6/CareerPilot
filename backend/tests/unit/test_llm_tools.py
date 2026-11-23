import httpx

from app.core.config import Settings
from app.core.llm import LLMClient
from app.tools import build_default_registry


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_mode="real",
        llm_api_key="test-key",
        llm_base_url="https://example.invalid/v4",
        llm_model="glm-4.7-flash",
        llm_max_retries=0,
        llm_timeout=5,
    )


def test_tools_are_sent_and_tool_calls_are_parsed():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "model": "glm-4.7-flash",
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "mock_echo",
                                        "arguments": '{"text":"hi"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        )

    registry = build_default_registry()
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = LLMClient(settings=_settings(), http_client=http_client)
    response = client.chat(
        [{"role": "user", "content": "hi"}],
        tools=registry.definitions(),
    )
    assert '"tools"' in captured["payload"]
    assert '"mock_echo"' in captured["payload"]
    assert response.tool_calls[0]["id"] == "call_1"
    assert response.tool_calls[0]["function"]["name"] == "mock_echo"
