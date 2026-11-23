"""CareerPilot 阶段一 Single-Agent 工作流：START → INTENT → ECHO → END。

这不是 Multi-Agent：只有一个 StateGraph、一个共享 CareerState、无 Supervisor、
无独立 Agent 状态与工具集。后续节点在同一图中扩展。
"""
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.echo import make_echo_node
from app.agents.nodes.intent import make_intent_node
from app.agents.state import CareerState
from app.tools.registry import ToolRegistry, build_default_registry

NODE_INTENT = "INTENT"
NODE_ECHO = "ECHO"
NODE_NAMES = frozenset({NODE_INTENT, NODE_ECHO})


def build_graph(
    registry: ToolRegistry | None = None,
    checkpointer=None,
):
    tool_registry = registry or build_default_registry()
    graph = StateGraph(CareerState)
    graph.add_node(NODE_INTENT, make_intent_node())
    graph.add_node(NODE_ECHO, make_echo_node(tool_registry))
    graph.add_edge(START, NODE_INTENT)
    graph.add_edge(NODE_INTENT, NODE_ECHO)
    graph.add_edge(NODE_ECHO, END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_default_graph():
    return build_graph()
