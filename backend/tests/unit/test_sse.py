import json

from app.api.sse import EventEmitter, encode_sse


def test_event_ids_are_monotonic():
    emitter = EventEmitter("task-1")
    first = emitter.next("task_started", {"status": "started"})
    second = emitter.next("intent_detected", {"intent": "general_chat"})
    third = emitter.next("content_delta", {"content": "你"})
    assert first.event_id == 1
    assert second.event_id == 2
    assert third.event_id == 3
    assert first.task_id == second.task_id == third.task_id == "task-1"


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


def test_encode_content_delta_and_intent_events():
    emitter = EventEmitter("task-2")
    intent = encode_sse(emitter.next("intent_detected", {"intent": "resume"}))
    delta = encode_sse(emitter.next("content_delta", {"content": "片段"}))
    assert "event: intent_detected" in intent
    assert "event: content_delta" in delta
    assert '"content": "片段"' in delta
