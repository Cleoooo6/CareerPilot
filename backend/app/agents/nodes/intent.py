import asyncio
import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.agents.context import format_history, usage_payload
from app.agents.state import CareerState
from app.ai import CHAT_INTENT_SPEC, AIService
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

INTENT_SYSTEM_PROMPT = CHAT_INTENT_SPEC.system


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


def _uuid_or_none(value: str | None) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


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
        ai = AIService(llm_client=client)
        target_user = _uuid_or_none(state.get("user_id"))
        target_conversation = _uuid_or_none(state.get("conversation_id"))
        started = time.perf_counter()
        try:
            result, meta = await asyncio.to_thread(
                ai.structured,
                user_id=target_user,
                purpose="chat_intent",
                prompt=CHAT_INTENT_SPEC,
                user_prompt=user_prompt,
                schema=IntentResult,
                mock_payload=(
                    {"intent": fallback} if client.mode == "mock" else None
                ),
                source_type="chat",
                source_id=target_conversation,
            )
        except LLMSchemaError as exc:
            ai.record_stream(
                user_id=target_user,
                purpose="chat_intent",
                prompt=CHAT_INTENT_SPEC,
                model=client.settings.llm_model,
                duration_ms=_elapsed_ms(started),
                usage=None,
                status="failed",
                error_code=exc.code,
                source_type="chat",
                source_id=target_conversation,
            )
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
            ai.record_stream(
                user_id=target_user,
                purpose="chat_intent",
                prompt=CHAT_INTENT_SPEC,
                model=client.settings.llm_model,
                duration_ms=_elapsed_ms(started),
                usage=None,
                status="failed",
                error_code=exc.code,
                source_type="chat",
                source_id=target_conversation,
            )
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

        intent = normalize_intent(result.intent)
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
                "intent_model": meta.model,
                "intent_usage": usage_payload(meta.usage),
                "intent_finish_reason": meta.finish_reason,
            },
            "error": None,
            "error_code": None,
        }

    return intent_node
