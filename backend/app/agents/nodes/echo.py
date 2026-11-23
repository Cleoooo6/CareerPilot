"""ECHO 节点：阶段一确定性响应 + Mock 工具调用验证。"""
from app.agents.nodes.intent import (
    INTENT_GENERAL,
    INTENT_GREETING,
    INTENT_MARKET,
    INTENT_PROFILE,
    INTENT_ROADMAP,
)
from app.agents.state import CareerState
from app.tools.base import ToolError
from app.tools.registry import ToolRegistry

_MESSAGES = {
    INTENT_GREETING: (
        "你好，我是 CareerPilot AI。当前处于阶段一最小闭环，"
        "我可以接收你的职业发展问题并记录执行过程；职业画像、市场趋势、"
        "机会匹配与成长规划将在后续阶段逐步开放。"
    ),
    INTENT_PROFILE: (
        "职业画像能力计划在阶段三实现。当前阶段一尚未采集或分析你的技能、"
        "经历与目标，因此不会给出画像结论。"
    ),
    INTENT_MARKET: (
        "行业趋势分析计划在阶段四实现。当前阶段一尚未接入真实招聘或行业数据，"
        "不会生成市场结论。"
    ),
    INTENT_ROADMAP: (
        "成长规划计划在阶段七实现。当前阶段一尚未生成任务或路线图，"
        "不会给出未经证据支持的计划。"
    ),
}


def make_echo_node(registry: ToolRegistry):
    def echo_node(state: CareerState) -> dict:
        intent = state.get("intent") or INTENT_GENERAL
        message = state.get("user_message", "")
        metadata = dict(state.get("metadata", {}))
        tool_results = list(state.get("tool_results", []))

        if intent == INTENT_GENERAL:
            try:
                tool_result = registry.execute("mock_echo", {"text": message[:2000]})
            except ToolError as exc:
                return {
                    "response": "",
                    "error": f"{exc.code}: {exc.message}",
                    "metadata": {**metadata, "tool_error": exc.code},
                }
            tool_results.append(
                {"tool": "mock_echo", "result": tool_result, "mock": True}
            )
            response = (
                f"已收到你的问题：{message.strip()}。"
                "当前为阶段一最小工作流（INTENT → ECHO），"
                "已通过 Mock 工具验证调用链路；尚未接入真实职业数据、"
                "画像分析或规划能力。"
            )
            metadata["mock_tool_used"] = True
        else:
            response = _MESSAGES[intent]
            metadata["mock_tool_used"] = False

        return {
            "response": response,
            "tool_results": tool_results,
            "metadata": {
                **metadata,
                "response_source": "deterministic_echo",
                "business_capability": "not_implemented",
            },
            "error": None,
        }

    return echo_node
