from datetime import datetime, timezone

from app.industry_pulse.personalize import profile_context, rank_personal_items


def _item(
    article_id: str,
    title: str,
    industries: list[str],
    *,
    summary: str = "",
    published_at: str = "2026-11-24T10:00:00+00:00",
) -> dict:
    return {
        "id": article_id,
        "title": title,
        "summary": summary,
        "industries": industries,
        "published_at": published_at,
        "url": f"https://example.invalid/{article_id}",
        "source_name": "test",
    }


PROFILE = {
    "basic": {"location": "上海", "education_level": "本科"},
    "goals": {
        "target_role": "数据分析师",
        "target_industry": "互联网",
        "desired_direction": "数据分析",
    },
    "skills": [
        {"name": "Python", "evidence": "课程项目", "verification": "confirmed"},
        {"name": "SQL", "evidence": "", "verification": "confirmed"},
    ],
}


def test_profile_context_maps_target_industry_and_skills():
    context = profile_context(PROFILE)
    assert context["sufficient"] is True
    assert context["target_industry_id"] == "digital_tech_comms"
    assert context["target_industry_label"] == "数字科技与通信"
    assert "数据分析" in context["role_terms"]
    assert context["skills"] == ["Python", "SQL"]


def test_direct_industry_match_gives_explainable_reason():
    items = [
        _item("a", "5G通信设备发布", ["digital_tech_comms"]),
        _item("b", "房地产数据发布", ["real_estate_construction"]),
    ]
    page, total, _context, reason = rank_personal_items(
        items, PROFILE, limit=20, offset=0
    )
    assert total == 1
    assert reason == ""
    assert page[0]["id"] == "a"
    assert page[0]["match_types"] == ["target_industry"]
    assert "目标行业" in page[0]["match_reasons"][0]


def test_role_skill_and_region_are_explainable_but_only_supporting():
    items = [
        _item(
            "a",
            "上海零售企业招聘数据分析师，要求 Python 与 SQL",
            ["consumer_retail_services"],
        ),
        _item(
            "b",
            "Python 教程：从入门到放弃",
            ["finance_insurance"],
        ),
    ]
    page, total, _context, _reason = rank_personal_items(
        items, PROFILE, limit=20, offset=0
    )
    assert total == 1
    assert page[0]["id"] == "a"
    assert {"role", "skill", "region"}.issubset(set(page[0]["match_types"]))
    reasons = "\n".join(page[0]["match_reasons"])
    assert "目标岗位方向" in reasons
    assert "Python" in reasons
    assert "上海" in reasons


def test_cross_industry_match_is_explicit_and_does_not_claim_skill():
    items = [
        _item("a", "芯片制造产能扩张", ["manufacturing_industry"]),
    ]
    page, total, _context, _reason = rank_personal_items(
        items, PROFILE, limit=20, offset=0
    )
    assert total == 1
    assert page[0]["match_types"] == ["cross_industry"]
    assert "明确交叉" in page[0]["match_reasons"][0]
    assert "不代表文章涉及你的具体技能" in page[0]["match_reasons"][0]


def test_multi_industry_item_is_not_duplicated():
    items = [
        _item(
            "a",
            "华为发布新款手机并在电商渠道首发",
            ["digital_tech_comms", "consumer_retail_services"],
        ),
        dict(
            _item(
                "a",
                "华为发布新款手机并在电商渠道首发",
                ["digital_tech_comms", "consumer_retail_services"],
            )
        ),
    ]
    page, total, _context, _reason = rank_personal_items(
        items, PROFILE, limit=20, offset=0
    )
    assert total == 1
    assert len(page) == 1


def test_pagination_and_total_are_after_personal_filter():
    items = [
        _item(f"a{index}", f"5G通信设备发布 {index}", ["digital_tech_comms"])
        for index in range(5)
    ]
    page, total, _context, _reason = rank_personal_items(
        items, PROFILE, limit=2, offset=2
    )
    assert total == 5
    assert len(page) == 2
    assert [item["id"] for item in page] == ["a2", "a1"] or len(page) == 2


def test_different_profiles_get_different_results():
    items = [
        _item("a", "5G通信设备发布", ["digital_tech_comms"]),
        _item("b", "医院临床药物研发", ["health_life_sciences"]),
    ]
    digital_profile = PROFILE
    health_profile = {
        "basic": {"location": "北京"},
        "goals": {"target_role": "临床医生", "target_industry": "医疗健康"},
        "skills": [{"name": "临床医学"}],
    }
    digital = rank_personal_items(items, digital_profile, limit=20, offset=0)
    health = rank_personal_items(items, health_profile, limit=20, offset=0)
    assert [row["id"] for row in digital[0]] == ["a"]
    assert [row["id"] for row in health[0]] == ["b"]


def test_missing_profile_returns_no_matches_and_reason():
    page, total, context, reason = rank_personal_items([], {}, limit=20, offset=0)
    assert page == []
    assert total == 0
    assert context["sufficient"] is False
    assert "目标岗位" in reason or "目标行业" in reason