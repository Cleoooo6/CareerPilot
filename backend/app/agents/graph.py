from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.intent import make_intent_node
from app.agents.nodes.reply import make_reply_node
from app.agents.state import CareerState
from app.agents.streaming import get_writer
from app.core.llm import LLMClient, get_llm_client
from app.tools.registry import ToolRegistry, build_default_registry
from app.tracing.tracer import utcnow

NODE_INTENT = "INTENT"
NODE_REPLY = "REPLY"
NODE_NAMES = frozenset({NODE_INTENT, NODE_REPLY})


def _wrap_node(name: str, node_func):
    async def wrapped(state: CareerState):
        writer = get_writer()
        started = utcnow()
        writer(
            {
                "type": "node_started",
                "node": name,
                "started_at": started.isoformat(),
            }
        )
        try:
            output = await node_func(state)
        except Exception as exc:
            finished = utcnow()
            writer(
                {
                    "type": "node_completed",
                    "node": name,
                    "status": "failed",
                    "started_at": started.isoformat(),
                    "finished_at": finished.isoformat(),
                    "payload": {},
                    "error_type": type(exc).__name__,
                }
            )
            raise
        finished = utcnow()
        failed = bool(output.get("error"))
        writer(
            {
                "type": "node_completed",
                "node": name,
                "status": "failed" if failed else "completed",
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "payload": output,
                "error_type": output.get("error_code") if failed else None,
            }
        )
        return output

    return wrapped


def build_graph(
    *,
    checkpointer=None,
    llm_client: LLMClient | None = None,
    registry: ToolRegistry | None = None,
):
    client = llm_client or get_llm_client()
    tool_registry = registry or build_default_registry()
    graph = StateGraph(CareerState)
    graph.add_node(NODE_INTENT, _wrap_node(NODE_INTENT, make_intent_node(client)))
    graph.add_node(
        NODE_REPLY, _wrap_node(NODE_REPLY, make_reply_node(client, tool_registry))
    )
    graph.add_edge(START, NODE_INTENT)
    graph.add_conditional_edges(
        NODE_INTENT,
        lambda state: "reply" if not state.get("error") else "end",
        {"reply": NODE_REPLY, "end": END},
    )
    graph.add_edge(NODE_REPLY, END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_default_graph():
    return build_graph()
