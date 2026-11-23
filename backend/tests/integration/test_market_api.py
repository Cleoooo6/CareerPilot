
import pytest

pytestmark = pytest.mark.integration


def _job(title, skills, month, city="上海", education="本科", experience="3-5年"):
    return {
        "external_id": f"{title}-{month}-{city}",
        "title": title,
        "company": "合成示例公司",
        "location": city,
        "description": f"负责 {skills} 相关工作；{title}岗位。",
        "education": education,
        "experience": experience,
        "industry": "互联网",
        "posted_at": f"2026-{month:02d}-15T00:00:00+08:00",
    }


def _payload():
    jobs = []
    for month in (9, 10, 11):
        for index in range(4):
            jobs.append(
                _job(
                    "数据分析师" if index < 2 else "后端工程师",
                    "Python、SQL、Excel" if index < 2 else "Python、Docker、Linux",
                    month,
                    city="上海" if index % 2 == 0 else "北京",
                )
            )
    return {
        "source": {
            "name": "e2e_synthetic_market",
            "source_type": "manual_json",
            "dataset_kind": "synthetic",
            "license_note": "合成测试数据，不代表真实招聘市场，仅用于链路验证",
        },
        "jobs": jobs,
    }


def _import(client):
    return client.post("/api/market/import", json=_payload())


def test_market_import_and_statistics(client):
    response = _import(client)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["imported"] == 12
    assert result["duplicates"] == 0

    overview = client.get("/api/market/overview").json()["data"]
    assert overview["total_jobs"] == 12
    assert overview["meta"]["sample_size"] == 12
    assert overview["meta"]["sample_sufficient"] is True
    assert "synthetic" in overview["meta"]["dataset_kinds"]
    assert overview["meta"]["sources"][0]["dataset_kind"] == "synthetic"
    assert "合成测试数据" in overview["meta"]["sources"][0]["license_note"]
    assert any("合成" in warning for warning in overview["meta"]["warnings"])
    assert overview["top_roles"]
    assert overview["top_skills"][0]["skill"] in {"Python", "SQL", "Excel"}

    skills = client.get("/api/market/skills?limit=5").json()["data"]
    assert skills["meta"]["sample_size"] == 12
    assert any(item["skill"] == "Python" for item in skills["items"])

    education = client.get(
        "/api/market/distributions?dimension=education"
    ).json()["data"]
    assert education["items"][0]["name"] == "本科"

    trends = client.get("/api/market/trends?months=6").json()["data"]
    assert trends["insufficient_data"] is False
    assert len(trends["points"]) == 3

    roles = client.get("/api/market/roles").json()["data"]
    assert "数据分析师" in roles["items"]
    assert "后端工程师" in roles["items"]


def test_market_role_filter_and_duplicate_import(client):
    _import(client)
    filtered = client.get(
        "/api/market/overview?role=数据分析师&dataset_kind=synthetic"
    ).json()["data"]
    assert filtered["total_jobs"] == 6
    assert filtered["top_skills"]
    assert all(
        skill["skill"] in {"Python", "SQL", "Excel"}
        for skill in filtered["top_skills"]
    )

    duplicate = _import(client).json()["data"]
    assert duplicate["imported"] == 0
    assert duplicate["duplicates"] == 12
    assert client.get("/api/market/overview").json()["data"]["total_jobs"] == 12


def test_market_empty_and_tool_contracts(client):
    empty = client.get("/api/market/overview?role=不存在的职业").json()["data"]
    assert empty["total_jobs"] == 0
    assert empty["meta"]["sample_sufficient"] is False
    assert empty["meta"]["warnings"]

    _import(client)
    from app.tools.registry import build_default_registry

    registry = build_default_registry()
    insights = registry.execute("get_market_insights", {"role": "数据分析师"})
    assert insights["total_jobs"] == 6
    assert insights["meta"]["sample_size"] == 6
    skills = registry.execute("get_skill_demand", {"role": "数据分析师", "limit": 5})
    assert skills["items"]
    requirements = registry.execute(
        "get_career_market_requirements", {"role": "数据分析师"}
    )
    assert requirements["role"] == "数据分析师"
    assert requirements["overview"]["meta"]["sample_size"] == 6


def test_market_rejects_unsupported_dimension(client):
    response = client.get("/api/market/distributions?dimension=salary")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
