import asyncio
import json
import time
from uuid import UUID

from app.agents.context import build_history, should_use_profile, usage_payload
from app.agents.state import CareerState
from app.agents.streaming import get_writer
from app.ai import (
    CHAT_REPLY_BOUNDARY,
    CHAT_REPLY_SPECS,
    CHAT_REPLY_VERSION,
    AIService,
)
from app.ai.prompts import PromptSpec
from app.core.llm import LLMClient, LLMError, LLMUsage
from app.tools.base import ToolError
from app.tools.registry import ToolRegistry

MAX_REPLY_TOKENS = 1200
MARKET_INTENTS = frozenset({"career_advice", "career_planning", "market_analysis"})
ROADMAP_INTENTS = frozenset({"career_planning"})
ROADMAP_GENERATE_ACTIONS = (
    "生成",
    "制定",
    "创建",
    "做一份",
    "规划一份",
    "规划",
    "调整",
    "重新生成",
    "重新制定",
    "重新规划",
    "再生成",
    "重做",
)
ROADMAP_GENERATE_OBJECTS = (
    "路线",
    "计划",
    "学习路径",
    "成长路径",
    "路线图",
)
ROADMAP_REGENERATE_WORDS = (
    "重新生成",
    "重新制定",
    "重新规划",
    "再生成",
    "重做",
    "再来一份",
    "调整",
)
ROADMAP_VIEW_WORDS = ("查看", "看看", "看一下", "显示", "打开", "了解")
ROADMAP_EXPLICIT_ACTIONS = (
    "生成",
    "制定",
    "创建",
    "做一份",
    "规划一份",
    "规划",
    "调整",
    "重新生成",
    "重新制定",
    "重新规划",
    "再生成",
    "重做",
)


def should_generate_roadmap(message: str) -> bool:
    text = message.strip()
    if not text:
        return False
    has_action = any(word in text for word in ROADMAP_GENERATE_ACTIONS)
    has_object = any(word in text for word in ROADMAP_GENERATE_OBJECTS)
    if not (has_action and has_object):
        return False
    if any(word in text for word in ROADMAP_VIEW_WORDS) and not any(
        word in text for word in ROADMAP_EXPLICIT_ACTIONS
    ):
        return False
    return True

REPLY_SYSTEM_PROMPTS = dict(CHAT_REPLY_SPECS)

REPLY_BOUNDARY_NOTE = CHAT_REPLY_BOUNDARY


def build_reply_messages(
    state: CareerState,
    market_context: dict | None = None,
    roadmap_context: dict | None = None,
) -> list[dict[str, str]]:
    intent = state.get("intent") or "unknown"
    system_prompt = REPLY_SYSTEM_PROMPTS.get(intent, REPLY_SYSTEM_PROMPTS["unknown"])
    messages = [
        {
            "role": "system",
            "content": f"{system_prompt}\n{REPLY_BOUNDARY_NOTE}",
        }
    ]
    if should_use_profile(intent) and state.get("profile_context"):
        messages.append(
            {
                "role": "system",
                "content": (
                    "以下是用户已确认的职业数据摘要（画像、简历解析、最新 AI 分析、"
                    "技能差距、路线进度），仅在相关时参考；"
                    "不要声称读取了完整简历或数据之外的信息：\n"
                    f"{state['profile_context']}"
                ),
            }
        )
    if market_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "以下是 CareerPilot Market Radar 数据库统计，不是实时互联网搜索结果：\n"
                    f"{json.dumps(market_context, ensure_ascii=False)[:6000]}\n"
                    "只能引用这些数字并说明样本量/来源/周期；数据不足时不要补造。"
                ),
            }
        )
    if roadmap_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "以下是 CareerPilot 成长路线工具结果（来自画像、Market Radar 与路线数据库，"
                    "不是实时互联网搜索）：\n"
                    f"{json.dumps(roadmap_context, ensure_ascii=False)[:6000]}\n"
                    "草稿只有用户在 My Roadmap 页面确认后才会成为正式路线；"
                    "任务完成不等于技能掌握，不要建议自动提高技能等级；"
                    "没有记录不等于不具备。"
                ),
            }
        )
    messages.extend(
        build_history(
            state.get("history", []),
            max_messages=10,
            max_chars=6000,
        )
    )
    messages.append(
        {"role": "user", "content": state.get("user_message", "")}
    )
    return messages


def _mock_reply(
    intent: str, message: str, roadmap_meta: dict | None = None
) -> str:
    text = (
        f"【Mock 模式】已识别意图：{intent}。"
        f"我收到了你的消息「{message[:80]}」。"
        "当前未调用真实模型，这是用于验证 LangGraph、SSE 与持久化链路的本地回复；"
        "不会伪造画像、市场、薪资或规划数据。"
    )
    action = (roadmap_meta or {}).get("roadmap_action")
    if action == "reused":
        version = roadmap_meta.get("roadmap_draft_version")
        draft_id = str(roadmap_meta.get("roadmap_draft_id") or "")[:8]
        return (
            text
            + f" 已有待确认草稿（版本 {version}，ID {draft_id}…）；"
            "当前画像/市场输入未变化，未重复创建。"
            "如需新版本，请明确要求重新生成。"
        )
    if action == "generated":
        version = roadmap_meta.get("roadmap_draft_version")
        draft_id = str(roadmap_meta.get("roadmap_draft_id") or "")[:8]
        return (
            text
            + f" 已生成成长路线草稿（版本 {version}，ID {draft_id}…）。"
            "草稿需要你到 My Roadmap 页面确认后才会正式启用。"
        )
    if roadmap_meta and roadmap_meta.get("roadmap_used"):
        return (
            text
            + " 已读取当前成长路线与技能差距；可在 My Roadmap 页面查看和确认变更。"
        )
    return text


async def _collect_market_context(intent: str, state: CareerState, registry):
    if registry is None or intent not in MARKET_INTENTS:
        return None, {"market_used": False}
    role = state.get("target_role") or None
    if intent == "market_analysis":
        calls = [
            ("get_market_insights", {"role": role, "dataset_kind": "all"}),
            ("get_skill_demand", {"role": role, "limit": 10}),
        ]
    else:
        calls = [
            (
                "get_career_market_requirements",
                {"role": role},
            )
        ]
    results = {}
    errors = {}
    for name, args in calls:
        try:
            results[name] = await asyncio.to_thread(registry.execute, name, args)
        except ToolError as exc:
            errors[name] = exc.code
    if not results:
        return None, {
            "market_used": False,
            "market_tool_errors": errors,
        }
    metas = []
    for result in results.values():
        meta = result.get("meta")
        if not isinstance(meta, dict) and isinstance(result.get("overview"), dict):
            meta = result["overview"].get("meta")
        if isinstance(meta, dict):
            metas.append(meta)
    sample_sizes = [meta.get("sample_size", 0) for meta in metas]
    dataset_kinds = sorted(
        {kind for meta in metas for kind in meta.get("dataset_kinds", [])}
    )
    warnings = sorted(
        {warning for meta in metas for warning in meta.get("warnings", [])}
    )
    context = {
        "tools": results,
        "sample_size": max(sample_sizes, default=0),
        "dataset_kinds": dataset_kinds,
        "warnings": warnings,
    }
    return context, {
        "market_used": True,
        "market_tools": list(results),
        "market_sample_size": context["sample_size"],
        "market_dataset_kinds": dataset_kinds,
    }


async def _collect_roadmap_context(intent: str, state: CareerState, registry):
    if registry is None or intent not in ROADMAP_INTENTS:
        return None, {"roadmap_used": False}
    user_id = str(state.get("user_id") or "")
    if not user_id:
        return None, {
            "roadmap_used": False,
            "roadmap_tool_errors": {"get_skill_gap": "TOOL_CONTEXT_MISSING"},
        }
    role = state.get("target_role") or None
    results: dict = {}
    errors: dict = {}
    for name, args in (
        ("get_skill_gap", {"role": role}),
        ("get_roadmap", {}),
    ):
        try:
            results[name] = await asyncio.to_thread(
                registry.execute, name, args, user_id=user_id
            )
        except ToolError as exc:
            errors[name] = exc.code

    action = "read"
    draft = None
    message = state.get("user_message", "")
    if should_generate_roadmap(message):
        regenerate = any(
            word in message for word in ROADMAP_REGENERATE_WORDS
        )
        try:
            draft = await asyncio.to_thread(
                registry.execute,
                "generate_roadmap_draft",
                {"target_role": role, "regenerate": regenerate},
                user_id=user_id,
            )
            results["generate_roadmap_draft"] = draft
            reused = isinstance(draft, dict) and bool(draft.get("reused"))
            action = "reused" if reused else "generated"
        except ToolError as exc:
            errors["generate_roadmap_draft"] = exc.code

    if not results:
        return None, {"roadmap_used": False, "roadmap_tool_errors": errors}

    meta = {"roadmap_used": True, "roadmap_action": action}
    if isinstance(draft, dict):
        meta["roadmap_draft_id"] = draft.get("draft_id")
        meta["roadmap_draft_version"] = draft.get("version")
    current = results.get("get_roadmap")
    if isinstance(current, dict):
        roadmap = current.get("roadmap")
        if isinstance(roadmap, dict):
            meta["roadmap_current_version"] = roadmap.get("version")
        meta["roadmap_has_draft"] = bool(current.get("has_draft"))
    if errors:
        meta["roadmap_tool_errors"] = errors
    return {"tools": results, "errors": errors}, meta


def _uuid_or_none(value: str | None) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def make_reply_node(client: LLMClient, registry: ToolRegistry | None = None):
    async def reply_node(state: CareerState) -> dict:
        intent = state.get("intent") or "unknown"
        message = state.get("user_message", "")
        profile_used = bool(state.get("profile_context")) and should_use_profile(intent)
        market_context, market_meta = await _collect_market_context(
            intent, state, registry
        )
        roadmap_context, roadmap_meta = await _collect_roadmap_context(
            intent, state, registry
        )
        messages = build_reply_messages(
            state, market_context, roadmap_context
        )
        mock_text = (
            _mock_reply(intent, message, roadmap_meta)
            if client.mode == "mock"
            else None
        )
        writer = get_writer()
        content_parts: list[str] = []
        usage = LLMUsage()
        model = client.settings.llm_model
        finish_reason: str | None = None
        started = time.perf_counter()
        ai = AIService(llm_client=client)
        reply_prompt = PromptSpec(
            key=f"chat_reply:{intent}",
            version=CHAT_REPLY_VERSION,
            system=(
                f"{REPLY_SYSTEM_PROMPTS.get(intent, REPLY_SYSTEM_PROMPTS['unknown'])}\n"
                f"{REPLY_BOUNDARY_NOTE}"
            ),
        )
        target_user = _uuid_or_none(state.get("user_id"))
        target_conversation = _uuid_or_none(state.get("conversation_id"))
        try:
            async for chunk in client.astream_chat(
                messages,
                mock_text=mock_text,
                max_tokens=min(client.settings.llm_max_tokens, MAX_REPLY_TOKENS),
            ):
                if chunk.content:
                    content_parts.append(chunk.content)
                    writer({"type": "content_delta", "content": chunk.content})
                if chunk.model:
                    model = chunk.model
                if usage_payload(chunk.usage) is not None:
                    usage = chunk.usage
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
        except LLMError as exc:
            ai.record_stream(
                user_id=target_user,
                purpose="chat_reply",
                prompt=reply_prompt,
                model=model,
                duration_ms=int((time.perf_counter() - started) * 1000),
                usage=usage if usage_payload(usage) is not None else None,
                status="failed",
                error_code=exc.code,
                source_type="chat",
                source_id=target_conversation,
            )
            return {
                "response": "".join(content_parts).strip(),
                "error": exc.message,
                "error_code": exc.code,
                "metadata": {
                    **_reply_metadata(
                        client,
                        model,
                        usage,
                        finish_reason,
                        started,
                        partial=bool(content_parts),
                        profile_used=profile_used,
                    ),
                    **market_meta,
                    **roadmap_meta,
                },
            }

        content = "".join(content_parts).strip()
        metadata = {
            **_reply_metadata(
                client,
                model,
                usage,
                finish_reason,
                started,
                partial=bool(content_parts),
                profile_used=profile_used,
            ),
            **market_meta,
            **roadmap_meta,
        }
        if finish_reason == "length":
            ai.record_stream(
                user_id=target_user,
                purpose="chat_reply",
                prompt=reply_prompt,
                model=model,
                duration_ms=metadata.get("duration_ms"),
                usage=usage if usage_payload(usage) is not None else None,
                status="succeeded",
                source_type="chat",
                source_id=target_conversation,
            )
            return {
                "response": content,
                "error": "回复达到 max_tokens 上限，已保留部分内容",
                "error_code": "LLM_OUTPUT_TRUNCATED",
                "metadata": {**metadata, "truncated": True},
            }
        if not content:
            ai.record_stream(
                user_id=target_user,
                purpose="chat_reply",
                prompt=reply_prompt,
                model=model,
                duration_ms=metadata.get("duration_ms"),
                usage=usage if usage_payload(usage) is not None else None,
                status="failed",
                error_code="LLM_EMPTY_RESPONSE",
                source_type="chat",
                source_id=target_conversation,
            )
            return {
                "response": "",
                "error": "LLM 未产生有效回复",
                "error_code": "LLM_EMPTY_RESPONSE",
                "metadata": metadata,
            }
        ai.record_stream(
            user_id=target_user,
            purpose="chat_reply",
            prompt=reply_prompt,
            model=model,
            duration_ms=metadata.get("duration_ms"),
            usage=usage if usage_payload(usage) is not None else None,
            status="succeeded",
            source_type="chat",
            source_id=target_conversation,
        )
        return {
            "response": content,
            "error": None,
            "error_code": None,
            "metadata": metadata,
        }

    return reply_node


def _reply_metadata(
    client: LLMClient,
    model: str,
    usage: LLMUsage,
    finish_reason: str | None,
    started: float,
    *,
    partial: bool,
    profile_used: bool,
) -> dict:
    metadata = {
        "llm_mode": client.mode,
        "provider": client.settings.llm_provider,
        "model": model,
        "finish_reason": finish_reason,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "streamed": partial,
        "mock": client.mode == "mock",
        "profile_used": profile_used,
    }
    usage_data = usage_payload(usage)
    if usage_data is not None:
        metadata["usage"] = usage_data
    return metadata
