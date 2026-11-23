from app.agents.nodes.intent import (
    INTENT_GENERAL,
    INTENT_GREETING,
    INTENT_MARKET,
    INTENT_PROFILE,
    INTENT_ROADMAP,
    classify_intent,
)


def test_greeting_is_deterministic():
    assert classify_intent("你好") == INTENT_GREETING
    assert classify_intent("Hello！") == INTENT_GREETING


def test_profile_intent():
    assert classify_intent("帮我看看我的技能画像") == INTENT_PROFILE
    assert classify_intent("我适合什么工作") == INTENT_PROFILE


def test_market_intent():
    assert classify_intent("数据分析岗位的行业趋势如何") == INTENT_MARKET


def test_roadmap_intent():
    assert classify_intent("给我一个转行学习计划") == INTENT_ROADMAP


def test_general_intent():
    assert classify_intent("今天天气不错") == INTENT_GENERAL
