"""Read-only V2.1 reclassification preview for existing articles.

Compares the legacy V2 classifier with V2.1 on the dev database. The
connection is opened read-only and only SELECT statements are issued.
Title-only limitation is explicit: summaries are empty for metadata_only
articles, so no claim is made about article bodies.
"""

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from dotenv import dotenv_values

from app.industry_pulse.classify import classify_article
from app.industry_pulse.classify_legacy import classify_article_v2
from app.industry_pulse.sources import FeedSource
from app.industry_pulse.taxonomy import INDUSTRY_LABELS, INDUSTRY_ORDER


def _database_url() -> str:
    url = os.getenv("DATABASE_URL") or dotenv_values(
        Path(__file__).resolve().parents[3] / ".env"
    ).get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    return url


def _source(row: dict[str, Any]) -> FeedSource:
    return FeedSource(
        key=row.get("source_key") or "unknown",
        name=row.get("source_name") or "unknown",
        industry=row.get("source_industry") or "enterprise_professional_services",
        industries=tuple(row.get("source_industries") or ()),
        region=row.get("region") or "CN",
        content_policy=row.get("content_policy") or "metadata_only",
        feed_url="",
        homepage_url="",
    )


def _detail(row: dict[str, Any], v2: Any, v21: Any) -> dict[str, Any]:
    v2_primary = v2.primary_industry
    v21_primary = v21.primary_industry
    v2_inds = list(v2.industries)
    v21_inds = list(v21.industries)
    changed = (
        v2.relevance != v21.relevance
        or v2_primary != v21_primary
        or v2_inds != v21_inds
    )
    if v2.relevance != "industry_relevant" and v21.relevance == "industry_relevant":
        change = "newly_recalled"
    elif v2.relevance == "industry_relevant" and v21.relevance != "industry_relevant":
        change = "newly_filtered"
    elif changed:
        change = "reclassified"
    else:
        change = "unchanged"
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "source_name": row.get("source_name") or "未知来源",
        "published_at": str(row["published_at"]) if row.get("published_at") else None,
        "old_industry": row["industry"],
        "v2": {
            "relevance": v2.relevance,
            "primary": v2_primary,
            "industries": v2_inds,
        },
        "v21": {
            "relevance": v21.relevance,
            "primary": v21_primary,
            "industries": v21_inds,
            "confidence": v21.confidence,
        },
        "change": change,
        "basis": {
            "title_terms": v21.basis.get("title_terms", {}),
            "entity_hits": v21.basis.get("entity_hits", {}),
            "signals": v21.basis.get("signals", []),
            "strong_signals": v21.basis.get("strong_signals", []),
            "macro_terms": v21.basis.get("macro_terms", []),
            "event_terms": v21.basis.get("event_terms", []),
            "boundary_rules": v21.basis.get("boundary_rules", []),
            "review_flags": v21.basis.get("review_flags", {}),
            "non_industry": v21.basis.get("non_industry", {}),
            "source_hint": v21.basis.get("source_hint", []),
            "scores": v21.basis.get("scores", {}),
        },
    }


def build_preview() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with psycopg.connect(
        _database_url(), options="-c default_transaction_read_only=on"
    ) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT a.id, a.title, a.summary, a.industry,
                       a.primary_industry, a.industries, a.region, a.published_at,
                       s.key AS source_key, s.name AS source_name,
                       s.industry AS source_industry,
                       s.industries AS source_industries,
                       s.content_policy
                FROM industry_pulse_article a
                LEFT JOIN industry_feed_source s ON s.id = a.source_id
                ORDER BY a.published_at NULLS LAST, a.id
                """
            )
            rows = list(cur.fetchall())

    details: list[dict[str, Any]] = []
    for row in rows:
        source = _source(row)
        details.append(
            _detail(
                row,
                classify_article_v2(source, row["title"], row["summary"] or ""),
                classify_article(source, row["title"], row["summary"] or ""),
            )
        )

    v2_rel = Counter(item["v2"]["relevance"] for item in details)
    v21_rel = Counter(item["v21"]["relevance"] for item in details)
    transitions = Counter(
        f"{item['v2']['relevance']}->{item['v21']['relevance']}" for item in details
    )

    v21_industry_counts: Counter[str] = Counter()
    v21_primary_counts: Counter[str] = Counter()
    multi_count = 0
    single_count = 0
    classified_count = 0
    for item in details:
        if item["v21"]["relevance"] != "industry_relevant":
            continue
        classified_count += 1
        inds = item["v21"]["industries"]
        if len(inds) > 1:
            multi_count += 1
        else:
            single_count += 1
        v21_primary_counts[item["v21"]["primary"] or "unclassified"] += 1
        for industry in inds:
            v21_industry_counts[industry] += 1

    changes = [item for item in details if item["change"] != "unchanged"]
    newly_recalled = [item for item in details if item["change"] == "newly_recalled"]
    newly_filtered = [item for item in details if item["change"] == "newly_filtered"]
    still_review = [
        item for item in details if item["v21"]["relevance"] == "needs_review"
    ]
    low_confidence = [
        item for item in details
        if item["v21"]["relevance"] == "industry_relevant"
        and item["v21"]["confidence"] == "low"
    ]
    return {
        "total": len(details),
        "title_only": True,
        "summary_note": "历史文章均为 metadata_only；摘要/正文为空，判断仅依据标题与来源元数据。",
        "v2_relevance_counts": dict(v2_rel),
        "v21_relevance_counts": dict(v21_rel),
        "transition_counts": dict(transitions),
        "v21_classified_articles": classified_count,
        "v21_single_industry_articles": single_count,
        "v21_multi_industry_articles": multi_count,
        "v21_industry_label_total": sum(v21_industry_counts.values()),
        "v21_primary_counts": dict(v21_primary_counts),
        "v21_industry_counts": dict(v21_industry_counts),
        "v21_industry_labels": {k: INDUSTRY_LABELS[k] for k in INDUSTRY_ORDER},
        "changed_count": len(changes),
        "newly_recalled_count": len(newly_recalled),
        "newly_filtered_count": len(newly_filtered),
        "still_needs_review_count": len(still_review),
        "low_confidence_count": len(low_confidence),
        "source_hint_used_count": sum(
            1 for item in details if item["basis"]["source_hint"]
            and item["v21"]["relevance"] == "industry_relevant"
        ),
        "changes": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only V2 -> V2.1 reclassification preview"
    )
    parser.add_argument(
        "--details",
        type=int,
        default=20,
        help="Number of changed-article detail rows to print (0 for summary only)",
    )
    args = parser.parse_args()
    preview = build_preview()
    changes = preview.pop("changes")
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if args.details:
        print(json.dumps(changes[: args.details], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()