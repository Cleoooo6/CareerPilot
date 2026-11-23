import pytest

pytestmark = pytest.mark.integration


def test_create_and_list_conversation(client):
    created = client.post(
        "/api/conversations",
        json={"title": "职业咨询"},
        headers={"X-User-Id": "user-a"},
    )
    assert created.status_code == 201
    conversation = created.json()["data"]
    assert conversation["title"] == "职业咨询"

    listed = client.get("/api/conversations", headers={"X-User-Id": "user-a"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]["items"]] == [
        conversation["id"]
    ]

    fetched = client.get(
        f"/api/conversations/{conversation['id']}",
        headers={"X-User-Id": "user-a"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == conversation["id"]


def test_user_isolation_on_conversation(client):
    created = client.post(
        "/api/conversations",
        json={},
        headers={"X-User-Id": "user-a"},
    )
    conversation_id = created.json()["data"]["id"]

    forbidden = client.get(
        f"/api/conversations/{conversation_id}",
        headers={"X-User-Id": "user-b"},
    )
    assert forbidden.status_code == 404
    assert forbidden.json()["ok"] is False
    assert forbidden.json()["error"]["code"] == "NOT_FOUND"

    messages = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"X-User-Id": "user-b"},
    )
    assert messages.status_code == 404


def test_invalid_user_header_rejected(client):
    response = client.get(
        "/api/conversations",
        headers={"X-User-Id": "bad user!"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_USER_ID"


def test_empty_message_list(client):
    created = client.post(
        "/api/conversations",
        json={},
        headers={"X-User-Id": "user-a"},
    )
    conversation_id = created.json()["data"]["id"]
    response = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"X-User-Id": "user-a"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []
