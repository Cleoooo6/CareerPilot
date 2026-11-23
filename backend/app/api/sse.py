"""SSE 强类型事件与帧编码。"""
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

SseEventName = Literal[
    "task_started",
    "node_started",
    "node_completed",
    "intent_detected",
    "content_delta",
    "assistant_message",
    "task_completed",
    "task_failed",
]


class SseEvent(BaseModel):
    task_id: str = Field(min_length=1)
    event_id: int = Field(ge=1)
    event: SseEventName
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventEmitter:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self._event_id = 0

    def next(self, event: SseEventName, data: dict[str, Any]) -> SseEvent:
        self._event_id += 1
        return SseEvent(
            task_id=self.task_id,
            event_id=self._event_id,
            event=event,
            data=data,
        )


def encode_sse(event: SseEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"event: {event.event}\nid: {event.event_id}\ndata: {payload}\n\n"
