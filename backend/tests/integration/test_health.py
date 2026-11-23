import pytest

pytestmark = pytest.mark.integration


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "ok"
    assert body["request_id"]


def test_ready_after_migration(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ready"


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-Id": "client-rid-123"})
    assert response.headers["X-Request-Id"] == "client-rid-123"
    assert response.json()["request_id"] == "client-rid-123"


def test_llm_status_is_mock_and_does_not_expose_key(client):
    response = client.get("/api/llm/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "mock"
    assert data["model"] == "glm-4.7-flash"
    assert data["api_key_configured"] is False
    assert "api_key" not in data


def test_tools_are_registered_and_planned_separately(client):
    response = client.get("/api/tools")
    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["name"] for item in data["registered"]] == ["mock_echo"]
    assert "get_user_profile" in data["planned"]
    assert "get_user_profile" not in [item["name"] for item in data["registered"]]


def test_openapi_contains_stage_one_paths(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/conversations" in paths
    assert "/api/conversations/{conversation_id}/messages" in paths
