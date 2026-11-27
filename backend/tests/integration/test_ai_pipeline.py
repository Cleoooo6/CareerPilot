"""End-to-end AI pipeline tests in mock mode against the test database."""
from __future__ import annotations

import os

import psycopg
import pytest

from app.ai.prompts import PROFILE_ANALYSIS_SPEC
from tests.resume_fixtures import make_docx

pytestmark = pytest.mark.integration

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEST_URL = os.environ["TEST_DATABASE_URL"]

PROFILE_PAYLOAD = {
    "data": {
        "basic": {
            "name": "张三",
            "education_level": "本科",
            "major": "信息管理与信息系统",
            "graduation_year": 2026,
            "location": "上海",
        },
        "goals": {
            "target_role": "数据分析师",
            "target_industry": "互联网",
            "job_status": "求职中",
            "desired_direction": "数据分析",
        },
        "skills": [
            {"name": "Python", "proficiency": "熟练", "evidence": "课程项目"}
        ],
        "education": [],
        "projects": [],
        "experiences": [],
    }
}


def _upload(client, user: str = "ai-user-a"):
    return client.post(
        "/api/profile/resume/upload",
        headers={"X-User-Id": user},
        files={"file": ("resume.docx", make_docx(), DOCX_MIME)},
    )


def _ai_calls(purpose: str) -> int:
    with psycopg.connect(TEST_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM ai_call_log WHERE purpose = %s", (purpose,)
            )
            return int(cur.fetchone()[0])


def test_resume_upload_is_idempotent_and_audited(client):
    first = _upload(client)
    assert first.status_code == 201, first.text
    second = _upload(client)
    assert second.status_code == 201, second.text
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["status"] == "pending_review"
    assert _ai_calls("resume_parse") == 1

    reparse = client.post(
        f"/api/profile/resume/{first.json()['data']['id']}/reparse",
        headers={"X-User-Id": "ai-user-a"},
    )
    assert reparse.status_code == 200, reparse.text
    assert _ai_calls("resume_parse") == 2


def test_profile_analysis_reuses_same_revision_and_marks_stale(client):
    headers = {"X-User-Id": "ai-user-a"}
    saved = client.put("/api/profile", json=PROFILE_PAYLOAD, headers=headers)
    assert saved.status_code == 200, saved.text

    first = client.post("/api/profile/analysis", headers=headers)
    assert first.status_code == 200, first.text
    second = client.post("/api/profile/analysis", headers=headers)
    assert second.status_code == 200, second.text
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["stale"] is False
    assert (
        first.json()["data"]["prompt_version"] == PROFILE_ANALYSIS_SPEC.version
    )

    forced = client.post(
        "/api/profile/analysis", json={"force": True}, headers=headers
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["data"]["id"] != first.json()["data"]["id"]

    changed = {
        **PROFILE_PAYLOAD,
        "data": {
            **PROFILE_PAYLOAD["data"],
            "basic": {**PROFILE_PAYLOAD["data"]["basic"], "name": "张三更新"},
        },
    }
    assert client.put("/api/profile", json=changed, headers=headers).status_code == 200
    history = client.get("/api/profile/analysis", headers=headers)
    assert history.status_code == 200
    assert history.json()["data"]["items"][0]["stale"] is True


def test_roadmap_adjustment_keeps_completed_tasks(client):
    headers = {"X-User-Id": "ai-user-a"}
    assert client.put("/api/profile", json=PROFILE_PAYLOAD, headers=headers).status_code == 200

    generated = client.post("/api/roadmap/generate", json={}, headers=headers)
    assert generated.status_code == 201, generated.text
    roadmap_id = generated.json()["data"]["id"]
    assert client.post(f"/api/roadmap/{roadmap_id}/confirm", headers=headers).status_code == 200

    current = client.get("/api/roadmap/current", headers=headers)
    assert current.status_code == 200
    roadmap = current.json()["data"]["roadmap"]
    task = roadmap["stages"][0]["tasks"][0]
    completed = client.patch(
        f"/api/roadmap/tasks/{task['id']}",
        json={"status": "completed", "outcome": "已完成并验证"},
        headers=headers,
    )
    assert completed.status_code == 200, completed.text

    adjusted = client.post(
        f"/api/roadmap/{roadmap_id}/adjust", headers=headers
    )
    assert adjusted.status_code == 200, adjusted.text
    draft = adjusted.json()["data"]
    assert draft["id"] != roadmap_id
    assert draft["status"] == "draft"
    tasks = [
        (item["title"], item["status"])
        for stage in draft["stages"]
        for item in stage["tasks"]
    ]
    assert (task["title"], "completed") in tasks

    cross = client.post(
        f"/api/roadmap/{roadmap_id}/adjust",
        headers={"X-User-Id": "ai-user-b"},
    )

    assert cross.status_code in (404, 409)


def test_ai_calls_are_isolated_per_user(client):
    assert _upload(client, "ai-user-a").status_code == 201
    assert _upload(client, "ai-user-b").status_code == 201
    with psycopg.connect(TEST_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.external_id, count(*)
                FROM ai_call_log a
                JOIN app_user u ON u.id = a.user_id
                WHERE a.purpose = 'resume_parse'
                GROUP BY u.external_id
                ORDER BY u.external_id
                """
            )
            rows = cur.fetchall()
    assert rows == [("ai-user-a", 1), ("ai-user-b", 1)]
