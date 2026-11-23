from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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


@dataclass
class ContentDelta:
    content: str


class WorkflowRun:
    def __init__(self, graph, initial_state: CareerState) -> None:
        self.graph = graph
        self.final_state: dict[str, Any] = dict(initial_state)

    async def events(self) -> AsyncIterator[NodeExecution | ContentDelta]:
        async for stream_mode, chunk in self.graph.astream(
            self.final_state,
            stream_mode=["custom", "updates"],
        ):
            if stream_mode == "updates":
                if isinstance(chunk, dict):
                    for output in chunk.values():
                        if isinstance(output, dict):
                            self.final_state.update(output)
                continue
            if stream_mode != "custom" or not isinstance(chunk, dict):
                continue

            kind = chunk.get("type")
            if kind == "content_delta":
                content = str(chunk.get("content") or "")
                if content:
                    yield ContentDelta(content=content)
                continue

            node = str(chunk.get("node") or "")
            if not node:
                continue
            started = _parse_datetime(chunk.get("started_at"))
            finished = _parse_datetime(chunk.get("finished_at"))
            if kind == "node_started":
                yield NodeExecution(
                    node=node,
                    status="started",
                    started_at=started,
                    finished_at=started,
                )
            elif kind == "node_completed":
                payload = chunk.get("payload")
                yield NodeExecution(
                    node=node,
                    status=str(chunk.get("status") or "completed"),
                    started_at=started,
                    finished_at=finished,
                    payload=payload if isinstance(payload, dict) else {},
                    error_type=chunk.get("error_type"),
                )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return utcnow()
