import asyncio
from types import SimpleNamespace

import pytest

from app.industry_pulse.sources import FeedSource
from app.services.industry_pulse_service import get_industry_pulse_service

pytestmark = pytest.mark.integration

SOURCE = FeedSource(
    key="integration-rss",
    name="Integration RSS",
    industry="digital_tech_comms",
    industries=("digital_tech_comms",),
    region="CN",
    content_policy="feed_excerpt",
    feed_url="https://example.invalid/rss",
    homepage_url="https://example.invalid/",
    license_note="测试 RSS，仅用于隔离测试库。",
)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>5G通信设备发布 动态一</title>
    <link>https://example.invalid/news/1?utm_source=test</link>
    <description>第一条真实结构测试摘要。</description>
    <pubDate>Mon, 24 Nov 2026 01:00:00 GMT</pubDate>
  </item>
  <item>
    <title>人工智能大模型发布 动态二</title>
    <link>https://example.invalid/news/2</link>
    <description>第二条摘要。</description>
    <pubDate>Sun, 23 Nov 2026 01:00:00 GMT</pubDate>
  </item>
</channel></rss>""".encode()


async def _fake_fetch(_source: FeedSource) -> bytes:
    return RSS


def test_collect_dedup_persist_and_api(client):
    service = get_industry_pulse_service()
    first = asyncio.run(
        service.collect_once(sources=(SOURCE,), fetch_func=_fake_fetch)
    )
    assert first["status"] == "succeeded"
    assert first["articles_fetched"] == 2
    assert first["articles_inserted"] == 2
    assert first["articles_duplicates"] == 0
    assert first["articles_skipped_limit"] == 0

    second = asyncio.run(
        service.collect_once(sources=(SOURCE,), fetch_func=_fake_fetch)
    )
    assert second["status"] == "succeeded"
    assert second["articles_inserted"] == 0
    assert second["articles_duplicates"] == 2
    assert second["articles_skipped_limit"] == 0
    assert second["stats_legacy"] is False

    payload = client.get("/api/industry-pulse").json()["data"]
    assert payload["total"] == 2
    assert payload["ai_enabled"] is False
    assert payload["llm_mode"] == "mock"
    assert payload["ai_unavailable_reason"]
    assert payload["latest_run"]["articles_inserted"] == 0
    assert payload["sources"][0]["last_status"] == "ok"
    assert payload["items"][0]["analysis_status"] == "pending"
    assert payload["items"][0]["relevance_status"] == "industry_relevant"
    assert payload["items"][0]["taxonomy_version"] == 2
    assert payload["items"][0]["primary_industry"] in payload["items"][0]["industries"]
    assert "utm_source" not in payload["items"][0]["canonical_url"]

    catalog = {item["id"]: item for item in payload["industries"]}
    assert len(catalog) == 16
    assert catalog["digital_tech_comms"]["article_count"] == 2
    assert catalog["digital_tech_comms"]["source_count"] == 1
    assert len(catalog["digital_tech_comms"]["majors"]) >= 5
    assert catalog["sports_industry"]["source_count"] == 0
    assert payload["industry_majors_note"]

    filtered = client.get(
        "/api/industry-pulse?industry=digital_tech_comms&limit=1&offset=1"
    ).json()["data"]
    assert filtered["total"] == 2
    assert len(filtered["items"]) == 1
    finance = client.get("/api/industry-pulse?industry=finance_insurance").json()["data"]
    assert finance["total"] == 0

    article_id = payload["items"][0]["id"]
    blocked = client.post(f"/api/industry-pulse/articles/{article_id}/analyze")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "INDUSTRY_PULSE_AI_DISABLED"


def _cap_source(key: str, industry: str) -> FeedSource:
    return FeedSource(
        key=key,
        name=f"Cap {key}",
        industry=industry,
        feed_url=f"https://example.invalid/{key}.xml",
        homepage_url="https://example.invalid/",
        industries=(industry,),
        region="CN",
        content_policy="metadata_only",
    )


def _cap_rss(prefix: str, count: int = 3, start: int = 1) -> bytes:
    items = "".join(
        f"<item><title>5G通信设备发布 {prefix}-{i}</title>"
        f"<link>https://example.invalid/{prefix}/{i}</link>"
        f"<description>{prefix} summary</description>"
        f"<pubDate>Mon, 24 Nov 2026 01:00:00 GMT</pubDate></item>"
        for i in range(start, start + count)
    )
    return (
        f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'
    ).encode()


def test_collect_global_new_article_cap_is_strict(client):
    source_a = _cap_source("cap-a", "digital_tech_comms")
    source_b = _cap_source("cap-b", "finance_insurance")

    async def fetch(source: FeedSource) -> bytes:
        return _cap_rss("cap-a" if source.key == "cap-a" else "cap-b")

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source_a, source_b), fetch_func=fetch, max_new_articles=3
        )
    )
    assert run["articles_inserted"] == 3
    assert run["articles_inserted"] <= 3
    assert run["articles_fetched"] == 3
    assert run["articles_duplicates"] == 0
    assert run["articles_skipped_limit"] == 0
    assert run["sources_skipped"] == 1
    assert run["stats_legacy"] is False
    skipped = [item for item in run["details"] if item["status"] == "skipped"]
    assert [item["source"] for item in skipped] == ["cap-b"]

    payload = client.get("/api/industry-pulse").json()["data"]
    assert payload["total"] == 3
    assert payload["latest_run"]["articles_skipped_limit"] == 0
    assert payload["latest_run"]["sources_skipped"] == 1
    assert payload["latest_run"]["stats_legacy"] is False
    assert all(item["content_policy"] == "metadata_only" for item in payload["items"])
    assert all(item["summary"] == "" for item in payload["items"])
    assert all(item["analysis_status"] == "disabled" for item in payload["items"])


def test_limit_skips_are_not_reported_as_duplicates(client):
    source = _cap_source("skip-a", "digital_tech_comms")

    async def fetch(_source: FeedSource) -> bytes:
        return _cap_rss("skip-a", count=5)

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source,), fetch_func=fetch, max_new_articles=2
        )
    )
    assert run["articles_fetched"] == 5
    assert run["articles_inserted"] == 2
    assert run["articles_duplicates"] == 0
    assert run["articles_skipped_limit"] == 3
    assert run["sources_skipped"] == 0
    detail = run["details"][0]
    assert detail["processed"] == 2
    assert detail["skipped_limit"] == 3

    payload = client.get("/api/industry-pulse").json()["data"]
    assert payload["latest_run"]["articles_duplicates"] == 0
    assert payload["latest_run"]["articles_skipped_limit"] == 3


def test_existing_duplicates_do_not_consume_cap(client):
    source = _cap_source("dup-a", "digital_tech_comms")

    async def fetch_old(_source: FeedSource) -> bytes:
        return _cap_rss("dup-a", count=2)

    asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source,), fetch_func=fetch_old
        )
    )

    async def fetch_mixed(_source: FeedSource) -> bytes:
        return _cap_rss("dup-a", count=3)

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source,), fetch_func=fetch_mixed, max_new_articles=1
        )
    )
    assert run["articles_inserted"] == 1
    assert run["articles_duplicates"] == 2
    assert run["articles_skipped_limit"] == 0


def test_cap_is_shared_across_sources(client):
    source_a = _cap_source("share-a", "digital_tech_comms")
    source_b = _cap_source("share-b", "finance_insurance")

    async def fetch(source: FeedSource) -> bytes:
        count = 2 if source.key == "share-a" else 3
        return _cap_rss(source.key, count=count)

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source_a, source_b), fetch_func=fetch, max_new_articles=3
        )
    )
    assert run["articles_fetched"] == 5
    assert run["articles_inserted"] == 3
    assert run["articles_duplicates"] == 0
    assert run["articles_skipped_limit"] == 2
    assert run["sources_skipped"] == 0


MIXED_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>5G通信设备发布 相关新闻</title>
    <link>https://example.invalid/mixed/1</link>
    <description>产业相关。</description>
    <pubDate>Mon, 24 Nov 2026 01:00:00 GMT</pubDate></item>
  <item><title>长期左侧卧睡，真的会压迫损伤心脏吗？</title>
    <link>https://example.invalid/mixed/2</link>
    <description>健康科普。</description>
    <pubDate>Mon, 24 Nov 2026 02:00:00 GMT</pubDate></item>
  <item><title>日本今年1至9月出生人口同比减少0.3%</title>
    <link>https://example.invalid/mixed/3</link>
    <description>宏观信号。</description>
    <pubDate>Mon, 24 Nov 2026 03:00:00 GMT</pubDate></item>
  <item><title>广西龙胜县举行盘王节，展瑶家民俗</title>
    <link>https://example.invalid/mixed/4</link>
    <description>普通活动。</description>
    <pubDate>Mon, 24 Nov 2026 04:00:00 GMT</pubDate></item>
</channel></rss>""".encode()


def test_only_industry_relevant_articles_enter_pulse_and_counts(client):
    async def fetch(_source: FeedSource) -> bytes:
        return MIXED_RSS

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(SOURCE,), fetch_func=fetch
        )
    )
    assert run["articles_inserted"] == 4

    payload = client.get("/api/industry-pulse").json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["relevance_status"] == "industry_relevant"
    assert payload["items"][0]["primary_industry"] == "digital_tech_comms"
    catalog = {item["id"]: item for item in payload["industries"]}
    assert catalog["digital_tech_comms"]["article_count"] == 1
    assert sum(item["article_count"] for item in payload["industries"]) == 1
    assert payload["items"][0]["classification_basis"]["rule_version"] == "industry-v2.1"

    import os
    import psycopg

    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT industry, primary_industry, industries::text, "
                "relevance_status, taxonomy_version, "
                "classification_basis->>'rule_version' "
                "FROM industry_pulse_article "
                "WHERE title LIKE '长期左侧卧睡%'"
            )
            row = cur.fetchone()
    assert row == (None, None, "[]", "irrelevant", 2, "industry-v2.1")


def test_legacy_run_is_exposed_without_fake_skip_counts(client):
    import os
    from uuid import uuid4

    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO industry_pulse_run "
                "(id, status, sources_total, sources_ok, articles_fetched, "
                " articles_inserted, articles_duplicates, details, finished_at) "
                "VALUES (%s,'succeeded',1,1,20,5,15,%s,NOW())",
                (
                    uuid4(),
                    Jsonb([
                        {
                            "source": "chinanews-scroll",
                            "entries": 20,
                            "inserted": 5,
                            "duplicates": 15,
                        }
                    ]),
                ),
            )

    run = client.get("/api/industry-pulse").json()["data"]["latest_run"]
    assert run["stats_legacy"] is True
    assert run["articles_skipped_limit"] is None
    assert run["articles_duplicates"] == 15


def test_limit_skips_match_twenty_five_fifteen_scenario(client):
    source = _cap_source("real-shape", "enterprise_professional_services")

    async def fetch(_source: FeedSource) -> bytes:
        return _cap_rss("real-shape", count=20)

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source,), fetch_func=fetch, max_new_articles=5
        )
    )
    assert run["articles_fetched"] == 20
    assert run["articles_inserted"] == 5
    assert run["articles_duplicates"] == 0
    assert run["articles_skipped_limit"] == 15
    assert run["sources_skipped"] == 0

    payload = client.get("/api/industry-pulse").json()["data"]["latest_run"]
    assert payload["articles_inserted"] == 5
    assert payload["articles_duplicates"] == 0
    assert payload["articles_skipped_limit"] == 15
    assert payload["stats_legacy"] is False

def test_industry_counts_include_secondary_labels(client):
    source = FeedSource(
        key="multi-count",
        name="Multi Count",
        industry="digital_tech_comms",
        industries=("digital_tech_comms",),
        region="CN",
        content_policy="metadata_only",
        feed_url="https://example.invalid/multi.xml",
        homepage_url="https://example.invalid/",
    )

    async def fetch(_source: FeedSource) -> bytes:
        return (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            '<item><title>华为发布新款手机，电商渠道首发</title>'
            '<link>https://example.invalid/multi/1</link>'
            '<description>multi</description>'
            '<pubDate>Mon, 24 Nov 2026 01:00:00 GMT</pubDate></item>'
            '</channel></rss>'
        ).encode()

    run = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=(source,), fetch_func=fetch
        )
    )
    assert run["articles_inserted"] == 1

    payload = client.get("/api/industry-pulse").json()["data"]
    assert payload["total"] == 1
    catalog = {item["id"]: item for item in payload["industries"]}
    assert catalog["digital_tech_comms"]["article_count"] == 1
    assert catalog["consumer_retail_services"]["article_count"] == 1

    filtered = client.get(
        "/api/industry-pulse?industry=consumer_retail_services"
    ).json()["data"]
    assert filtered["total"] == 1

def test_refresh_is_disabled_in_production_even_with_user_header(
    client, monkeypatch
):
    from app.api.routes import industry_pulse as route

    called: list[bool] = []

    class FakeService:
        def collect_once(self):
            called.append(True)
            return {}

    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            industry_pulse_refresh_cooldown=60,
            industry_pulse_collect_timeout=30,
        ),
    )
    monkeypatch.setattr(route, "_service", lambda: FakeService())

    response = client.post(
        "/api/industry-pulse/refresh",
        headers={"X-User-Id": "demo-user"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INDUSTRY_PULSE_REFRESH_DISABLED"
    assert called == []


def test_refresh_remains_available_in_test_env_with_mocked_collection(
    client, monkeypatch
):
    from app.api.routes import industry_pulse as route

    route.reset_refresh_guard()
    run = {
        "id": "00000000-0000-4000-8000-000000000001",
        "status": "succeeded",
        "started_at": "2026-11-26T00:00:00Z",
        "finished_at": "2026-11-26T00:00:01Z",
        "sources_total": 0,
        "sources_ok": 0,
        "sources_failed": 0,
        "articles_fetched": 0,
        "articles_inserted": 0,
        "articles_duplicates": 0,
        "articles_skipped_limit": 0,
        "sources_skipped": 0,
        "stats_legacy": False,
        "error_message": "",
        "details": [],
    }

    class FakeService:
        async def collect_once(self):
            return run

    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="test",
            industry_pulse_refresh_cooldown=0,
            industry_pulse_collect_timeout=30,
        ),
    )
    monkeypatch.setattr(route, "_service", lambda: FakeService())

    try:
        response = client.post("/api/industry-pulse/refresh")
        assert response.status_code == 200
        assert response.json()["data"]["run"]["id"] == run["id"]
    finally:
        route.reset_refresh_guard()
