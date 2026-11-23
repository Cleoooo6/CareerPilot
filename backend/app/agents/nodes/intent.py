import asyncio
from typing import Literal

from pydantic import BaseModel, field_validator

from app.agents.context import format_history, usage_payload
from app.agents.state import CareerState
from app.core.llm import LLMClient, LLMError, LLMSchemaError
from app.core.logging import redact

IntentName = Literal[
    "general_chat",
    "career_advice",
    "resume",
    "career_planning",
    "market_analysis",
    "unknown",
]

INTENT_GENERAL_CHAT: IntentName = "general_chat"
INTENT_CAREER_ADVICE: IntentName = "career_advice"
INTENT_RESUME: IntentName = "resume"
INTENT_CAREER_PLANNING: IntentName = "career_planning"
INTENT_MARKET_ANALYSIS: IntentName = "market_analysis"
INTENT_UNKNOWN: IntentName = "unknown"

_ALLOWED = frozenset(
    {
        INTENT_GENERAL_CHAT,
        INTENT_CAREER_ADVICE,
        INTENT_RESUME,
        INTENT_CAREER_PLANNING,
        INTENT_MARKET_ANALYSIS,
        INTENT_UNKNOWN,
    }
)

_ALIASES = {
    "greeting": INTENT_GENERAL_CHAT,
    "general": INTENT_GENERAL_CHAT,
    "profile": INTENT_RESUME,
    "market": INTENT_MARKET_ANALYSIS,
    "roadmap": INTENT_CAREER_PLANNING,
    "planning": INTENT_CAREER_PLANNING,
    "advice": INTENT_CAREER_ADVICE,
}

_GREETINGS = frozenset({"你好", "您好", "hi", "hello", "嗨", "哈喽", "在吗"})
_RESUME_WORDS = ("简历", "技能", "画像", "经历", "项目", "能力", "我适合")
_PLANNING_WORDS = ("规划", "路线", "计划", "学习路径", "转行", "阶段目标", "提升")
_MARKET_WORDS = ("行业", "趋势", "市场", "薪资", "岗位需求", "就业", "招聘")
_ADVICE_WORDS = ("求职", "面试", "职业建议", "职业发展", "转岗", "跳槽", "选择工作")

INTENT_SYSTEM_PROMPT = """你是 CareerPilot AI 的意图分类器，只做分类，不回答用户问题。
允许的 intent 只能是以下之一：
- general_chat：问候、闲聊、平台使用或非职业问题
- career_advice：求职、面试、转岗、职业选择、职业发展建议
- resume：简历、技能、经历、项目、个人能力画像相关
- career_planning：学习计划、成长路线、阶段目标、转行计划
- market_analysis：行业趋势、岗位需求、薪资、就业市场
- unknown：信息不足，无法判断
只输出 JSON 对象，格式为 {"intent":"..."}。不要输出解释、Markdown 或额外字段。"""


class IntentResult(BaseModel):
    intent: IntentName

    @field_validator("intent", mode="before")
    @classmethod
    def normalize(cls, value):
        return normalize_intent(value)


def normalize_intent(value) -> IntentName:
    if not isinstance(value, str):
        return INTENT_UNKNOWN
    normalized = value.strip().lower()
    normalized = _ALIASES.get(normalized, normalized)
    if normalized in _ALLOWED:
        return normalized
    return INTENT_UNKNOWN


def classify_intent(message: str) -> IntentName:
    text = message.strip().lower().strip("，。！？!?.,;；:：\"'“”‘’()（）[]【】~～ ")
    if text in _GREETINGS:
        return INTENT_GENERAL_CHAT
    if any(word in text for word in _RESUME_WORDS):
        return INTENT_RESUME
    if any(word in text for word in _MARKET_WORDS):
        return INTENT_MARKET_ANALYSIS
    if any(word in text for word in _PLANNING_WORDS):
        return INTENT_CAREER_PLANNING
    if any(word in text for word in _ADVICE_WORDS):
        return INTENT_CAREER_ADVICE
    return INTENT_GENERAL_CHAT


def make_intent_node(client: LLMClient):
    async def intent_node(state: CareerState) -> dict:
        message = state.get("user_message", "")
        fallback = classify_intent(message)
        history_text = format_history(state.get("history", []))
        user_prompt = (
            f"最近对话：\n{history_text or '（无）'}\n\n"
            f"当前用户消息：{message}"
        )
        metadata = {
            **state.get("metadata", {}),
            "llm_mode": client.mode,
            "provider": client.settings.llm_provider,
            "model": client.settings.llm_model,
        }
        try:
            result = await asyncio.to_thread(
                client.complete_structured_with_meta,
                INTENT_SYSTEM_PROMPT,
                user_prompt,
                IntentResult,
                mock_payload=(
                    {"intent": fallback} if client.mode == "mock" else None
                ),
            )
        except LLMSchemaError as exc:
            return {
                "intent": fallback,
                "context": {
                    **state.get("context", {}),
                    "stage": "stage-2",
                    "intent_classifier": "structured_llm_fallback",
                },
                "metadata": {
                    **metadata,
                    "intent": fallback,
                    "intent_source": "fallback_schema",
                    "intent_error": redact(str(exc))[:300],
                },
                "error": None,
                "error_code": None,
            }
        except LLMError as exc:
            return {
                "intent": INTENT_UNKNOWN,
                "context": {
                    **state.get("context", {}),
                    "stage": "stage-2",
                    "intent_classifier": "structured_llm_error",
                },
                "metadata": {
                    **metadata,
                    "intent": INTENT_UNKNOWN,
                    "intent_source": "error",
                },
                "error": exc.message,
                "error_code": exc.code,
            }

        intent = normalize_intent(result.value.intent)
        return {
            "intent": intent,
            "context": {
                **state.get("context", {}),
                "stage": "stage-2",
                "intent_classifier": "structured_llm",
            },
            "metadata": {
                **metadata,
                "intent": intent,
                "intent_source": "mock" if client.mode == "mock" else "llm",
                "intent_model": result.model,
                "intent_usage": usage_payload(result.usage),
                "intent_finish_reason": result.finish_reason,
            },
            "error": None,
            "error_code": None,
        }

    return intent_node
