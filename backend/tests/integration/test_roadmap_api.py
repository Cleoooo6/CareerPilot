import asyncio
import json
import threading
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.errors import UniqueViolation

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.roadmap_service import get_roadmap_service

pytestmark = pytest.mark.integration

SOURCE = {
    "name": "Roadmap 合成测试源",
    "source_type": "synthetic_fixture",
    "dataset_kind": "synthetic",
    "license_note": "仅用于自动化测试的合成数据，不代表真实招聘市场。",
}
SKILL_DISTRIBUTION = ["Python"] * 4 + ["SQL"] * 3 + ["Spark"] * 2 + [
    "Tableau"
]


def _profile_payload(target: str = "数据分析师") -> dict:
    return {
        "data": {
            "basic": {
                "name": "张三",
                "education_level": "本科",
                "major": "信息管理",
                "location": "上海",
            },
            "goals": {
                "target_role": target,
                "target_industry": "互联网",
                "job_status": "求职中",
                "desired_direction": "",
            },
            "skills": [
                {
                    "id": "skill-python",
                    "name": "Python",
                    "proficiency": "熟练",
                    "evidence": "课程项目",
                    "category": "编程语言",
                },
                {
                    "id": "skill-sql",
                    "name": "SQL",
                    "proficiency": "",
                    "evidence": "",
                    "category": "数据工具",
                },
                {
                    "id": "skill-vue",
                    "name": "Vue",
                    "proficiency": "熟练",
                    "evidence": "前端项目",
                    "category": "前端",
                },
            ],
            "education": [],
            "projects": [],
            "experiences": [],
        }
    }


def _put_profile(client, user: str = "user-a", target: str = "数据分析师"):
    response = client.put(
        "/api/profile",
        json=_profile_payload(target),
        headers={"X-User-Id": user},
    )
    assert response.status_code == 200
    return response.json()["data"]


def _import_market(
    client,
    user: str = "user-a",
    *,
    role: str = "数据分析师",
    distribution: list[str] | None = None,
):
    rows = distribution or SKILL_DISTRIBUTION
    jobs = []
    for index, skill in enumerate(rows):
        jobs.append(
            {
                "external_id": f"roadmap-syn-{role}-{index}",
                "title": role,
                "company": "合成·测试公司",
                "location": "上海",
                "description": f"岗位要求熟练使用 {skill} 完成业务分析。",
                "education": "本科",
                "experience": "1-3年",
                "posted_at": f"2026-09-{index + 1:02d}T09:00:00+08:00",
            }
        )
    response = client.post(
        "/api/market/import",
        json={"source": SOURCE, "jobs": jobs},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 200
    assert response.json()["data"]["imported"] == len(rows)


def _generate(
    client, user: str = "user-a", *, regenerate: bool = False
):
    response = client.post(
        "/api/roadmap/generate",
        json={"regenerate": regenerate},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201
    return response.json()["data"]


def _current(client, user: str = "user-a"):
    response = client.get(
        "/api/roadmap/current", headers={"X-User-Id": user}
    )
    assert response.status_code == 200
    return response.json()["data"]["roadmap"]


def _profile_user_id(client, user: str = "user-a") -> UUID:
    response = client.get("/api/profile", headers={"X-User-Id": user})
    assert response.status_code == 200
    profile = response.json()["data"]["profile"]
    assert profile is not None
    return UUID(profile["user_id"])


def test_gap_requires_target_role(client):
    response = client.get("/api/roadmap/gap", headers={"X-User-Id": "user-a"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROADMAP_TARGET_REQUIRED"

    generated = client.post(
        "/api/roadmap/generate", json={}, headers={"X-User-Id": "user-a"}
    )
    assert generated.status_code == 409


def test_gap_uses_synthetic_market_without_inferring_ability(client):
    _put_profile(client)
    _import_market(client)

    response = client.get("/api/roadmap/gap", headers={"X-User-Id": "user-a"})
    assert response.status_code == 200
    gap = response.json()["data"]
    assert gap["basis"] == "market"
    assert gap["meta"]["sample_size"] == 10
    assert gap["meta"]["sample_sufficient"] is True
    assert gap["meta"]["dataset_kinds"] == ["synthetic"]
    assert any("合成" in warning for warning in gap["warnings"])
    assert "Python" in [item["name"] for item in gap["matched"]]
    assert "SQL" in [item["name"] for item in gap["to_improve"]]
    assert {"Spark", "Tableau"} == {
        item["name"] for item in gap["not_recorded"]
    }
    reasons = [item["reason"] for item in gap["not_recorded"]]
    assert all("没有记录不等于不具备" in reason for reason in reasons)
    assert "Vue" in [item["name"] for item in gap["profile_skills"]]


def test_generate_confirm_and_version_switch(client):
    _put_profile(client)
    _import_market(client)

    draft = _generate(client)
    assert draft["status"] == "draft"
    assert draft["version"] == 1
    assert draft["generation_mode"] == "mock"
    assert draft["provider"] == "zhipu"
    assert draft["model"] == "glm-4.7-flash"
    assert draft["gap"]["basis"] == "market"
    assert draft["gap"]["meta"]["sample_size"] == 10
    assert len(draft["stages"]) >= 3
    assert draft["task_total"] >= 2
    assert all(
        task["acceptance_criteria"].strip()
        for stage in draft["stages"]
        for task in stage["tasks"]
    )
    assert _current(client) is None
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["version"] for item in drafts] == [1]

    second = _generate(client, regenerate=True)
    assert second["version"] == 2
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["version"] for item in drafts] == [2]

    confirmed = client.post(
        f"/api/roadmap/{second['id']}/confirm", headers={"X-User-Id": "user-a"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "active"
    assert confirmed.json()["data"]["confirmed_at"] is not None
    assert _current(client)["version"] == 2

    third = _generate(client, regenerate=True)
    assert third["version"] == 3
    assert _current(client)["version"] == 2

    confirmed_third = client.post(
        f"/api/roadmap/{third['id']}/confirm", headers={"X-User-Id": "user-a"}
    )
    assert confirmed_third.status_code == 200
    current = _current(client)
    assert current["version"] == 3
    history = client.get(
        "/api/roadmap/history", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [(item["version"], item["status"]) for item in history] == [
        (3, "active"),
        (2, "archived"),
    ]

    assert (
        client.get(
            f"/api/roadmap/{third['id']}", headers={"X-User-Id": "user-b"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/roadmap/{third['id']}/confirm",
            headers={"X-User-Id": "user-b"},
        ).status_code
        == 404
    )
    assert _current(client, "user-b") is None
    assert (
        client.get("/api/roadmap/drafts", headers={"X-User-Id": "user-b"})
        .json()["data"]["items"]
        == []
    )


def test_generate_reuses_unchanged_draft_and_allows_explicit_regenerate(client):
    _put_profile(client)
    _import_market(client)
    first = _generate(client)
    reused = _generate(client)
    assert reused["id"] == first["id"]
    assert reused["version"] == first["version"]
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["version"] for item in drafts] == [first["version"]]

    regenerated = _generate(client, regenerate=True)
    assert regenerated["id"] != first["id"]
    assert regenerated["version"] == first["version"] + 1
    old = client.get(
        f"/api/roadmap/{first['id']}", headers={"X-User-Id": "user-a"}
    ).json()["data"]
    assert old["status"] == "discarded"
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["version"] for item in drafts] == [regenerated["version"]]


def test_discard_draft_keeps_active_roadmap(client):
    _put_profile(client)
    _import_market(client)
    first = _generate(client)
    client.post(
        f"/api/roadmap/{first['id']}/confirm", headers={"X-User-Id": "user-a"}
    )
    second = _generate(client)

    discarded = client.post(
        f"/api/roadmap/{second['id']}/discard", headers={"X-User-Id": "user-a"}
    )
    assert discarded.status_code == 200
    assert discarded.json()["data"]["status"] == "discarded"
    assert _current(client)["version"] == 1
    assert (
        client.get("/api/roadmap/drafts", headers={"X-User-Id": "user-a"})
        .json()["data"]["items"]
        == []
    )
    assert (
        client.post(
            f"/api/roadmap/{second['id']}/confirm",
            headers={"X-User-Id": "user-a"},
        ).status_code
        == 409
    )


def test_task_progress_outcome_and_profile_unchanged(client):
    _put_profile(client)
    _import_market(client)
    draft = _generate(client)
    client.post(
        f"/api/roadmap/{draft['id']}/confirm", headers={"X-User-Id": "user-a"}
    )
    current = _current(client)
    task = current["stages"][0]["tasks"][0]
    before = client.get("/api/profile", headers={"X-User-Id": "user-a"}).json()[
        "data"
    ]["profile"]["data"]["skills"]

    started = client.patch(
        f"/api/roadmap/tasks/{task['id']}",
        json={"status": "in_progress"},
        headers={"X-User-Id": "user-a"},
    )
    assert started.status_code == 200
    assert started.json()["data"]["task"]["status"] == "in_progress"

    completed = client.patch(
        f"/api/roadmap/tasks/{task['id']}",
        json={
            "status": "completed",
            "outcome": "完成 SQL 分析项目，仓库链接：https://example.invalid/repo",
        },
        headers={"X-User-Id": "user-a"},
    )
    assert completed.status_code == 200
    updated = completed.json()["data"]["task"]
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None
    assert "https://example.invalid/repo" in updated["outcome"]

    after = client.get("/api/profile", headers={"X-User-Id": "user-a"}).json()[
        "data"
    ]["profile"]["data"]["skills"]
    assert after == before

    draft_second = _generate(client)
    draft_task = draft_second["stages"][0]["tasks"][0]
    blocked = client.patch(
        f"/api/roadmap/tasks/{draft_task['id']}",
        json={"status": "completed"},
        headers={"X-User-Id": "user-a"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ROADMAP_NOT_ACTIVE"

    assert (
        client.patch(
            "/api/roadmap/tasks/00000000-0000-0000-0000-000000000000",
            json={"status": "completed"},
            headers={"X-User-Id": "user-a"},
        ).status_code
        == 404
    )


def test_general_fallback_when_no_market_sample(client):
    _put_profile(client, target="稀有岗位XYZ")

    gap_response = client.get(
        "/api/roadmap/gap", headers={"X-User-Id": "user-a"}
    )
    assert gap_response.status_code == 200
    gap = gap_response.json()["data"]
    assert gap["basis"] == "general"
    assert gap["not_recorded"] == []
    assert any("没有可用的市场样本" in warning for warning in gap["warnings"])

    generated = _generate(client)
    assert generated["gap"]["basis"] == "general"
    assert generated["generation_mode"] == "mock"


def test_insufficient_sample_is_reference_only(client):
    _put_profile(client)
    _import_market(client, distribution=["Python"] * 3)
    gap = client.get(
        "/api/roadmap/gap", headers={"X-User-Id": "user-a"}
    ).json()["data"]
    assert gap["basis"] == "market"
    assert gap["reference_only"] is True
    assert gap["meta"]["sample_sufficient"] is False
    assert any("参考" in warning for warning in gap["warnings"])

    generated = _generate(client)
    assert generated["gap"]["reference_only"] is True
    assert "参考" in generated["summary"]


def test_confirm_and_discard_require_draft(client):
    _put_profile(client)
    _import_market(client)
    roadmap = _generate(client)
    client.post(
        f"/api/roadmap/{roadmap['id']}/confirm", headers={"X-User-Id": "user-a"}
    )

    confirm_again = client.post(
        f"/api/roadmap/{roadmap['id']}/confirm", headers={"X-User-Id": "user-a"}
    )
    assert confirm_again.status_code == 409
    assert confirm_again.json()["error"]["code"] == "ROADMAP_NOT_DRAFT"

    discard_active = client.post(
        f"/api/roadmap/{roadmap['id']}/discard", headers={"X-User-Id": "user-a"}
    )
    assert discard_active.status_code == 409

def _create_conversation(client, user: str = "user-a") -> str:
    response = client.post(
        "/api/conversations",
        json={"title": "Roadmap Advisor"},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _send(client, conversation_id: str, content: str, user: str = "user-a"):
    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages",
        json={"content": content},
        headers={"X-User-Id": user},
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event_name = None
        payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                payload = json.loads(line[6:])
        if event_name and payload:
            events.append(payload)
    return events


def test_advisor_generates_draft_but_does_not_confirm(client):
    _put_profile(client)
    _import_market(client)
    conversation = _create_conversation(client)

    events = _send(client, conversation, "帮我生成一份学习路线")
    intent = next(
        event for event in events if event["event"] == "intent_detected"
    )["data"]["intent"]
    assert intent == "career_planning"
    completed = next(
        event for event in events if event["event"] == "task_completed"
    )["data"]
    assert completed["roadmap_used"] is True
    draft_id = completed["roadmap_draft_id"]
    assert draft_id
    assert _current(client) is None

    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["id"] for item in drafts] == [draft_id]

    review = _send(client, conversation, "查看我的成长路线")
    reviewed = next(
        event for event in review if event["event"] == "task_completed"
    )["data"]
    assert reviewed["roadmap_used"] is True
    assert reviewed["roadmap_draft_id"] is None
    drafts_after = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert [item["id"] for item in drafts_after] == [draft_id]

def _completed(events):
    return next(
        event for event in events if event["event"] == "task_completed"
    )["data"]


def test_advisor_view_does_not_generate_and_reuses_unchanged_draft(client):
    _put_profile(client)
    _import_market(client)
    conversation = _create_conversation(client)

    initial = _completed(_send(client, conversation, "查看我的成长路线"))
    assert initial["roadmap_used"] is True
    assert initial["roadmap_draft_id"] is None
    assert (
        client.get("/api/roadmap/drafts", headers={"X-User-Id": "user-a"})
        .json()["data"]["items"]
        == []
    )

    first = _completed(_send(client, conversation, "帮我生成学习计划"))
    assert first["roadmap_draft_id"]
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) == 1
    first_version = drafts[0]["version"]

    reused = _completed(_send(client, conversation, "帮我生成学习计划"))
    assert reused["roadmap_draft_id"] == first["roadmap_draft_id"]
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) == 1
    assert drafts[0]["version"] == first_version

    regenerated = _completed(
        _send(client, conversation, "重新生成学习计划")
    )
    assert regenerated["roadmap_draft_id"] != first["roadmap_draft_id"]
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) == 1
    assert drafts[0]["version"] > first_version
    regenerated_version = drafts[0]["version"]

    reread = _completed(
        _send(client, conversation, "重新看看我的成长路线")
    )
    assert reread["roadmap_draft_id"] is None
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) == 1
    assert drafts[0]["version"] == regenerated_version


def test_concurrent_generate_creates_single_draft(client):
    _put_profile(client)
    _import_market(client)
    user_id = _profile_user_id(client)
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker() -> None:
        barrier.wait()
        try:
            results.append(
                asyncio.run(get_roadmap_service().generate_draft(user_id))
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(results) == 2
    assert {str(result[0].id) for result in results} == {
        str(results[0][0].id)
    }
    assert {result[0].version for result in results} == {1}
    assert {result[1] for result in results} == {False, True}
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) == 1


def test_concurrent_confirm_same_draft_has_clear_conflict(client):
    _put_profile(client)
    _import_market(client)
    draft = _generate(client)
    user_id = _profile_user_id(client)
    roadmap_id = UUID(draft["id"])
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker() -> None:
        barrier.wait()
        try:
            results.append(
                asyncio.run(
                    get_roadmap_service().confirm(user_id, roadmap_id)
                )
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], AppError)
    assert errors[0].status_code == 409
    assert errors[0].code in {
        "ROADMAP_NOT_DRAFT",
        "ROADMAP_CONFIRM_CONFLICT",
    }
    assert _current(client)["id"] == draft["id"]


def test_unique_draft_index_prevents_second_draft(client):
    _put_profile(client)
    _import_market(client)
    _generate(client)
    user_id = _profile_user_id(client)
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 "
                "FROM career_roadmap WHERE user_id = %s",
                (user_id,),
            )
            version = cur.fetchone()[0]
            try:
                with conn.transaction():
                    cur.execute(
                        """
                        INSERT INTO career_roadmap
                            (id, user_id, target_role, status, version, title,
                             summary, gap_snapshot, generation_mode, provider,
                             model)
                        VALUES (%s, %s, '数据分析师', 'draft', %s,
                                '并发重复草稿', '', '{}'::jsonb,
                                'mock', 'zhipu', 'glm-4.7-flash')
                        """,
                        (uuid4(), user_id, version),
                    )
            except UniqueViolation:
                pass
            else:
                raise AssertionError("unique draft index is not enforced")


def test_concurrent_confirm_active_and_draft_has_clear_conflict(client):
    _put_profile(client)
    _import_market(client)
    first = _generate(client)
    confirmed = client.post(
        f"/api/roadmap/{first['id']}/confirm",
        headers={"X-User-Id": "user-a"},
    )
    assert confirmed.status_code == 200
    second = _generate(client, regenerate=True)
    user_id = _profile_user_id(client)
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def worker(roadmap_id: UUID) -> None:
        barrier.wait()
        try:
            results.append(
                asyncio.run(
                    get_roadmap_service().confirm(user_id, roadmap_id)
                )
            )
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(UUID(first["id"]),)),
        threading.Thread(target=worker, args=(UUID(second["id"]),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], AppError)
    assert errors[0].status_code == 409
    assert _current(client)["id"] == second["id"]


def test_concurrent_generate_and_confirm_keep_single_active(client):
    _put_profile(client)
    _import_market(client)
    first = _generate(client)
    confirmed = client.post(
        f"/api/roadmap/{first['id']}/confirm",
        headers={"X-User-Id": "user-a"},
    )
    assert confirmed.status_code == 200
    second = _generate(client, regenerate=True)
    user_id = _profile_user_id(client)
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def generate_worker() -> None:
        barrier.wait()
        try:
            results.append(
                asyncio.run(
                    get_roadmap_service().generate_draft(
                        user_id, regenerate=True
                    )
                )
            )
        except Exception as exc:
            errors.append(exc)

    def confirm_worker() -> None:
        barrier.wait()
        try:
            results.append(
                asyncio.run(
                    get_roadmap_service().confirm(
                        user_id, UUID(second["id"])
                    )
                )
            )
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=generate_worker),
        threading.Thread(target=confirm_worker),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(
        isinstance(exc, AppError) and exc.status_code == 409
        for exc in errors
    )
    assert _current(client) is not None
    drafts = client.get(
        "/api/roadmap/drafts", headers={"X-User-Id": "user-a"}
    ).json()["data"]["items"]
    assert len(drafts) <= 1
