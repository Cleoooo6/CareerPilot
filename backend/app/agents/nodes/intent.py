"""INTENT 节点：确定性基础意图识别，不调用 LLM。"""
from app.agents.state import CareerState

INTENT_GREETING = "greeting"
INTENT_PROFILE = "profile"
INTENT_MARKET = "market"
INTENT_ROADMAP = "roadmap"
INTENT_GENERAL = "general_chat"

_GREETINGS = frozenset({"你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗"})
_PROFILE_WORDS = ("画像", "技能", "简历", "经历", "能力", "我适合")
_MARKET_WORDS = ("行业", "趋势", "市场", "薪资", "岗位需求", "就业")
_ROADMAP_WORDS = ("规划", "路线", "计划", "学习路径", "转行", "提升")


def classify_intent(message: str) -> str:
    text = message.strip().lower().strip("，。！？!?.,;；:：\"'“”‘’()（）[]【】~～ ")
    if text in _GREETINGS:
        return INTENT_GREETING
    if any(word in text for word in _PROFILE_WORDS):
        return INTENT_PROFILE
    if any(word in text for word in _MARKET_WORDS):
        return INTENT_MARKET
    if any(word in text for word in _ROADMAP_WORDS):
        return INTENT_ROADMAP
    return INTENT_GENERAL


def make_intent_node():
    def intent_node(state: CareerState) -> dict:
        intent = classify_intent(state.get("user_message", ""))
        return {
            "intent": intent,
            "context": {
                **state.get("context", {}),
                "stage": "stage-1",
                "intent_classifier": "deterministic",
            },
            "metadata": {
                **state.get("metadata", {}),
                "intent": intent,
            },
            "error": None,
        }

    return intent_node
