"""Real authentication, session and account lifecycle coverage."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from app.core.config import get_settings
from app.core.security import hash_token
from app.db.auth_repository import AuthRepository
from app.services.auth_service import reset_auth_service
from app.services.resume_service import ResumeStorage

pytestmark = pytest.mark.integration

TEST_URL = os.environ["TEST_DATABASE_URL"]
PASSWORD = "CareerPilot2026"
NEW_PASSWORD = "CareerPilot2027"


@pytest.fixture(autouse=True)
def _fresh_auth_service() -> None:
    reset_auth_service()


def _real_auth(monkeypatch: pytest.MonkeyPatch, *, csrf: bool = False):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_test_mode", False)
    monkeypatch.setattr(settings, "auth_csrf_enabled", csrf)
    return settings


def _register(client, email: str, password: str = PASSWORD, name: str = "Tester"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )


def _login(client, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _cookie_jar(client) -> dict[str, str]:
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def _use_cookies(client, jar: dict[str, str]) -> None:
    client.cookies.clear()
    for name, value in jar.items():
        client.cookies.set(name, value)


def _db():
    return psycopg.connect(TEST_URL)


def test_register_creates_isolated_empty_account(client, monkeypatch):
    _real_auth(monkeypatch)
    response = _register(client, "alice@example.com", name="Alice")
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["display_name"] == "Alice"
    assert body["user"]["is_demo"] is False
    assert body["email_verification"] == "not_configured"
    assert body["csrf_token"]
    assert any(cookie.name == "cp_session" for cookie in client.cookies.jar)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["id"] == body["user"]["id"]

    profile = client.get("/api/profile")
    assert profile.status_code == 200
    assert profile.json()["data"]["profile"] is None


def test_register_rejects_duplicate_email_case_insensitively(client, monkeypatch):
    _real_auth(monkeypatch)
    assert _register(client, "Bob@Example.com").status_code == 201
    client.cookies.clear()
    duplicate = _register(client, "bob@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


def test_register_rejects_weak_password(client, monkeypatch):
    _real_auth(monkeypatch)
    response = _register(client, "weak@example.com", password="short1")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "WEAK_PASSWORD"


def test_login_logout_and_session_revocation(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "carol@example.com")
    jar = _cookie_jar(client)

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    _use_cookies(client, jar)
    client.cookies.clear()
    login = _login(client, "carol@example.com")
    assert login.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_invalid_login_and_rate_limiting(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "dave@example.com")
    client.cookies.clear()

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_login_max_attempts", 3)
    for _ in range(3):
        response = _login(client, "dave@example.com", "WrongPassword123")
        assert response.status_code == 401
    limited = _login(client, "dave@example.com", "WrongPassword123")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_unknown_email_and_wrong_password_look_identical(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "erin@example.com")
    client.cookies.clear()
    unknown = _login(client, "nobody@example.com")
    wrong = _login(client, "erin@example.com", "WrongPassword123")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["code"] == wrong.json()["error"]["code"]


def test_x_user_id_header_is_ignored_outside_test_mode(client, monkeypatch):
    _real_auth(monkeypatch)
    response = client.get("/api/profile", headers={"X-User-Id": "attacker"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_two_users_are_fully_isolated(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "owner@example.com", name="Owner")
    owner_jar = _cookie_jar(client)

    profile_payload = {"data": {"basic": {"name": "Owner"}, "goals": {}}}
    assert client.put("/api/profile", json=profile_payload).status_code == 200
    conversation = client.post("/api/conversations", json={"title": "Owner chat"})
    assert conversation.status_code == 201
    conversation_id = conversation.json()["data"]["id"]

    client.cookies.clear()
    _register(client, "intruder@example.com", name="Intruder")
    assert client.get("/api/profile").json()["data"]["profile"] is None
    assert client.get("/api/conversations").json()["data"]["items"] == []
    hidden = client.get(f"/api/conversations/{conversation_id}")
    assert hidden.status_code == 404

    _use_cookies(client, owner_jar)
    assert client.get("/api/profile").json()["data"]["profile"]["data"]["basic"]["name"] == "Owner"
    assert len(client.get("/api/conversations").json()["data"]["items"]) == 1


def test_new_user_never_sees_demo_data(client, monkeypatch):
    _real_auth(monkeypatch)
    demo_id = uuid.uuid4()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_user (id, external_id, display_name, is_demo) "
                "VALUES (%s, 'demo-user', 'Demo User', true)",
                (demo_id,),
            )
            cur.execute(
                "INSERT INTO career_profile (id, user_id, data) VALUES (%s, %s, %s)",
                (uuid.uuid4(), demo_id, '{"basic": {"name": "Demo"}}'),
            )

    _register(client, "fresh@example.com")
    assert client.get("/api/profile").json()["data"]["profile"] is None
    assert client.get("/api/conversations").json()["data"]["items"] == []


def test_sse_endpoint_requires_authentication(client, monkeypatch):
    _real_auth(monkeypatch)
    response = client.post(
        f"/api/conversations/{uuid.uuid4()}/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 401


def test_expired_and_disabled_sessions_are_rejected(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "grace@example.com")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE auth_session SET expires_at = %s WHERE revoked_at IS NULL",
                (datetime.now(UTC) - timedelta(minutes=1),),
            )
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.clear()
    assert _login(client, "grace@example.com").status_code == 200
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_user SET status = 'suspended' WHERE email = %s",
                ("grace@example.com",),
            )
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    disabled = _login(client, "grace@example.com")
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_csrf_is_enforced_for_authenticated_mutations(client, monkeypatch):
    _real_auth(monkeypatch, csrf=True)
    _register(client, "csrf@example.com")
    assert client.post("/api/conversations", json={"title": "x"}).status_code == 403
    token = None
    for cookie in client.cookies.jar:
        if cookie.name == "cp_csrf":
            token = cookie.value
    assert token
    ok = client.post(
        "/api/conversations",
        json={"title": "x"},
        headers={"X-CSRF-Token": token},
    )
    assert ok.status_code == 201


def test_password_reset_is_honest_when_email_is_unconfigured(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "reset@example.com")
    client.cookies.clear()
    response = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["delivery"] == "not_configured"

    invalid = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "x" * 32, "new_password": NEW_PASSWORD},
    )
    assert invalid.status_code == 400


def test_password_reset_consumes_token_and_revokes_sessions(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "rotate@example.com")
    raw_token = "reset-token-for-test-0123456789"
    with _db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM app_user WHERE email = %s", ("rotate@example.com",))
            user_id = cur.fetchone()["id"]
    repository = AuthRepository()
    repository.create_token(
        user_id=user_id,
        purpose="password_reset",
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": NEW_PASSWORD},
    )
    assert confirm.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.clear()
    assert _login(client, "rotate@example.com", PASSWORD).status_code == 401
    assert _login(client, "rotate@example.com", NEW_PASSWORD).status_code == 200

    replay = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": PASSWORD},
    )
    assert replay.status_code == 400


def test_export_excludes_password_hash(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "export@example.com")
    client.put(
        "/api/profile",
        json={"data": {"basic": {"name": "Exporter"}, "goals": {}}},
    )
    response = client.get("/api/auth/export")
    assert response.status_code == 200
    payload = response.json()["data"]["data"]
    assert payload["user"]["email"] == "export@example.com"
    assert "password_hash" not in payload["user"]
    assert payload["profile"]["data"]["basic"]["name"] == "Exporter"


def test_delete_account_removes_only_own_data_and_resume_files(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "delete-me@example.com")
    owner_jar = _cookie_jar(client)
    client.put("/api/profile", json={"data": {"basic": {"name": "Delete"}, "goals": {}}})

    storage = ResumeStorage()
    stored_name = storage.save(b"%PDF-1.4 test", ".pdf")
    with _db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM app_user WHERE email = %s",
                ("delete-me@example.com",),
            )
            owner_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO resume_parse (id, user_id, original_filename, "
                "stored_filename, file_size, mime_type, status, parse_mode, "
                "provider, model) VALUES (%s, %s, 'cv.pdf', %s, 13, "
                "'application/pdf', 'pending_review', 'mock', 'mock', 'mock')",
                (uuid.uuid4(), owner_id, stored_name),
            )

    client.cookies.clear()
    _register(client, "bystander@example.com")
    bystander_jar = _cookie_jar(client)
    client.put("/api/profile", json={"data": {"basic": {"name": "Bystander"}, "goals": {}}})

    _use_cookies(client, owner_jar)
    wrong = client.request(
        "DELETE", "/api/auth/account", json={"password": "WrongPassword123"}
    )
    assert wrong.status_code == 401

    deleted = client.request(
        "DELETE", "/api/auth/account", json={"password": PASSWORD}
    )
    assert deleted.status_code == 200
    assert not (storage.base / stored_name).exists()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM app_user WHERE id = %s", (owner_id,))
            assert cur.fetchone() is None

    _use_cookies(client, bystander_jar)
    profile = client.get("/api/profile")
    assert profile.status_code == 200
    assert profile.json()["data"]["profile"]["data"]["basic"]["name"] == "Bystander"


def test_logout_all_revokes_every_session(client, monkeypatch):
    _real_auth(monkeypatch)
    _register(client, "multi@example.com")
    first_jar = _cookie_jar(client)
    client.cookies.clear()
    assert _login(client, "multi@example.com").status_code == 200
    second_jar = _cookie_jar(client)

    response = client.post("/api/auth/logout-all")
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    for jar in (first_jar, second_jar):
        _use_cookies(client, jar)
        assert client.get("/api/auth/me").status_code == 401


def test_production_rejects_test_mode_and_insecure_https_cookie():
    from app.core.config import Settings

    with pytest.raises(ValueError):
        Settings(app_env="production", auth_test_mode=True, auth_cookie_secure=False)
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            auth_test_mode=False,
            auth_public_base_url="https://careerpilot.example.com",
            auth_cookie_secure=False,
        )
