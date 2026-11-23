import json

import pytest

from tests.resume_fixtures import make_docx

pytestmark = pytest.mark.integration

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FICTIONAL_RESUME = """姓名：张三
目标岗位：数据分析师
学历：本科
专业：信息管理与信息系统
所在地：上海
毕业时间：2026
学校：虚构大学
技能：Python、SQL、Excel
项目：校园数据分析项目
实习：虚构科技有限公司
"""


def _profile_payload(target="数据分析师", name="张三"):
    return {
        "data": {
            "basic": {
                "name": name,
                "education_level": "本科",
                "major": "信息管理与信息系统",
                "graduation_year": 2026,
                "location": "上海",
            },
            "goals": {
                "target_role": target,
                "target_industry": "互联网",
                "job_status": "求职中",
                "desired_direction": "数据分析",
            },
            "skills": [
                {
                    "name": "Python",
                    "proficiency": "熟练",
                    "evidence": "课程项目",
                }
            ],
            "education": [
                {
                    "school": "虚构大学",
                    "degree": "本科",
                    "major": "信息管理与信息系统",
                    "start_date": "2022-09",
                    "end_date": "2026-06",
                    "description": "",
                }
            ],
            "projects": [
                {
                    "name": "校园数据分析项目",
                    "role": "开发者",
                    "description": "使用 Python 分析校园数据",
                    "tech_stack": "Python, SQL",
                    "achievements": "完成可视化报告",
                    "start_date": "2025-03",
                    "end_date": "2025-06",
                }
            ],
            "experiences": [
                {
                    "company": "虚构科技有限公司",
                    "position": "数据分析实习生",
                    "start_date": "2025-07",
                    "end_date": "2025-09",
                    "description": "整理业务指标",
                }
            ],
        }
    }


def _profile_data(client, user="user-a"):
    response = client.get("/api/profile", headers={"X-User-Id": user})
    assert response.status_code == 200
    return response.json()["data"]["profile"]


def _create_conversation(client, user="user-a"):
    response = client.post(
        "/api/conversations",
        json={"title": "Stage 03"},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _send(client, conversation_id, content, user="user-a"):
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


def _upload(client, user="user-a", content=FICTIONAL_RESUME):
    return client.post(
        "/api/profile/resume/upload",
        files={"file": ("fictional.docx", make_docx(content), DOCX_MIME)},
        headers={"X-User-Id": user},
    )


def test_profile_crud_and_user_isolation(client):
    assert _profile_data(client) is None
    response = client.put(
        "/api/profile", json=_profile_payload(), headers={"X-User-Id": "user-a"}
    )
    assert response.status_code == 200
    profile = response.json()["data"]
    assert profile["data"]["basic"]["name"] == "张三"
    assert _profile_data(client)["data"]["goals"]["target_role"] == "数据分析师"

    updated = _profile_payload(target="高级数据分析师")
    response = client.put(
        "/api/profile", json=updated, headers={"X-User-Id": "user-a"}
    )
    assert response.status_code == 200
    assert _profile_data(client)["data"]["goals"]["target_role"] == "高级数据分析师"

    other = _profile_payload(target="产品经理", name="李四")
    assert (
        client.put(
            "/api/profile", json=other, headers={"X-User-Id": "user-b"}
        ).status_code
        == 200
    )
    assert _profile_data(client, "user-b")["data"]["basic"]["name"] == "李四"
    assert _profile_data(client)["data"]["basic"]["name"] == "张三"

    response = client.delete("/api/profile", headers={"X-User-Id": "user-a"})
    assert response.status_code == 204
    assert _profile_data(client) is None
    assert _profile_data(client, "user-b") is not None


def test_resume_requires_confirmation_and_merges_selected_sections(client):
    upload = _upload(client)
    assert upload.status_code == 201
    parsed = upload.json()["data"]
    assert parsed["status"] == "pending_review"
    assert parsed["parse_mode"] == "mock"
    assert parsed["parsed_data"]["basic"]["name"] == "张三"
    assert parsed["parsed_data"]["goals"]["target_role"] == "数据分析师"
    assert "stored_filename" not in parsed
    assert _profile_data(client) is None

    resume_id = parsed["id"]
    draft = parsed["parsed_data"]
    draft["goals"]["target_role"] = "高级数据分析师"
    patch = client.patch(
        f"/api/profile/resume/{resume_id}",
        json={"parsed_data": draft},
        headers={"X-User-Id": "user-a"},
    )
    assert patch.status_code == 200
    assert _profile_data(client) is None

    confirm = client.post(
        f"/api/profile/resume/{resume_id}/confirm",
        json={"sections": ["basic", "goals", "skills"]},
        headers={"X-User-Id": "user-a"},
    )
    assert confirm.status_code == 200
    profile = confirm.json()["data"]
    assert profile["data"]["basic"]["name"] == "张三"
    assert profile["data"]["goals"]["target_role"] == "高级数据分析师"
    assert profile["data"]["skills"][0]["name"] == "Python"
    assert profile["data"]["projects"] == []

    resumed = client.get(
        f"/api/profile/resume/{resume_id}", headers={"X-User-Id": "user-a"}
    )
    assert resumed.json()["data"]["status"] == "confirmed"

    assert (
        client.get(
            f"/api/profile/resume/{resume_id}", headers={"X-User-Id": "user-b"}
        ).status_code
        == 404
    )


def test_discard_resume_does_not_change_profile(client):
    upload = _upload(client)
    resume_id = upload.json()["data"]["id"]
    discard = client.post(
        f"/api/profile/resume/{resume_id}/discard", headers={"X-User-Id": "user-a"}
    )
    assert discard.status_code == 200
    assert discard.json()["data"]["status"] == "discarded"
    assert _profile_data(client) is None


def test_resume_rejects_invalid_files(client):
    bad_extension = client.post(
        "/api/profile/resume/upload",
        files={"file": ("resume.txt", b"hello", "text/plain")},
        headers={"X-User-Id": "user-a"},
    )
    assert bad_extension.status_code == 415

    fake_pdf = client.post(
        "/api/profile/resume/upload",
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
        headers={"X-User-Id": "user-a"},
    )
    assert fake_pdf.status_code == 422

    oversized = client.post(
        "/api/profile/resume/upload",
        files={
            "file": (
                "resume.docx",
                b"x" * (10 * 1024 * 1024 + 1),
                DOCX_MIME,
            )
        },
        headers={"X-User-Id": "user-a"},
    )
    assert oversized.status_code == 413


def test_analysis_history_is_append_only(client):
    client.put("/api/profile", json=_profile_payload(), headers={"X-User-Id": "user-a"})
    first = client.post("/api/profile/analysis", headers={"X-User-Id": "user-a"})
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["llm_mode"] == "mock"
    assert "Mock" in first_data["analysis"]["overview"]

    client.put(
        "/api/profile",
        json=_profile_payload(target="高级数据分析师"),
        headers={"X-User-Id": "user-a"},
    )
    second = client.post("/api/profile/analysis", headers={"X-User-Id": "user-a"})
    assert second.status_code == 200
    history = client.get("/api/profile/analysis", headers={"X-User-Id": "user-a"})
    items = history.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["id"] == second.json()["data"]["id"]
    assert items[1]["id"] == first_data["id"]
    assert (
        client.get(
            f"/api/profile/analysis/{first_data['id']}", headers={"X-User-Id": "user-b"}
        ).status_code
        == 404
    )


def test_chat_uses_profile_only_for_relevant_intents_and_does_not_write_profile(client):
    client.put("/api/profile", json=_profile_payload(), headers={"X-User-Id": "user-a"})
    conversation = _create_conversation(client)

    general = _send(client, conversation, "你好")
    general_intent = next(e for e in general if e["event"] == "intent_detected")
    assert general_intent["data"]["profile_used"] is False

    resume = _send(client, conversation, "帮我看看简历")
    resume_intent = next(e for e in resume if e["event"] == "intent_detected")
    assert resume_intent["data"]["profile_used"] is True

    update = _send(client, conversation, "把我的目标岗位改成产品经理")
    assert update[-1]["event"] == "task_completed"
    assert _profile_data(client)["data"]["goals"]["target_role"] == "数据分析师"


def test_analysis_requires_profile(client):
    response = client.post("/api/profile/analysis", headers={"X-User-Id": "user-a"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROFILE_EMPTY"
