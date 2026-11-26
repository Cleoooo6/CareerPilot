import asyncio

from app.industry_pulse.sources import FeedSource
from app.services.industry_pulse_service import get_industry_pulse_service

SOURCE = FeedSource(
    key="pulse-personal",
    name="Pulse Personal",
    industry="digital_tech_comms",
    industries=("digital_tech_comms",),
    region="CN",
    content_policy="metadata_only",
    feed_url="https://example.invalid/personal.xml",
    homepage_url="https://example.invalid/",
)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>5G通信设备发布 个人一</title>
    <link>https://example.invalid/personal/1</link>
    <pubDate>Mon, 24 Nov 2026 01:00:00 GMT</pubDate></item>
  <item><title>人工智能大模型发布 个人二</title>
    <link>https://example.invalid/personal/2</link>
    <pubDate>Mon, 24 Nov 2026 02:00:00 GMT</pubDate></item>
  <item><title>华为发布新款手机并在电商渠道首发</title>
    <link>https://example.invalid/personal/3</link>
    <pubDate>Mon, 24 Nov 2026 03:00:00 GMT</pubDate></item>
  <item><title>长期左侧卧睡，真的会压迫损伤心脏吗？</title>
    <link>https://example.invalid/personal/4</link>
    <pubDate>Mon, 24 Nov 2026 04:00:00 GMT</pubDate></item>
</channel></rss>""".encode()


async def _fetch(_source: FeedSource) -> bytes:
    return RSS


def _save_profile(client, user_id: str) -> None:
    response = client.put(
        "/api/profile",
        headers={"X-User-Id": user_id},
        json={
            "data": {
                "basic": {"location": "上海", "education_level": "本科"},
                "goals": {
                    "target_role": "数据分析师",
                    "target_industry": "互联网",
                    "desired_direction": "数据分析",
                },
                "skills": [
                    {
                        "name": "Python",
                        "evidence": "课程项目",
                        "verification": "confirmed",
                    },
                    {
                        "name": "SQL",
                        "evidence": "",
                        "verification": "confirmed",
                    },
                ],
            }
        },
    )
    assert response.status_code == 200


def test_personal_pulse_filters_and_paginates_server_side(client):
    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(SOURCE,), fetch_func=_fetch
        )
    )
    assert run["articles_inserted"] == 4
    _save_profile(client, "pulse-personal-user")

    response = client.get(
        "/api/industry-pulse/personal",
        headers={"X-User-Id": "pulse-personal-user"},
        params={"limit": 1, "offset": 0},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["view"] == "personal"
    assert payload["profile_sufficient"] is True
    assert payload["total"] == 3
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["match_types"]
    assert item["match_reasons"]
    assert "目标行业" in item["match_reasons"][0]
    assert "长期左侧卧睡" not in item["title"]

    second = client.get(
        "/api/industry-pulse/personal",
        headers={"X-User-Id": "pulse-personal-user"},
        params={"limit": 1, "offset": 1},
    ).json()["data"]
    assert second["total"] == 3
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] != item["id"]

    filtered = client.get(
        "/api/industry-pulse/personal",
        headers={"X-User-Id": "pulse-personal-user"},
        params={"industry": "consumer_retail_services", "limit": 20},
    ).json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["industries"].count("consumer_retail_services") == 1


def test_personal_pulse_does_not_leak_other_users(client):
    asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(SOURCE,), fetch_func=_fetch
        )
    )
    _save_profile(client, "pulse-owner")
    other = client.get(
        "/api/industry-pulse/personal",
        headers={"X-User-Id": "pulse-other"},
    ).json()["data"]
    assert other["profile_sufficient"] is False
    assert other["items"] == []
    assert other["total"] == 0
    assert "目标岗位" in other["profile_missing"]