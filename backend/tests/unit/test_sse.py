import json

from app.api.sse import EventEmitter, encode_sse


def test_event_ids_are_monotonic():
    emitter = EventEmitter("task-1")
    first = emitter.next("task_started", {"status": "started"})
    second = emitter.next("node_started", {"node": "INTENT"})
    assert first.event_id == 1
    assert second.event_id == 2
    assert first.task_id == second.task_id == "task-1"


def test_encode_sse_frame():
    event = EventEmitter("task-1").next("assistant_message", {"content": "你好"})
    frame = encode_sse(event)
    lines = frame.strip().splitlines()
    assert lines[0] == "event: assistant_message"
    assert lines[1] == "id: 1"
    assert lines[2].startswith("data: ")
    payload = json.loads(lines[2][len("data: ") :])
    assert payload["event"] == "assistant_message"
    assert payload["data"]["content"] == "你好"
    assert payload["task_id"] == "task-1"
    assert frame.endswith("\n\n")
