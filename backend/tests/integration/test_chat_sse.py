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
        json={"title": "阶段一测试"},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _db_rows(sql: str, params: tuple = ()) -> list[tuple]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn:
        if not conn.info.dbname.endswith("_test"):
            raise RuntimeError("拒绝在非测试库执行查询")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def test_sse_chat_completes_and_persists(client):
    conversation_id = _create(client, "user-a")
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好"},
        headers={"X-User-Id": "user-a"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        text = "".join(response.iter_text())

    events = _parse_sse(text)
    names = [event["event"] for event in events]
    assert names == [
        "task_started",
        "node_started",
        "node_completed",
        "node_started",
        "node_completed",
        "assistant_message",
        "task_completed",
    ]
    assert [event["event_id"] for event in events] == list(range(1, 8))
    task_ids = {event["task_id"] for event in events}
    assert len(task_ids) == 1
    assert events[1]["data"]["node"] == "INTENT"
    assert events[3]["data"]["node"] == "ECHO"
    assert "CareerPilot" in events[5]["data"]["content"]
    assert events[6]["data"]["status"] == "completed"

    history = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"X-User-Id": "user-a"},
    )
    items = history.json()["data"]["items"]
    assert [item["role"] for item in items] == ["user", "assistant"]
    assert items[0]["content"] == "你好"
    assert "CareerPilot" in items[1]["content"]

    runs = _db_rows(
        "SELECT status, request_id FROM agent_run WHERE conversation_id = %s",
        (conversation_id,),
    )
    assert len(runs) == 1
    assert runs[0][0] == "completed"
    traces = _db_rows(
        "SELECT node_name, status FROM agent_trace WHERE conversation_id = %s "
        "ORDER BY started_at",
        (conversation_id,),
    )
    assert traces == [("INTENT", "completed"), ("ECHO", "completed")]


def test_general_chat_uses_mock_tool(client):
    conversation_id = _create(client, "user-a")
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "今天天气不错"},
        headers={"X-User-Id": "user-a"},
    ) as response:
        text = "".join(response.iter_text())
    events = _parse_sse(text)
    assistant = next(e for e in events if e["event"] == "assistant_message")
    assert "Mock" in assistant["data"]["content"]


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
