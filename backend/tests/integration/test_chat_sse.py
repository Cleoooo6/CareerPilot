import json

import psycopg
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.integration


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = None
        payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
        if event_name and payload:
            assert payload["event"] == event_name
            events.append(payload)
    return events


def _create(client, user: str) -> str:
    response = client.post(
        "/api/conversations",
        json={"title": "阶段二测试"},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _send(client, conversation_id: str, content: str, user: str = "user-a") -> list[dict]:
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages",
        json={"content": content},
        headers={"X-User-Id": user},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        text = "".join(response.iter_text())
    return _parse_sse(text)


def _db_rows(sql: str, params: tuple = ()) -> list[tuple]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        if not conn.info.dbname.endswith("_test"):
            raise RuntimeError("拒绝在非测试库执行查询")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def test_sse_chat_streams_and_persists(client):
    conversation_id = _create(client, "user-a")
    events = _send(client, conversation_id, "你好")
    names = [event["event"] for event in events]

    assert names[0] == "task_started"
    assert names[1] == "node_started"
    assert events[1]["data"]["node"] == "INTENT"
    assert names[2] == "node_completed"
    assert events[2]["data"]["node"] == "INTENT"
    assert names[3] == "intent_detected"
    assert events[3]["data"]["intent"] == "general_chat"
    assert names[4] == "node_started"
    assert events[4]["data"]["node"] == "REPLY"
    assert "content_delta" in names
    assert names[-3] == "node_completed"
    assert events[-3]["data"]["node"] == "REPLY"
    assert names[-2] == "assistant_message"
    assert names[-1] == "task_completed"

    reply_start = 4
    reply_end = len(names) - 3
    assert all(
        name == "content_delta" for name in names[reply_start + 1 : reply_end]
    )
    deltas = "".join(
        event["data"]["content"]
        for event in events
        if event["event"] == "content_delta"
    )
    assert deltas
    assert deltas == events[-2]["data"]["content"]
    assert "Mock" in deltas

    assert [event["event_id"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["task_id"] for event in events}) == 1

    history = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"X-User-Id": "user-a"},
    )
    items = history.json()["data"]["items"]
    assert [item["role"] for item in items] == ["user", "assistant"]
    assert items[0]["content"] == "你好"
    assert items[1]["content"] == deltas

    runs = _db_rows(
        "SELECT status, metadata FROM agent_run WHERE conversation_id = %s",
        (conversation_id,),
    )
    assert len(runs) == 1
    assert runs[0][0] == "completed"
    assert runs[0][1]["llm_mode"] == "mock"
    assert runs[0][1]["model"] == "glm-4.7-flash"

    traces = _db_rows(
        "SELECT node_name, status, payload FROM agent_trace "
        "WHERE conversation_id = %s ORDER BY started_at",
        (conversation_id,),
    )
    assert [(row[0], row[1]) for row in traces] == [
        ("INTENT", "completed"),
        ("REPLY", "completed"),
    ]
    assert traces[0][2]["intent"] == "general_chat"
    assert traces[0][2]["llm_mode"] == "mock"
    assert traces[1][2]["model"] == "glm-4.7-flash"
    assert traces[1][2]["llm_mode"] == "mock"
    assert "usage" not in traces[1][2]


def test_multi_turn_history_is_persisted(client):
    conversation_id = _create(client, "user-a")
    first = _send(client, conversation_id, "你好")
    second = _send(client, conversation_id, "我适合什么工作")

    assert second[3]["data"]["intent"] == "resume"
    assert next(e for e in first if e["event"] == "assistant_message")["data"][
        "content"
    ]
    assert next(e for e in second if e["event"] == "assistant_message")["data"][
        "content"
    ]

    history = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"X-User-Id": "user-a"},
    )
    items = history.json()["data"]["items"]
    assert [item["role"] for item in items] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    runs = _db_rows(
        "SELECT status FROM agent_run WHERE conversation_id = %s ORDER BY started_at",
        (conversation_id,),
    )
    assert runs == [("completed",), ("completed",)]
    traces = _db_rows(
        "SELECT node_name FROM agent_trace WHERE conversation_id = %s ORDER BY started_at",
        (conversation_id,),
    )
    assert [row[0] for row in traces] == ["INTENT", "REPLY", "INTENT", "REPLY"]


def test_chat_rejects_cross_user_conversation(client):
    conversation_id = _create(client, "user-a")
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好"},
        headers={"X-User-Id": "user-b"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_chat_validates_empty_content(client):
    conversation_id = _create(client, "user-a")
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": ""},
        headers={"X-User-Id": "user-a"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_rejects_invalid_conversation_uuid(client):
    response = client.post(
        "/api/conversations/not-a-uuid/messages",
        json={"content": "你好"},
        headers={"X-User-Id": "user-a"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
