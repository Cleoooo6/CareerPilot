"""消费 LangGraph 事件，产出节点执行记录。"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agents.graph import NODE_NAMES
from app.agents.state import CareerState
from app.tracing.tracer import utcnow


@dataclass
class NodeExecution:
    node: str
    status: str
    started_at: datetime
    finished_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None


class WorkflowRun:
    def __init__(self, graph, initial_state: CareerState) -> None:
        self.graph = graph
        self.final_state: dict[str, Any] = dict(initial_state)
        self._started: dict[str, datetime] = {}

    async def events(self):
        async for event in self.graph.astream_events(self.final_state, version="v2"):
            name = event.get("name")
            kind = event.get("event")
            if name not in NODE_NAMES:
                continue
            if kind == "on_chain_start":
                started = utcnow()
                self._started[name] = started
                yield NodeExecution(
                    node=name,
                    status="started",
                    started_at=started,
                    finished_at=started,
                )
            elif kind == "on_chain_end":
                output = (event.get("data") or {}).get("output")
                if isinstance(output, dict):
                    self.final_state.update(output)
                started = self._started.get(name, utcnow())
                finished = utcnow()
                failed = isinstance(output, dict) and bool(output.get("error"))
                yield NodeExecution(
                    node=name,
                    status="failed" if failed else "completed",
                    started_at=started,
                    finished_at=finished,
                    payload=output if isinstance(output, dict) else {},
                    error_type=str(output.get("error")) if failed else None,
                )
