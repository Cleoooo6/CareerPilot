import httpx
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.llm import (
    LLMClient,
    LLMNonRetryableError,
    LLMRateLimitError,
    LLMSchemaError,
)


class Demo(BaseModel):
    value: str


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "database_url": "postgresql://careerpilot:test@localhost:5433/careerpilot_test",
        "llm_provider": "zhipu",
        "llm_mode": "real",
        "llm_model": "glm-4.7-flash",
        "llm_base_url": "https://example.invalid/v4",
        "llm_api_key": "test-key",
        "llm_max_retries": 1,
        "llm_timeout": 5,
    }
    values.update(overrides)
    return Settings(**values)


def _response(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "glm-4.7-flash",
            "choices": [
                {
                    "message": {"content": content, "tool_calls": []},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        },
    )


def test_mock_text_does_not_call_http():
    settings = _settings(llm_mode="mock")
    client = LLMClient(settings=settings)
    assert "Mock" in client.complete_text("system", "hello")


def test_mock_structured_requires_payload():
    settings = _settings(llm_mode="mock")
    client = LLMClient(settings=settings)
    with pytest.raises(Exception):
        client.complete_structured("system", "hello", Demo)


def test_mock_structured_payload_is_validated():
    settings = _settings(llm_mode="mock")
    client = LLMClient(settings=settings, mock_payload={"value": "ok"})
    assert client.complete_structured("system", "hello", Demo).value == "ok"


def test_real_text_call_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"].startswith("Bearer ")
        return _response("hello from mock")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = LLMClient(settings=_settings(), http_client=http_client)
    assert client.complete_text("system", "hello") == "hello from mock"


def test_rate_limit_with_retry_after_is_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return _response("ok")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = LLMClient(
        settings=_settings(),
        http_client=http_client,
        sleep_func=lambda _: None,
    )
    assert client.complete_text("system", "hello") == "ok"
    assert calls["count"] == 2


def test_rate_limit_without_retry_after_stops():
    http_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={})
        )
    )
    client = LLMClient(settings=_settings(), http_client=http_client)
    with pytest.raises(LLMRateLimitError):
        client.complete_text("system", "hello")


def test_non_retryable_http_error():
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(401))
    )
    client = LLMClient(settings=_settings(), http_client=http_client)
    with pytest.raises(LLMNonRetryableError):
        client.complete_text("system", "hello")


def test_truncated_output_is_not_retried():
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda request: _response("x", "length"))
    )
    client = LLMClient(settings=_settings(), http_client=http_client)
    with pytest.raises(Exception):
        client.complete_text("system", "hello")


def test_structured_output_retries_after_invalid_json():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return _response("not-json")
        return _response('{"value": "fixed"}')

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = LLMClient(
        settings=_settings(),
        http_client=http_client,
        sleep_func=lambda _: None,
    )
    assert client.complete_structured("system", "hello", Demo).value == "fixed"
    assert calls["count"] == 2


def test_structured_output_failure_is_reported():
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda request: _response("not-json"))
    )
    client = LLMClient(settings=_settings(), http_client=http_client)
    with pytest.raises(LLMSchemaError):
        client.complete_structured("system", "hello", Demo)


def test_status_does_not_expose_key():
    client = LLMClient(settings=_settings())
    status = client.status()
    assert status["mode"] == "real"
    assert status["api_key_configured"] is True
    assert "test-key" not in str(status)
