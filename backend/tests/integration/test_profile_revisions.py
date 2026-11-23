import pytest

from tests.resume_fixtures import make_docx

pytestmark = pytest.mark.integration

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FICTIONAL_RESUME = """姓名：张三
目标岗位：数据分析师
学历：本科
所在地：上海
技能：Python、SQL、Excel
"""


def _payload(target="数据分析师", proficiency="熟练"):
    return {
        "data": {
            "basic": {"name": "张三"},
            "goals": {"target_role": target},
            "skills": [
                {
                    "id": "skill-python",
                    "name": "Python",
                    "proficiency": proficiency,
                    "evidence": "课程项目",
                    "category": "编程语言",
                }
            ],
            "education": [],
            "projects": [],
            "experiences": [],
        }
    }


def _revisions(client, user="user-a"):
    response = client.get("/api/profile/revisions", headers={"X-User-Id": user})
    assert response.status_code == 200
    return response.json()["data"]["items"]


def test_profile_revisions_are_append_only_and_user_scoped(client):
    first = client.put(
        "/api/profile", json=_payload(), headers={"X-User-Id": "user-a"}
    )
    assert first.status_code == 200
    first_profile = first.json()["data"]
    first_skill = first_profile["data"]["skills"][0]
    assert first_skill["source"] == "manual"
    assert first_skill["verification"] == "confirmed"
    assert first_skill["category"] == "编程语言"
    assert first_skill["updated_at"]

    second = client.put(
        "/api/profile",
        json=_payload(target="高级数据分析师"),
        headers={"X-User-Id": "user-a"},
    )
    assert second.status_code == 200
    second_profile = second.json()["data"]
    assert second_profile["id"] == first_profile["id"]
    assert (
        second_profile["data"]["skills"][0]["updated_at"]
        == first_skill["updated_at"]
    )
    assert second_profile["data"]["skills"][0]["source"] == "manual"

    revisions = _revisions(client)
    assert [item["version"] for item in revisions] == [2, 1]
    assert all(item["change_source"] == "manual" for item in revisions)
    assert "data" not in revisions[0]

    detail = client.get(
        f"/api/profile/revisions/{revisions[0]['id']}",
        headers={"X-User-Id": "user-a"},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["data"]["goals"]["target_role"] == "高级数据分析师"

    assert _revisions(client, "user-b") == []
    assert (
        client.get(
            f"/api/profile/revisions/{revisions[0]['id']}",
            headers={"X-User-Id": "user-b"},
        ).status_code
        == 404
    )


def test_resume_confirmation_records_resume_source_and_revision(client):
    client.put("/api/profile", json=_payload(), headers={"X-User-Id": "user-a"})

    upload = client.post(
        "/api/profile/resume/upload",
        files={"file": ("fictional.docx", make_docx(FICTIONAL_RESUME), DOCX_MIME)},
        headers={"X-User-Id": "user-a"},
    )
    assert upload.status_code == 201
    resume_id = upload.json()["data"]["id"]

    confirm = client.post(
        f"/api/profile/resume/{resume_id}/confirm",
        json={"sections": ["skills"]},
        headers={"X-User-Id": "user-a"},
    )
    assert confirm.status_code == 200
    skills = confirm.json()["data"]["data"]["skills"]
    assert len(skills) == 3
    assert {item["name"] for item in skills} == {"Python", "SQL", "Excel"}
    assert all(item["source"] == "resume" for item in skills)
    assert all(item["verification"] == "confirmed" for item in skills)
    assert all(item["updated_at"] for item in skills)

    revisions = _revisions(client)
    assert [item["version"] for item in revisions] == [2, 1]
    assert revisions[0]["change_source"] == "resume"


def test_delete_profile_removes_revision_history(client):
    client.put("/api/profile", json=_payload(), headers={"X-User-Id": "user-a"})
    assert len(_revisions(client)) == 1

    response = client.delete("/api/profile", headers={"X-User-Id": "user-a"})
    assert response.status_code == 204
    assert _revisions(client) == []
