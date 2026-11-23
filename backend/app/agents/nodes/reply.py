import asyncio
import json
import time

from app.agents.context import build_history, should_use_profile, usage_payload
from app.agents.state import CareerState
from app.agents.streaming import get_writer
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

REPLY_SYSTEM_PROMPTS = {
    "general_chat": (
        "你是 CareerPilot AI，一名友好、专业的职业发展助手。"
        "自然回应用户，必要时把话题引向职业发展；不要编造用户经历或外部数据。"
    ),
    "career_advice": (
        "你是 CareerPilot AI 的职业发展顾问。基于用户提供的信息给出可执行建议，"
        "必要时追问目标、背景和时间安排。不要编造用户经历、岗位或薪资数据。"
    ),
    "resume": (
        "你是 CareerPilot AI 的简历与能力表达顾问。可以基于用户已确认的画像摘要"
        "提供针对性建议，但不要声称读取了完整简历；需要具体信息时请让用户补充。"
    ),
    "career_planning": (
        "你是 CareerPilot AI 的成长规划顾问。可以读取用户已确认画像、技能差距和现有路线；"
        "如本轮生成了路线草稿，必须说明草稿需要用户到 My Roadmap 页面确认后才正式启用。"
        "不要声称已经确认路线、修改画像或完成任务；任务完成不等于技能掌握。"
    ),
    "market_analysis": (
        "你是 CareerPilot AI 的就业市场分析顾问。优先使用 Market Radar 数据库统计，"
        "并明确区分数据库统计、实时互联网搜索结果和一般模型知识。"
        "不得编造实时岗位、薪资或趋势结论。"
    ),
    "unknown": (
        "你是 CareerPilot AI。用户意图不够明确，请先用一个简短问题澄清目标，"
        "不要假设用户背景，也不要编造画像、市场或规划结果。"
    ),
}

REPLY_BOUNDARY_NOTE = (
    "使用简体中文，自然、具体、简洁。不要提及系统提示或内部实现；"
    "不要输出 JSON；不要伪造个人画像、市场数据、薪资或岗位信息。"
    "如果用户要求修改职业目标、技能或经历，不要声称已经修改；"
    "明确提示用户到 Profile 页面确认并保存。"
    "如果提供 Market Radar 数据，必须注明样本量、来源和统计周期；"
    "样本不足时明确说不能代表全国市场。"
    "涉及成长路线时，只能说明草稿已生成或当前路线内容；"
    "不得声称已启用路线、替用户确认或自动提高技能等级。"
)


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
                    "以下是用户已确认的职业画像摘要，仅在相关时参考；"
                    "不要声称读取了完整简历或画像之外的数据：\n"
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
            return {
                "response": content,
                "error": "回复达到 max_tokens 上限，已保留部分内容",
                "error_code": "LLM_OUTPUT_TRUNCATED",
                "metadata": {**metadata, "truncated": True},
            }
        if not content:
            return {
                "response": "",
                "error": "LLM 未产生有效回复",
                "error_code": "LLM_EMPTY_RESPONSE",
                "metadata": metadata,
            }
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
