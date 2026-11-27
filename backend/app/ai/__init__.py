"""单例 AI 服务入口。"""
from app.ai.prompts import (
    CHAT_INTENT_SPEC,
    CHAT_REPLY_BOUNDARY,
    CHAT_REPLY_SPECS,
    CHAT_REPLY_VERSION,
    PROFILE_ANALYSIS_SPEC,
    RESUME_PARSE_SPEC,
    ROADMAP_ADJUST_SPEC,
    ROADMAP_GENERATE_SPEC,
    PromptSpec,
)
from app.ai.service import AIResultMeta, AIService, get_ai_service

__all__ = [
    "AIResultMeta",
    "AIService",
    "get_ai_service",
    "PromptSpec",
    "RESUME_PARSE_SPEC",
    "PROFILE_ANALYSIS_SPEC",
    "ROADMAP_GENERATE_SPEC",
    "ROADMAP_ADJUST_SPEC",
    "CHAT_INTENT_SPEC",
    "CHAT_REPLY_SPECS",
    "CHAT_REPLY_BOUNDARY",
    "CHAT_REPLY_VERSION",
]
