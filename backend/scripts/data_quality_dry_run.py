"""Read-only dry-run for InfoQ timezone repair and V2.1 label cleanup.

This script never writes to PostgreSQL. It opens a READ ONLY transaction,
prints the affected records and proposed values, and exits. Applying any
change requires a separate, explicitly authorized data-migration task.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

from app.industry_pulse.classify import classify_article
from app.industry_pulse.sources import FeedSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INFOQ_SOURCE = "InfoQ 中文"
INFOQ_OFFSET = timedelta(hours=8)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _database_url() -> str:
    value = os.getenv("DATABASE_URL") or dotenv_values(
        PROJECT_ROOT / ".env"
    ).get("DATABASE_URL")
    if not value:
        raise SystemExit("DATABASE_URL missing")
    return value


def _time_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if row["source_name"] != INFOQ_SOURCE:
            continue
        published = row["published_at"]
        fetched = row["fetched_at"]
        if not isinstance(published, datetime):
            continue
        proposed = published.astimezone(UTC) - INFOQ_OFFSET
        confidence = (
            "high"
            if isinstance(fetched, datetime)
            and published > fetched + timedelta(minutes=30)
            else "medium"
        )
        result.append(
            {
                "id": row["id"],
                "source": row["source_name"],
                "title": row["title"],
                "old_published_at": _iso(published),
                "proposed_published_at": _iso(proposed),
                "confidence": confidence,
                "reason": (
                    "InfoQ 中文 RSS pubDate 无时区，按北京时间解释后应转为 UTC；"
                    "旧解析器把无时区值直接当 UTC 存储。"
                ),
                "impact": (
                    "新闻时间线整体前移 8 小时；可能改变 30 天新闻跨度门槛、"
                    "月度分布和 Pulse 展示时间；不改原文、标签或采集状态。"
                ),
                "rollback": (
                    "UPDATE industry_pulse_article "
                    "SET published_at = published_at + interval '8 hours' "
                    f"WHERE id = '{row['id']}';"
                ),
            }
        )
    return result


def _other_time_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if row["source_name"] == INFOQ_SOURCE:
            continue
        published = row["published_at"]
        fetched = row["fetched_at"]
        if not isinstance(published, datetime) or not isinstance(
            fetched, datetime
        ):
            continue
        if published <= fetched + timedelta(hours=2):
            continue
        result.append(
            {
                "id": row["id"],
                "source": row["source_name"],
                "title": row["title"],
                "published_at": _iso(published),
                "fetched_at": _iso(fetched),
                "status": "needs_source_check",
                "reason": (
                    "发布时间晚于采集时间超过 2 小时；可能是未来排期文章，"
                    "也可能存在来源时区缺失。未自动提出偏移。"
                ),
            }
        )
    return result


def _source_from_row(row: dict[str, Any]) -> FeedSource:
    return FeedSource(
        key=str(row.get("source_key") or row["source_name"]),
        name=str(row["source_name"]),
        industry=str(row.get("source_industry") or "enterprise_professional_services"),
        feed_url=str(row.get("source_feed_url") or "https://example.invalid/feed"),
        homepage_url=str(
            row.get("source_homepage_url") or "https://example.invalid/"
        ),
        industries=tuple(row.get("source_industries") or ()),
        region=str(row.get("source_region") or "CN"),
        content_policy=str(row.get("source_content_policy") or "metadata_only"),
    )


def _classification_candidates(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if row["relevance_status"] != "industry_relevant":
            continue
        old_industries = list(row.get("industries") or [])
        primary = row.get("primary_industry")
        source = _source_from_row(row)
        # metadata_only sources deliberately do not store summaries. The
        # preview is therefore title-only unless the policy allows excerpts.
        title_only = (
            source.content_policy != "feed_excerpt" or not row.get("summary")
        )
        summary = (
            str(row.get("summary") or "")
            if source.content_policy == "feed_excerpt"
            else ""
        )
        preview = classify_article(source, str(row["title"]), summary)
        new_industries = list(preview.industries)
        new_primary = preview.primary_industry
        if (
            preview.relevance == row["relevance_status"]
            and new_industries == old_industries
            and new_primary == primary
        ):
            continue
        result.append(
            {
                "id": row["id"],
                "source": row["source_name"],
                "title": row["title"],
                "input": "title_only" if title_only else "title_and_summary",
                "old_relevance_status": row["relevance_status"],
                "proposed_relevance_status": preview.relevance,
                "old_primary_industry": primary,
                "proposed_primary_industry": new_primary,
                "old_industries": old_industries,
                "proposed_industries": new_industries,
                "old_confidence": (row.get("classification_basis") or {}).get(
                    "confidence"
                ),
                "proposed_confidence": preview.confidence,
                "reasons": [
                    "按当前 V2.1 规则重新分类；低置信度、边界规则、实体范围与"
                    "标题级证据均按新逻辑计算。"
                ],
                "impact": (
                    "该文章将从行业动态/行业趋势的强制行业标签中移除；"
                    "原文不删除；如果全部标签移除则进入 needs_review。"
                ),
                "rollback": (
                    "保留原 relevance_status / primary_industry / industries / "
                    "classification_basis 快照后，按原值恢复。"
                ),
            }
        )
    return result


def main() -> None:
    url = _database_url()
    with psycopg.connect(url, row_factory=dict_row) as conn:
        # Read-only transaction: no INSERT/UPDATE/DELETE can be applied.
        conn.execute("BEGIN READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id::text, a.source_name, a.published_at, a.fetched_at,
                       a.title, a.summary, a.content_policy,
                       a.industries, a.primary_industry,
                       a.relevance_status, a.classification_basis,
                       s.key AS source_key, s.industry AS source_industry,
                       s.feed_url AS source_feed_url,
                       s.homepage_url AS source_homepage_url,
                       s.industries AS source_industries,
                       s.region AS source_region,
                       s.content_policy AS source_content_policy
                FROM industry_pulse_article a
                JOIN industry_feed_source s ON s.id = a.source_id
                WHERE a.taxonomy_version = 2
                  AND (a.source_name = %s OR a.relevance_status = 'industry_relevant')
                ORDER BY a.source_name, a.published_at DESC
                """,
                (INFOQ_SOURCE,),
            )
            rows = list(cur.fetchall())
            cur.execute(
                """
                SELECT id::text, source_name, published_at, fetched_at, title
                FROM industry_pulse_article
                WHERE published_at > fetched_at + interval '2 hours'
                ORDER BY published_at DESC
                """
            )
            time_anomaly_rows = list(cur.fetchall())
        conn.rollback()

    time_candidates = _time_candidates(rows)
    other_anomalies = _other_time_anomalies(time_anomaly_rows)
    classification_candidates = _classification_candidates(rows)
    report = {
        "read_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "infoq_time_candidates": len(time_candidates),
            "infoq_high_confidence": sum(
                1 for item in time_candidates if item["confidence"] == "high"
            ),
            "other_time_anomalies": len(other_anomalies),
            "classification_candidates": len(classification_candidates),
            "classification_to_review": sum(
                1
                for item in classification_candidates
                if item["proposed_relevance_status"] == "needs_review"
            ),
        },
        "time_candidates": time_candidates,
        "other_time_anomalies": other_anomalies,
        "classification_candidates": classification_candidates,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
