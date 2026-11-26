"""Seed isolated E2E industry-pulse articles; guarded to careerpilot_test."""

import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

TEST_DB = "careerpilot_test"

SOURCES = [
    ("e2e-techcrunch", "TechCrunch", "digital_tech_comms", "https://techcrunch.com/"),
    ("e2e-federal-reserve", "Federal Reserve", "finance_insurance", "https://www.federalreserve.gov/"),
    ("e2e-openai", "OpenAI", "digital_tech_comms", "https://openai.com/news/"),
    ("e2e-us-doe", "U.S. Department of Energy", "energy_environment", "https://www.energy.gov/news"),
]

ARTICLES = [
    ("digital_tech_comms", "e2e-techcrunch", "5G通信设备发布与数据中心建设", "通信基础设施与平台协作测试摘要。", "2026-11-24T01:00:00+00:00"),
    ("finance_insurance", "e2e-openai", "银行保险业发布新监管政策", "风险数据报送与合规流程测试摘要。", "2026-11-24T02:00:00+00:00"),
    ("manufacturing_industry", "e2e-techcrunch", "智能制造工厂生产线投产", "智能制造与产业链协作测试摘要。", "2026-11-24T03:00:00+00:00"),
    ("energy_environment", "e2e-federal-reserve", "光伏储能与电网项目投产", "储能设备与运行数据测试摘要。", "2026-11-24T04:00:00+00:00"),
    ("auto_smart_mobility", "e2e-techcrunch", "新能源汽车与智能驾驶技术发布", "智能驾驶与车载系统测试摘要。", "2026-11-24T05:00:00+00:00"),
    ("transport_logistics", "e2e-us-doe", "物流供应链与港口航运合作", "供应链可视化与运输测试摘要。", "2026-11-24T06:00:00+00:00"),
    ("health_life_sciences", "e2e-techcrunch", "医院临床药物与疫苗研发", "医疗数据与诊断流程测试摘要。", "2026-11-24T07:00:00+00:00"),
    ("education_research", "e2e-openai", "高校科研与职业教育课程发布", "科研协作与教育工具测试摘要。", "2026-11-24T08:00:00+00:00"),
    ("agriculture_food", "e2e-federal-reserve", "农业粮食与食品加工项目投产", "农业数据与食品安全测试摘要。", "2026-11-24T09:00:00+00:00"),
    ("consumer_retail_services", "e2e-us-doe", "零售电商与消费品牌合作", "零售体验与消费趋势测试摘要。", "2026-11-24T10:00:00+00:00"),
    ("real_estate_construction", "e2e-techcrunch", "房地产建筑工程项目建设", "建筑能效与城市更新测试摘要。", "2026-11-24T11:00:00+00:00"),
    ("culture_media_content", "e2e-us-doe", "影视传媒与游戏内容发布", "内容平台与文旅体验测试摘要。", "2026-11-24T12:00:00+00:00"),
    ("arts_design", "e2e-techcrunch", "艺术设计展览与产品设计发布", "设计流程与商业应用测试摘要。", "2026-11-24T13:00:00+00:00"),
    ("sports_industry", "e2e-openai", "体育赛事与健身产业合作", "运动监测与赛事运营测试摘要。", "2026-11-24T14:00:00+00:00"),
    ("tourism_hospitality_events", "e2e-federal-reserve", "旅游酒店景区项目合作", "冰雪温泉与度假体验测试摘要。", "2026-11-24T15:00:00+00:00"),
    ("enterprise_professional_services", "e2e-openai", "管理咨询与会计审计服务合作", "企业服务与专业协作测试摘要。", "2026-11-24T16:00:00+00:00"),
]

NON_RELEVANT = [
    ("日本今年1至9月出生人口同比减少0.3%", "宏观人口信号。", "2026-11-24T17:00:00+00:00", "macro_signal"),
    ("广西龙胜县举行盘王节，展瑶家民俗", "普通民俗活动。", "2026-11-24T18:00:00+00:00", "needs_review"),
]


def main() -> None:
    if os.environ.get("APP_ENV") != "test":
        raise SystemExit("refusing E2E seed: APP_ENV is not test")
    if os.environ.get("E2E_DB_GUARD") != TEST_DB:
        raise SystemExit("refusing E2E seed: E2E_DB_GUARD mismatch")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("refusing E2E seed: DATABASE_URL missing")

    with psycopg.connect(url) as conn:
        if conn.info.dbname != TEST_DB:
            raise SystemExit(f"refusing E2E seed: db is {conn.info.dbname}")
        with conn.cursor() as cur:
            source_ids: dict[str, object] = {}
            for key, name, industry, homepage in SOURCES:
                region = 'INTL' if key == 'e2e-openai' else 'CN'
                cur.execute(
                    """
                    INSERT INTO industry_feed_source
                        (id, key, name, industry, industries, region, content_policy,
                         feed_url, homepage_url, license_note, enabled, last_status,
                         taxonomy_version)
                    VALUES (%s,%s,%s,%s,%s,%s,'metadata_only',
                            %s,%s,%s,true,'ok',2)
                    ON CONFLICT (key) DO UPDATE SET
                        name=EXCLUDED.name, industry=EXCLUDED.industry,
                        homepage_url=EXCLUDED.homepage_url,
                        enabled=true, last_status='ok', last_error='',
                        taxonomy_version=2, updated_at=NOW()
                    RETURNING id
                    """,
                    (
                        uuid4(), key, name, industry,
                        Jsonb([industry]), region,
                        f"https://example.invalid/{key}.xml", homepage,
                        "E2E 测试源，仅用于隔离测试库。",
                    ),
                )
                source_ids[key] = cur.fetchone()[0]

            rows = [
                (industry, source_key, title, summary, published, "industry_relevant")
                for industry, source_key, title, summary, published in ARTICLES
            ] + [
                (None, "e2e-techcrunch", title, summary, published, relevance)
                for title, summary, published, relevance in NON_RELEVANT
            ]

            for index, (industry, source_key, title, summary, published, relevance) in enumerate(rows):
                source_name = next(name for key, name, _, _ in SOURCES if key == source_key)
                region = 'INTL' if source_key == 'e2e-openai' else 'CN'
                cur.execute(
                    """
                    INSERT INTO industry_pulse_article
                        (id, source_id, source_name, source_url, industry,
                         primary_industry, industries, region, content_policy,
                         title, url, canonical_url, summary, published_at,
                         content_hash, analysis_status, tags, analysis_details,
                         relevance_status, classification_basis, taxonomy_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'metadata_only',
                            %s,%s,%s,%s,%s,%s,'pending',%s,%s,%s,%s,2)
                    ON CONFLICT (canonical_url) DO NOTHING
                    """,
                    (
                        uuid4(),
                        source_ids[source_key],
                        source_name,
                        next(h for k, _, _, h in SOURCES if k == source_key),
                        industry, industry,
                        Jsonb([industry] if industry else []),
                        region,
                        title,
                        f"https://example.invalid/industry/{index}",
                        f"https://example.invalid/industry/{index}",
                        summary,
                        datetime.fromisoformat(published),
                        f"e2e-{index}",
                        Jsonb([]),
                        Jsonb({}),
                        relevance,
                        Jsonb({"rule_version": "e2e-seed"}),
                    ),
                )
            cur.execute("SELECT count(*) FROM industry_pulse_article")
            total = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO industry_pulse_run
                    (id, status, started_at, finished_at, sources_total, sources_ok,
                     sources_failed, articles_fetched, articles_inserted,
                     articles_duplicates, error_message, details)
                VALUES (%s,'succeeded',NOW(),NOW(),%s,%s,0,%s,%s,0,'',%s)
                """,
                (uuid4(), len(SOURCES), len(SOURCES), total, total, Jsonb([])),
            )
            conn.commit()
            print(f"seeded industry pulse articles={total}")


if __name__ == "__main__":
    main()