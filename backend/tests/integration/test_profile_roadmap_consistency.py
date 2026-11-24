import pytest

pytestmark = pytest.mark.integration

SOURCE = {
    "name": "跨页一致性合成测试源",
    "source_type": "synthetic_fixture",
    "dataset_kind": "synthetic",
    "license_note": "仅用于自动化测试的合成数据，不代表真实招聘市场。",
}

SKILL_SETS = [
    ["Python", "SQL", "Excel", "数据可视化"],
    ["Python", "SQL", "Tableau", "数据建模"],
    ["Python", "统计分析", "项目管理", "A/B 测试"],
    ["Python", "ETL", "Hive", "Pandas"],
    ["SQL", "Spark", "机器学习", "数据可视化"],
    ["SQL", "Excel", "Tableau", "统计分析"],
]


def _profile_payload() -> dict:
    return {
        "data": {
            "basic": {
                "name": "一致性测试用户",
                "education_level": "本科",
                "major": "信息管理",
                "location": "上海",
            },
            "goals": {
                "target_role": "数据分析师",
                "target_industry": "互联网",
                "job_status": "求职中",
                "desired_direction": "",
            },
            "skills": [
                {
                    "id": "consistency-python",
                    "name": "Python",
                    "proficiency": "熟练",
                    "evidence": "课程项目",
                    "category": "编程语言",
                },
                {
                    "id": "consistency-sql",
                    "name": "SQL",
                    "proficiency": "",
                    "evidence": "",
                    "category": "数据工具",
                },
            ],
            "education": [],
            "projects": [],
            "experiences": [],
        }
    }


def _import_market(client) -> None:
    jobs = []
    for index, skills in enumerate(SKILL_SETS):
        jobs.append(
            {
                "external_id": f"consistency-{index}",
                "title": "数据分析师",
                "company": "合成·一致性测试公司",
                "location": "上海",
                "description": "岗位要求：" + "、".join(skills),
                "education": "本科",
                "experience": "1-3年",
                "posted_at": f"2026-09-{index + 1:02d}T09:00:00+08:00",
            }
        )
    response = client.post(
        "/api/market/import",
        json={"source": SOURCE, "jobs": jobs},
        headers={"X-User-Id": "consistency-user"},
    )
    assert response.status_code == 200


def _gap_items(gap: dict) -> list[dict]:
    return [
        item
        for bucket in ("matched", "to_improve", "not_recorded")
        for item in gap[bucket]
    ]


def test_market_and_roadmap_share_the_same_skill_demand(client):
    profile = client.put(
        "/api/profile",
        json=_profile_payload(),
        headers={"X-User-Id": "consistency-user"},
    )
    assert profile.status_code == 200
    _import_market(client)

    market = client.get(
        "/api/market/skills?role=数据分析师&limit=20"
    ).json()["data"]
    gap = client.get(
        "/api/roadmap/gap", headers={"X-User-Id": "consistency-user"}
    ).json()["data"]

    market_items = {item["skill"]: item for item in market["items"]}
    gap_items = {item["name"]: item for item in _gap_items(gap)}

    assert market["meta"]["sample_size"] == 6
    assert gap["meta"]["sample_size"] == 6
    assert set(market_items) == set(gap_items)
    assert len(market_items) == 14
    for name, market_item in market_items.items():
        gap_item = gap_items[name]
        assert gap_item["market_count"] == market_item["count"]
        assert gap_item["market_share"] == market_item["share"]

    assert market_items["Python"]["count"] == 4
    assert market_items["Python"]["share"] == pytest.approx(4 / 6, abs=1e-4)
    assert gap_items["Python"]["market_count"] == 4
    assert gap_items["Python"]["market_share"] == pytest.approx(4 / 6, abs=1e-4)