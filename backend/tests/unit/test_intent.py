import pytest

from app.agents.nodes.intent import (
    INTENT_CAREER_ADVICE,
    INTENT_CAREER_PLANNING,
    INTENT_GENERAL_CHAT,
    INTENT_MARKET_ANALYSIS,
    INTENT_RESUME,
    INTENT_UNKNOWN,
    IntentResult,
    classify_intent,
    make_intent_node,
    normalize_intent,
)
from app.core.config import Settings
from app.core.llm import LLMRateLimitError, LLMSchemaError


def test_general_chat_is_deterministic():
    assert classify_intent("你好") == INTENT_GENERAL_CHAT
    assert classify_intent("Hello！") == INTENT_GENERAL_CHAT
    assert classify_intent("今天天气不错") == INTENT_GENERAL_CHAT


def test_resume_intent():
    assert classify_intent("帮我看看我的技能画像") == INTENT_RESUME
    assert classify_intent("我适合什么工作") == INTENT_RESUME


def test_market_intent():
    assert classify_intent("数据分析岗位的行业趋势如何") == INTENT_MARKET_ANALYSIS


def test_planning_intent():
    assert classify_intent("给我一个转行学习计划") == INTENT_CAREER_PLANNING


def test_advice_intent():
    assert classify_intent("面试有什么建议") == INTENT_CAREER_ADVICE


def test_aliases_and_unknown_are_normalized():
    assert normalize_intent("profile") == INTENT_RESUME
    assert normalize_intent("greeting") == INTENT_GENERAL_CHAT
    assert normalize_intent("not-a-real-intent") == INTENT_UNKNOWN
    assert IntentResult(intent="not-a-real-intent").intent == INTENT_UNKNOWN


class _FakeClient:
    mode = "real"
    settings = Settings(
        _env_file=None,
        llm_provider="zhipu",
        llm_model="glm-4.7-flash",
        llm_base_url="https://example.invalid/v4",
        llm_api_key="test-key",
        llm_mode="real",
    )

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def complete_structured_with_meta(self, *args, **kwargs):
        raise self.exc


def _node_state(message: str) -> dict:
    return {
        "user_message": message,
        "history": [],
        "context": {},
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_schema_failure_falls_back_to_deterministic_intent():
    node = make_intent_node(_FakeClient(LLMSchemaError("bad json")))
    result = await node(_node_state("帮我看看简历"))
    assert result["intent"] == INTENT_RESUME
    assert result["error"] is None
    assert result["metadata"]["intent_source"] == "fallback_schema"


@pytest.mark.asyncio
async def test_model_error_is_explicit():
    node = make_intent_node(_FakeClient(LLMRateLimitError("limit")))
    result = await node(_node_state("你好"))
    assert result["intent"] == INTENT_UNKNOWN
    assert result["error"] == "limit"
    assert result["error_code"]
