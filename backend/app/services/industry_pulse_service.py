import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.llm import LLMClient
from app.db.industry_pulse_repositories import industry_pulse_repository
from app.industry_pulse.classify import classify_article
from app.industry_pulse.parser import FeedParseError, parse_feed
from app.industry_pulse.personalize import rank_personal_items
from app.industry_pulse.sources import FEED_SOURCES, FeedSource
from app.industry_pulse.taxonomy import INDUSTRIES, INDUSTRY_LABELS, MAJORS_NOTE
from app.schemas.industry_pulse import IndustryPulseAnalysisOut

logger = logging.getLogger(__name__)
FetchFunc = Callable[[FeedSource], Awaitable[bytes]]


def _article_out(row: dict[str, Any]) -> dict[str, Any]:
    industries = list(row.get("industries") or [])
    policy = row.get("content_policy", "metadata_only")
    hidden = policy != "feed_excerpt"
    return {
        **row,
        "industries": industries,
        "industry_labels": [INDUSTRY_LABELS.get(item, item) for item in industries],
        "primary_industry": row.get("primary_industry"),
        "region": row.get("region", "INTL"),
        "content_policy": policy,
        "relevance_status": row.get("relevance_status", "needs_review"),
        "classification_basis": row.get("classification_basis") or {},
        "legacy_industry": row.get("legacy_industry"),
        "taxonomy_version": row.get("taxonomy_version", 1),
        "summary": "" if hidden else row.get("summary", ""),
        "ai_summary": "" if hidden else row.get("ai_summary", ""),
        "career_impact": "" if hidden else row.get("career_impact", ""),
        "analysis_status": "disabled" if hidden else row.get("analysis_status", "pending"),
        "tags": list(row.get("tags") or []),
        "analysis_details": row.get("analysis_details") or {},
    }


def _source_out(row: dict[str, Any]) -> dict[str, Any]:
    industries = list(row.get("industries") or [])
    return {
        **row,
        "industries": industries,
        "industry_labels": [INDUSTRY_LABELS.get(item, item) for item in industries],
        "primary_industry_label": INDUSTRY_LABELS.get(row["industry"], row["industry"]),
    }


def _run_out(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if run is None:
        return None
    details = list(run.get("details") or [])
    legacy = bool(details) and all("skipped_limit" not in item for item in details)
    skipped_limit = (
        None
        if legacy
        else sum(int(item.get("skipped_limit") or 0) for item in details)
    )
    sources_skipped = max(
        sum(1 for item in details if item.get("status") == "skipped"),
        max(
            0,
            int(run.get("sources_total") or 0)
            - int(run.get("sources_ok") or 0)
            - int(run.get("sources_failed") or 0),
        ),
    )
    return {
        **run,
        "details": details,
        "articles_skipped_limit": skipped_limit,
        "sources_skipped": sources_skipped,
        "stats_legacy": legacy,
    }


def _skipped_detail(source: FeedSource) -> dict[str, Any]:
    return {
        "source": source.key, "name": source.name,
        "industry": source.industry, "region": source.region,
        "status": "skipped", "entries": 0, "processed": 0,
        "inserted": 0, "duplicates": 0, "skipped_limit": 0,
        "error": "",
    }


class IndustryPulseService:
    async def _fetch_feed(self, client: httpx.AsyncClient, source: FeedSource) -> bytes:
        settings = get_settings()
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await client.get(source.feed_url)
                response.raise_for_status()
                if len(response.content) > settings.industry_pulse_max_feed_bytes:
                    raise ValueError("Feed 响应体超过上限")
                return response.content
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.5)
        raise last_error or RuntimeError("Feed 请求失败")

    async def collect_once(
        self,
        *,
        sources: tuple[FeedSource, ...] | None = None,
        fetch_func: FetchFunc | None = None,
        max_new_articles: int | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        all_sources = sources or FEED_SOURCES
        source_ids: dict[str, UUID] = {}
        for source in all_sources:
            source_ids[source.key] = await asyncio.to_thread(
                industry_pulse_repository.sync_source, source
            )
        active = tuple(source for source in all_sources if source.enabled)
        run_id = await asyncio.to_thread(
            industry_pulse_repository.start_run, len(active)
        )
        details: dict[str, dict[str, Any]] = {}
        sources_ok = sources_failed = 0
        articles_fetched = articles_inserted = articles_duplicates = 0
        articles_skipped_limit = 0
        lock = asyncio.Semaphore(4)

        async def process(source: FeedSource, client: httpx.AsyncClient) -> None:
            nonlocal sources_ok, sources_failed, articles_fetched
            nonlocal articles_inserted, articles_duplicates, articles_skipped_limit
            async with lock:
                try:
                    data = (
                        await fetch_func(source)
                        if fetch_func is not None
                        else await self._fetch_feed(client, source)
                    )
                    entries = await asyncio.to_thread(
                        parse_feed,
                        data,
                        source,
                        min(settings.industry_pulse_max_items_per_feed, source.max_items),
                    )
                    processed = 0
                    inserted = 0
                    for entry in entries:
                        if (
                            max_new_articles is not None
                            and articles_inserted + inserted >= max_new_articles
                        ):
                            break
                        classification = classify_article(
                            source, entry.title, entry.summary
                        )
                        summary = entry.summary if source.content_policy == "feed_excerpt" else ""
                        was_inserted = await asyncio.to_thread(
                            industry_pulse_repository.insert_article,
                            source=source,
                            source_id=source_ids[source.key],
                            title=entry.title,
                            url=entry.url,
                            canonical_url=entry.canonical_url,
                            summary=summary,
                            published_at=entry.published_at,
                            content_hash=entry.content_hash,
                            primary_industry=classification.primary_industry,
                            industries=list(classification.industries),
                            relevance_status=classification.relevance,
                            classification_basis=classification.basis,
                            tags=list(classification.tags),
                        )
                        processed += 1
                        inserted += 1 if was_inserted else 0
                    duplicates = processed - inserted
                    skipped_limit = len(entries) - processed
                    articles_fetched += len(entries)
                    articles_inserted += inserted
                    articles_duplicates += duplicates
                    articles_skipped_limit += skipped_limit
                    sources_ok += 1
                    await asyncio.to_thread(
                        industry_pulse_repository.update_source_status,
                        source_ids[source.key],
                        status="ok",
                        error="",
                    )
                    details[source.key] = {
                        "source": source.key, "name": source.name,
                        "industry": source.industry, "region": source.region,
                        "status": "ok", "entries": len(entries),
                        "processed": processed, "inserted": inserted,
                        "duplicates": duplicates, "skipped_limit": skipped_limit,
                        "error": "",
                    }
                except (httpx.HTTPError, FeedParseError, ValueError) as exc:
                    sources_failed += 1
                    message = str(exc)[:500]
                    await asyncio.to_thread(
                        industry_pulse_repository.update_source_status,
                        source_ids[source.key], status="failed", error=message,
                    )
                    details[source.key] = {
                        "source": source.key, "name": source.name,
                        "industry": source.industry, "region": source.region,
                        "status": "failed", "entries": 0, "processed": 0,
                        "inserted": 0, "duplicates": 0, "skipped_limit": 0,
                        "error": message,
                    }
                    logger.warning("industry_pulse_feed_failed source=%s error=%s", source.key, message)
                except Exception as exc:
                    sources_failed += 1
                    message = str(exc)[:500]
                    await asyncio.to_thread(
                        industry_pulse_repository.update_source_status,
                        source_ids[source.key], status="failed", error=message,
                    )
                    details[source.key] = {
                        "source": source.key, "name": source.name,
                        "industry": source.industry, "region": source.region,
                        "status": "failed", "entries": 0, "processed": 0,
                        "inserted": 0, "duplicates": 0, "skipped_limit": 0,
                        "error": message,
                    }
                    logger.exception("industry_pulse_feed_unexpected_error source=%s", source.key)

        timeout = httpx.Timeout(
            settings.industry_pulse_fetch_timeout,
            connect=min(5.0, settings.industry_pulse_fetch_timeout),
        )
        headers = {
            "User-Agent": settings.industry_pulse_user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=headers
        ) as client:
            if max_new_articles is None:
                await asyncio.gather(*(process(source, client) for source in active))
            else:
                for index, source in enumerate(active):
                    if articles_inserted >= max_new_articles:
                        for pending in active[index:]:
                            if pending.key not in details:
                                details[pending.key] = _skipped_detail(pending)
                        break
                    await process(source, client)

        details_list = [
            details[source.key] for source in active if source.key in details
        ]
        if sources_ok and sources_failed:
            status, error_message = "partial", f"{sources_failed} 个来源失败"
        elif sources_ok:
            status, error_message = "succeeded", ""
        else:
            status, error_message = "failed", "所有来源采集失败"
        await asyncio.to_thread(
            industry_pulse_repository.finish_run,
            run_id,
            status=status,
            sources_ok=sources_ok,
            sources_failed=sources_failed,
            articles_fetched=articles_fetched,
            articles_inserted=articles_inserted,
            articles_duplicates=articles_duplicates,
            error_message=error_message,
            details=details_list,
        )
        return _run_out(await asyncio.to_thread(industry_pulse_repository.latest_run)) or {
            "id": run_id, "status": status, "details": details_list,
            "sources_total": len(active), "sources_ok": sources_ok,
            "sources_failed": sources_failed, "articles_fetched": articles_fetched,
            "articles_inserted": articles_inserted,
            "articles_duplicates": articles_duplicates,
            "articles_skipped_limit": articles_skipped_limit,
            "sources_skipped": len(active) - sources_ok - sources_failed,
            "stats_legacy": False,
            "error_message": error_message,
        }

    def list_articles(
        self, *, industry: str | None, region: str | None, limit: int, offset: int
    ) -> dict[str, Any]:
        rows, total = industry_pulse_repository.list_articles(
            industry=industry, region=region, limit=limit, offset=offset
        )
        settings = get_settings()
        configured = {source.key: source for source in FEED_SOURCES}
        sources = industry_pulse_repository.sources()
        for source in sources:
            hint = configured.get(source.get("key", ""))
            if hint is not None:
                source["industries"] = list(hint.industries)
        if not sources:
            sources = [{
                "key": source.key, "name": source.name, "industry": source.industry,
                "industries": list(source.industries),
                "region": source.region, "content_policy": source.content_policy,
                "feed_url": source.feed_url, "homepage_url": source.homepage_url,
                "license_note": source.license_note, "enabled": source.enabled,
                "blocked_reason": source.blocked_reason,
                "last_status": "blocked" if not source.enabled else "never",
                "last_error": source.blocked_reason, "last_fetched_at": None,
                "legacy_industry": None, "taxonomy_version": 2,
            } for source in FEED_SOURCES]
        if not settings.industry_pulse_ai_enabled:
            reason = "AI 分析默认关闭；需在环境中显式启用并使用真实模型"
        elif settings.llm_mode != "real":
            reason = "AI 已启用，但当前 LLM_MODE=mock，不会产生真实分析"
        else:
            reason = ""
        counts = industry_pulse_repository.article_counts_by_industry()
        coverage = []
        for item in INDUSTRIES:
            source_count = sum(
                1 for source in sources
                if source.get("enabled")
                and item.id in (source.get("industries") or [])
            )
            coverage.append({
                "id": item.id, "label": item.name,
                "scope": item.scope, "majors": list(item.majors),
                "source_count": source_count,
                "article_count": counts.get(item.id, 0),
            })
        return {
            "items": [_article_out(row) for row in rows],
            "total": total, "limit": limit, "offset": offset,
            "industry": industry or "all", "region": region or "all",
            "industries": coverage,
            "industry_majors_note": MAJORS_NOTE,
            "sources": [_source_out(source) for source in sources],
            "latest_run": _run_out(industry_pulse_repository.latest_run()),
            "ai_enabled": settings.industry_pulse_ai_enabled,
            "llm_mode": settings.llm_mode,
            "ai_unavailable_reason": reason,
        }

    def personal_articles(
        self,
        *,
        profile_data: dict[str, Any] | None,
        industry: str | None,
        region: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        payload = self.list_articles(
            industry=industry, region=region, limit=500, offset=0
        )
        page, total, context, reason = rank_personal_items(
            payload["items"],
            profile_data,
            limit=limit,
            offset=offset,
        )
        return {
            **payload,
            "items": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "view": "personal",
            "profile_sufficient": context["sufficient"],
            "profile_missing": context["missing"],
            "personalization_reason": reason,
            "personal_target_role": context["target_role"],
            "personal_target_industry": context["target_industry_label"],
            "personal_target_location": context["target_location"],
        }

    def analyze_article(self, article_id: UUID) -> dict[str, Any]:
        settings = get_settings()
        if not settings.industry_pulse_ai_enabled:
            raise AppError("INDUSTRY_PULSE_AI_DISABLED", "Industry Pulse AI 分析默认关闭", status_code=409)
        if settings.llm_mode != "real":
            raise AppError("INDUSTRY_PULSE_REAL_LLM_REQUIRED", "需要 LLM_MODE=real 才能执行真实 AI 分析", status_code=409)
        article = industry_pulse_repository.get_article(article_id)
        if article is None:
            raise NotFoundError("行业动态不存在")
        if article.get("content_policy") != "feed_excerpt":
            raise AppError(
                "INDUSTRY_PULSE_CONTENT_POLICY_BLOCKED",
                "该来源仅允许元数据使用，不能进行 AI 改写",
                status_code=403,
            )
        prompt = (
            "请基于以下公开 RSS 元数据做结构化分析。只能使用给定标题、来源和摘要；"
            "不得补写新闻中没有的事实，推断必须谨慎。\n"
            f"标题：{article['title']}\n来源：{article['source_name']}\n"
            f"发布时间：{article['published_at']}\n摘要：{article['summary']}"
        )
        try:
            result = LLMClient().complete_structured_with_meta(
                "你是行业信息分析助手。输出必须符合 schema；summary 只总结来源事实，"
                "career_impact 必须标为推断而非新闻事实。",
                prompt,
                IndustryPulseAnalysisOut,
            )
            updated = industry_pulse_repository.update_analysis(
                article_id, status="analyzed", ai_summary=result.value.summary,
                career_impact=result.value.career_impact, tags=result.value.keywords,
                details={"event": result.value.event, "affected_roles": result.value.affected_roles},
                model=result.model, error="",
            )
            return _article_out(updated or article)
        except Exception as exc:
            industry_pulse_repository.update_analysis(
                article_id, status="failed", error=str(exc)[:1000]
            )
            logger.exception("industry_pulse_ai_analysis_failed")
            raise AppError("INDUSTRY_PULSE_ANALYSIS_FAILED", "AI 分析失败，可稍后重试", status_code=502) from exc


_service: IndustryPulseService | None = None


def get_industry_pulse_service() -> IndustryPulseService:
    global _service
    if _service is None:
        _service = IndustryPulseService()
    return _service
