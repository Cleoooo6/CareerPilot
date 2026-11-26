from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.industry_trends_repository import IndustryTrendsRepository, industry_trends_repository
from app.industry_pulse.taxonomy import INDUSTRY_LABELS, INDUSTRY_ORDER
from app.schemas.industry_trends import (
    IndustryCatalogItem,
    IndustryTrendItem,
    IndustryTrendsOut,
    InsufficientIndustry,
    PersonalIndustryTrendsOut,
    PersonalSkillGap,
    PersonalTrendItem,
    RoadmapTrendSuggestion,
    TrendCountItem,
    TrendEvidence,
    TrendMonthCount,
    TrendNewsItem,
    TrendSkillItem,
)
from app.services.market_cleaner import normalize_skill

MIN_MARKET_SAMPLE = 5
MIN_MARKET_MONTHS = 2
NEWS_LONG_SPAN_DAYS = 30
MAX_NEWS_EXAMPLES = 3

MARKET_INDUSTRY_MAP = {
    "互联网": "digital_tech_comms",
    "云计算": "digital_tech_comms",
    "人工智能": "digital_tech_comms",
    "软件": "digital_tech_comms",
    "金融科技": "finance_insurance",
    "银行": "finance_insurance",
    "保险": "finance_insurance",
    "新零售": "consumer_retail_services",
    "零售": "consumer_retail_services",
    "电商": "consumer_retail_services",
    "企业服务": "enterprise_professional_services",
    "咨询": "enterprise_professional_services",
    "制造": "manufacturing_industry",
    "半导体": "manufacturing_industry",
    "能源": "energy_environment",
    "新能源": "energy_environment",
    "汽车": "auto_smart_mobility",
    "物流": "transport_logistics",
    "供应链": "transport_logistics",
    "医疗": "health_life_sciences",
    "健康": "health_life_sciences",
    "教育": "education_research",
    "科研": "education_research",
    "农业": "agriculture_food",
    "食品": "agriculture_food",
    "房地产": "real_estate_construction",
    "建筑": "real_estate_construction",
    "文化": "culture_media_content",
    "传媒": "culture_media_content",
    "艺术": "arts_design",
    "设计": "arts_design",
    "体育": "sports_industry",
    "旅游": "tourism_hospitality_events",
    "酒店": "tourism_hospitality_events",
}

CATALOG = [IndustryCatalogItem(id=i, label=INDUSTRY_LABELS[i]) for i in INDUSTRY_ORDER]


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _month(value: datetime) -> str:
    return value.strftime("%Y-%m")


def _skill_key(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    normalized = normalize_skill(text)
    return (normalized or text).lower()


def _map_industry(value: str, *, title: str = "") -> str | None:
    text = (value or "").strip()
    if text in INDUSTRY_ORDER:
        return text
    for label, industry in ((INDUSTRY_LABELS[i], i) for i in INDUSTRY_ORDER):
        if text == label or label in text:
            return industry
    for keyword, industry in MARKET_INDUSTRY_MAP.items():
        if keyword in text:
            return industry
    probe = f"{text} {title}"
    for label, industry in ((INDUSTRY_LABELS[i], i) for i in INDUSTRY_ORDER):
        if label in probe:
            return industry
    return None


def _counts(counter: Counter[str], limit: int) -> list[TrendCountItem]:
    return [
        TrendCountItem(name=name, count=count)
        for name, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:limit]
    ]


def _skills(
    counter: Counter[str], total: int, limit: int = 8
) -> list[TrendSkillItem]:
    return [
        TrendSkillItem(
            skill=name,
            count=count,
            share=round(count / total, 4) if total else 0.0,
        )
        for name, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:limit]
    ]


class IndustryTrendsService:
    def __init__(self, repository: IndustryTrendsRepository | None = None) -> None:
        self.repository = repository or industry_trends_repository

    def overall(
        self, *, industry: str = "all", months: int = 12
    ) -> IndustryTrendsOut:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=months * 30)
        news_rows = self.repository.news_rows(since)
        job_rows = self.repository.job_rows(since)
        news = self._news_stats(news_rows)
        # Keep real and synthetic evidence separate. A real industry must never
        # be inflated by demo rows; synthetic rows are only a fallback for
        # industries that have no real sample at all.
        real_rows = [
            row for row in job_rows if row.get("dataset_kind") == "real"
        ]
        synthetic_rows = [
            row for row in job_rows if row.get("dataset_kind") == "synthetic"
        ]
        real_jobs, real_unmapped = self._job_stats(real_rows)
        synthetic_jobs, synthetic_unmapped = self._job_stats(synthetic_rows)
        jobs: dict[str, dict[str, Any]] = {}
        for industry_id in set(real_jobs) | set(synthetic_jobs):
            real_stat = real_jobs.get(industry_id)
            if real_stat is not None and real_stat["count"] > 0:
                jobs[industry_id] = real_stat
            elif industry_id in synthetic_jobs:
                jobs[industry_id] = synthetic_jobs[industry_id]
        unmapped = real_unmapped + synthetic_unmapped
        self._attach_jobs_cache(jobs)
        warnings = []
        if any(stat["synthetic"] for stat in jobs.values()):
            warnings.append(
                "市场岗位数据包含 synthetic 合成数据，仅用于链路验证，不代表真实招聘市场。"
            )
        if real_rows and synthetic_rows:
            warnings.append(
                "检测到真实与 synthetic 岗位并存；每个行业优先使用真实数据，"
                "synthetic 仅用于无真实样本行业的演示并明确标注。"
            )
        if unmapped:
            warnings.append(
                f"{unmapped} 条岗位的行业无法映射到 16 行业，未纳入行业趋势。"
            )

        items: list[IndustryTrendItem] = []
        insufficient: list[InsufficientIndustry] = []
        for industry_id in INDUSTRY_ORDER:
            if industry != "all" and industry_id != industry:
                continue
            item = self._build_item(industry_id, news, jobs)
            if item is not None:
                items.append(item)
            else:
                news_stat = news.get(industry_id, {"count": 0})
                job_stat = jobs.get(industry_id, {"count": 0})
                insufficient.append(
                    InsufficientIndustry(
                        industry_id=industry_id,
                        label=INDUSTRY_LABELS[industry_id],
                        reason=self._insufficient_reason(
                            news_stat, job_stat
                        ),
                        news_count=news_stat.get("count", 0),
                        job_count=job_stat.get("count", 0),
                    )
                )
        if industry != "all" and not items and not insufficient:
            insufficient.append(
                InsufficientIndustry(
                    industry_id=industry,
                    label=INDUSTRY_LABELS.get(industry, industry),
                    reason="暂无高相关新闻与岗位证据",
                    news_count=0,
                    job_count=0,
                )
            )
        return IndustryTrendsOut(
            generated_at=now,
            months=months,
            industry_filter=industry,
            items=items,
            insufficient_industries=insufficient,
            warnings=warnings,
            industry_catalog=CATALOG,
        )

    def personal(
        self,
        profile_data: dict[str, Any] | None,
        *,
        industry: str = "all",
        months: int = 12,
    ) -> PersonalIndustryTrendsOut:
        overall = self.overall(industry=industry, months=months)
        profile = profile_data or {}
        basic = profile.get("basic") or {}
        goals = profile.get("goals") or {}
        target_role = str(goals.get("target_role") or "").strip()
        target_industry = str(goals.get("target_industry") or "").strip()
        target_location = str(basic.get("location") or "").strip()
        profile_skills = [
            str(item.get("name") or "").strip()
            for item in profile.get("skills", [])
            if str(item.get("name") or "").strip()
        ]
        profile_missing = []
        if not target_role:
            profile_missing.append("目标岗位")
        if not target_industry:
            profile_missing.append("目标行业")
        if not target_location:
            profile_missing.append("目标地区")
        if not profile_skills:
            profile_missing.append("已有技能")
        sufficient = bool(target_role or target_industry)
        target_industry_id = _map_industry(target_industry) if target_industry else None
        target_label = (
            INDUSTRY_LABELS.get(target_industry_id, "")
            if target_industry_id
            else target_industry
        )
        base = PersonalIndustryTrendsOut(
            generated_at=overall.generated_at,
            months=months,
            profile_sufficient=sufficient,
            profile_missing=profile_missing,
            target_role=target_role,
            target_industry=target_industry,
            target_industry_label=target_label,
            target_location=target_location,
            items=[],
            insufficient_reason="",
            warnings=list(overall.warnings),
            industry_catalog=overall.industry_catalog,
        )
        if not sufficient:
            base.insufficient_reason = (
                "当前 Profile 缺少目标岗位或目标行业，无法判断哪些行业趋势与你有关。"
                "请先在 Profile 中补充目标方向，系统不会凭空推断匹配度。"
            )
            return base

        skill_keys = {_skill_key(item): item for item in profile_skills}
        matched_any = False
        for item in overall.items:
            if industry != "all" and item.industry_id != industry:
                continue
            job_stat = self._job_stat_for(item.industry_id)
            if job_stat is None:
                continue
            role_count = job_stat["titles"].get(target_role, 0) if target_role else 0
            location_count = job_stat["locations"].get(target_location, 0) if target_location else 0
            role_skills = (
                job_stat["role_skills"].get(target_role)
                if target_role and target_role in job_stat["role_skills"]
                else job_stat["skills"]
            )
            matched = [
                skill
                for skill in role_skills
                if _skill_key(skill) in skill_keys
            ]
            missing = [
                skill
                for skill, _count in sorted(
                    role_skills.items(), key=lambda x: (-x[1], x[0])
                )
                if _skill_key(skill) not in skill_keys
            ][:5]
            score = 0
            goals_matched: list[str] = []
            if target_industry_id == item.industry_id:
                score += 3
                goals_matched.append(
                    f"目标行业「{target_label or target_industry}」"
                )
            if role_count:
                score += 3
                goals_matched.append(f"目标岗位「{target_role}」")
            if location_count:
                score += 1
                goals_matched.append(f"目标地区「{target_location}」")
            if matched:
                score += min(2, len(matched))
                goals_matched.append(f"已记录技能 {len(matched)} 项")
            if score < 3:
                continue
            matched_any = True
            gaps = [
                PersonalSkillGap(
                    name=skill,
                    count=role_skills[skill],
                    share=round(
                        role_skills[skill] / max(1, job_stat["count"]), 4
                    ),
                    recorded=False,
                    evidence_note="画像尚未记录该技能；没有记录不等于不具备。",
                )
                for skill in missing
            ]
            matched_gaps = [
                PersonalSkillGap(
                    name=skill,
                    count=role_skills[skill],
                    share=round(
                        role_skills[skill] / max(1, job_stat["count"]), 4
                    ),
                    recorded=True,
                    evidence_note=(
                        "画像有记录；资料已确认不等于客观能力验证，"
                        "当前没有额外客观验证。"
                    ),
                )
                for skill in matched
            ]
            suggested = missing[:3]
            relevance = "high" if score >= 8 else "medium" if score >= 5 else "low"
            why = []
            if target_industry_id == item.industry_id:
                if target_industry and target_label and target_industry != target_label:
                    why.append(
                        f"目标行业「{target_industry}」对应展示行业「{target_label}」。"
                    )
                else:
                    why.append(
                        f"目标行业「{target_label or target_industry}」对应该行业。"
                    )
            if role_count:
                why.append(f"目标岗位「{target_role}」在当前岗位样本中有 {role_count} 条。")
            if location_count:
                why.append(f"目标地区「{target_location}」在当前岗位样本中有 {location_count} 条。")
            if matched:
                why.append(f"画像已记录 {', '.join(matched)}，与岗位技能有交集。")
            if not why:
                why.append("画像目标与该行业的岗位/技能证据存在交集。")
            impact = (
                f"该行业当前有 {item.job_count} 条岗位样本，"
                f"目标岗位「{target_role or '未填写'}」相关样本 {role_count} 条。"
                f"市场数据性质：{'合成/演示，仅用于链路验证' if item.evidence.synthetic else '现有真实数据'}；"
                f"新闻 {item.news_count} 篇、{item.news_source_count} 个来源，仅作辅助。"
            )
            opportunities = []
            if target_industry_id == item.industry_id and role_count:
                opportunities.append("目标行业与目标岗位同时出现岗位样本，可作为优先关注方向。")
            if matched:
                opportunities.append(
                    f"已有 {', '.join(matched)} 的资料记录，可继续补充项目证据，而非重复从零学习。"
                )
            if location_count:
                opportunities.append(f"目标地区有 {location_count} 条相关岗位样本。")
            risks = [
                "岗位样本量较小且可能为合成数据，不能当作真实长期市场结论。",
                "画像资料已确认不等于客观能力验证；系统不会据此给你打分。",
            ]
            if missing:
                risks.append(
                    f"{', '.join(missing[:3])} 尚未记录；这是信息缺口，不是能力否定。"
                )
            next_actions = [
                f"围绕 {', '.join(suggested)} 补充一个可验证的项目或实践成果。",
                "用真实招聘数据复核该趋势后再决定是否调整目标。",
                "在 My Roadmap 中查看技能差距，确认是否加入学习阶段。",
            ]
            roadmap = RoadmapTrendSuggestion(
                reason=(
                    f"目标岗位「{target_role}」的岗位样本中出现 "
                    f"{', '.join(suggested) if suggested else '部分技能'}，"
                    "画像尚未记录；建议仅作复核，不自动修改路线。"
                ),
                suggested_skills=suggested,
                deprioritize_skills=[],
                requires_confirmation=True,
                confirm_url="/roadmap",
            )
            facts = [
                f"目标岗位：{target_role or '未填写'}；目标行业：{target_industry or '未填写'}；目标地区：{target_location or '未填写'}。",
                f"画像技能：{', '.join(profile_skills) if profile_skills else '未记录'}。",
                f"该行业岗位样本 {item.job_count} 条，目标岗位样本 {role_count} 条。",
                f"相关新闻 {item.news_count} 篇，来自 {item.news_source_count} 个来源。",
            ]
            inferences = [
                f"系统推断：该趋势与目标{'行业' if target_industry_id == item.industry_id else '岗位/技能'}存在关联，依据仅为上述画像与市场字段。",
                "系统推断：未记录的技能是信息缺口，不能据此判断“不会”或“不胜任”。",
            ]
            suggestions = [
                "先补充证据，再决定是否把建议加入 Roadmap。",
                "不要因为单篇新闻或单个岗位样本改变长期方向。",
            ]
            base.items.append(
                PersonalTrendItem(
                    trend=item,
                    relevance_confidence=relevance,
                    why_relevant=why,
                    matched_goals=goals_matched,
                    matched_skills=matched,
                    missing_skills=missing,
                    skill_gaps=matched_gaps + gaps,
                    affected_roles=_counts(job_stat["titles"], 6),
                    impact=impact,
                    opportunities=opportunities,
                    risks=risks,
                    next_actions=next_actions,
                    roadmap_suggestion=roadmap,
                    facts=facts,
                    inferences=inferences,
                    suggestions=suggestions,
                )
            )
            base.items.sort(
            key=lambda x: (
                {"high": 0, "medium": 1, "low": 2}[x.relevance_confidence],
                -x.trend.job_count,
                x.trend.label,
            )
        )
        if not matched_any:
            base.insufficient_reason = (
                "当前目标行业/岗位没有同时满足“市场样本 + 新闻辅助”证据门槛的趋势。"
                "系统不生成无证据的个性化匹配，请先补充目标方向或等待更多真实数据。"
            )
        return base

    def _news_stats(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        seen: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            observed = _aware(row.get("observed_at"))
            for industry in set(row.get("industries") or []):
                if industry not in INDUSTRY_ORDER or row["id"] in seen[industry]:
                    continue
                seen[industry].add(row["id"])
                stat = stats.setdefault(
                    industry,
                    {"count": 0, "sources": set(), "dates": [], "examples": []},
                )
                stat["count"] += 1
                if row.get("source_name"):
                    stat["sources"].add(str(row["source_name"]))
                if observed:
                    stat["dates"].append(observed)
                stat["examples"].append(
                    TrendNewsItem(
                        id=str(row["id"]),
                        title=str(row["title"]),
                        source=str(row.get("source_name") or "未知来源"),
                        published_at=observed,
                        url=str(row.get("url") or ""),
                    )
                )
        for stat in stats.values():
            stat["examples"].sort(
                key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            stat["examples"] = stat["examples"][:MAX_NEWS_EXAMPLES]
            stat["period_start"] = min(stat["dates"]) if stat["dates"] else None
            stat["period_end"] = max(stat["dates"]) if stat["dates"] else None
            stat["span_days"] = (
                (stat["period_end"] - stat["period_start"]).days
                if stat["period_start"] and stat["period_end"]
                else 0
            )
        return stats

    def _job_stats(
        self, rows: list[dict[str, Any]]
    ) -> tuple[dict[str, dict[str, Any]], int]:
        stats: dict[str, dict[str, Any]] = {}
        unmapped = 0
        seen_ids: set[str] = set()
        for row in rows:
            row_id = str(row.get("id") or "")
            if row_id and row_id in seen_ids:
                continue
            if row_id:
                seen_ids.add(row_id)
            industry = _map_industry(
                str(row.get("industry") or ""), title=str(row.get("title") or "")
            )
            if industry is None:
                unmapped += 1
                continue
            stat = stats.setdefault(industry, self._empty_job_stat())
            title = str(row.get("title") or "").strip()
            observed = _aware(row.get("observed_at"))
            skills = [
                str(skill).strip()
                for skill in (row.get("skills") or [])
                if str(skill).strip()
            ]
            stat["count"] += 1
            if title:
                stat["titles"][title] += 1
            if observed:
                stat["dates"].append(observed)
                stat["months"][_month(observed)] += 1
            for skill in skills:
                stat["skills"][skill] += 1
                if title:
                    stat["role_skills"][title][skill] += 1
            if row.get("location"):
                stat["locations"][str(row["location"])] += 1
            if row.get("education"):
                stat["education"][str(row["education"])] += 1
            if row.get("experience"):
                stat["experience"][str(row["experience"])] += 1
            if row.get("source_name"):
                stat["sources"].add(str(row["source_name"]))
            if row.get("dataset_kind"):
                stat["dataset_kinds"].add(str(row["dataset_kind"]))
        for stat in stats.values():
            stat["period_start"] = min(stat["dates"]) if stat["dates"] else None
            stat["period_end"] = max(stat["dates"]) if stat["dates"] else None
            stat["synthetic"] = "synthetic" in stat["dataset_kinds"]
        return stats, unmapped

    @staticmethod
    def _empty_job_stat() -> dict[str, Any]:
        return {
            "count": 0,
            "titles": Counter(),
            "skills": Counter(),
            "locations": Counter(),
            "education": Counter(),
            "experience": Counter(),
            "months": Counter(),
            "role_skills": defaultdict(Counter),
            "sources": set(),
            "dataset_kinds": set(),
            "dates": [],
            "synthetic": False,
        }

    def _job_stat_for(self, industry: str) -> dict[str, Any] | None:
        return getattr(self, "_jobs_cache", {}).get(industry)

    def _build_item(
        self,
        industry: str,
        news: dict[str, dict[str, Any]],
        jobs: dict[str, dict[str, Any]],
    ) -> IndustryTrendItem | None:
        news_stat = news.get(
            industry, {"count": 0, "sources": set(), "span_days": 0, "examples": []}
        )
        job_stat = jobs.get(industry, self._empty_job_stat())
        job_count = job_stat["count"]
        month_count = len(job_stat["months"])
        news_count = news_stat["count"]
        news_sources = len(news_stat.get("sources", set()))
        news_span = news_stat.get("span_days", 0)
        market_supported = (
            job_count >= MIN_MARKET_SAMPLE and month_count >= MIN_MARKET_MONTHS
        )
        news_long = (
            news_count >= 2
            and news_sources >= 2
            and news_span >= NEWS_LONG_SPAN_DAYS
        )
        if not market_supported and not news_long:
            return None
        synthetic = bool(job_stat["synthetic"])
        evidence_level = (
            "strong"
            if market_supported and news_long and not synthetic
            else "medium"
        )
        confidence = "low" if synthetic else ("high" if news_long else "medium")
        direction, trend_word = self._direction(job_stat, market_supported)
        gaps = []
        if job_count < MIN_MARKET_SAMPLE:
            gaps.append(f"岗位样本 {job_count} 条，少于 5 条")
        if month_count < MIN_MARKET_MONTHS:
            gaps.append(f"岗位时间跨度 {month_count} 个月，少于 2 个月")
        if news_count < 2:
            gaps.append(f"新闻证据 {news_count} 篇，少于 2 篇")
        if news_sources < 2:
            gaps.append(f"新闻来源 {news_sources} 个，少于 2 个")
        if news_span < NEWS_LONG_SPAN_DAYS:
            gaps.append(f"新闻时间跨度 {news_span} 天，不足 30 天")
        if synthetic:
            gaps.append("市场数据包含 synthetic 合成数据，仅用于链路验证")
        basis = (
            "market_news"
            if market_supported and news_count
            else "market"
            if market_supported
            else "news"
        )
        title = f"{INDUSTRY_LABELS[industry]}：{trend_word}"
        if market_supported:
            summary = (
                f"岗位样本 {job_count} 条，覆盖 {month_count} 个月，"
                f"月度需求{trend_word}；新闻 {news_count} 篇来自 {news_sources} 个来源，"
                f"时间跨度 {news_span} 天，作为辅助证据。"
            )
        else:
            summary = (
                f"新闻 {news_count} 篇来自 {news_sources} 个来源，跨度 {news_span} 天；"
                "尚未达到长期趋势所需的跨时间证据门槛。"
            )
        if synthetic:
            summary += "市场数据为合成演示，不能作为真实就业市场结论。"
        items = [
            TrendMonthCount(period=period, count=count)
            for period, count in sorted(job_stat["months"].items())
        ]
        evidence = TrendEvidence(
            news_count=news_count,
            news_source_count=news_sources,
            news_period_start=news_stat.get("period_start"),
            news_period_end=news_stat.get("period_end"),
            news_span_days=news_span,
            news_examples=news_stat.get("examples", []),
            job_count=job_count,
            job_month_count=month_count,
            job_period_start=job_stat.get("period_start"),
            job_period_end=job_stat.get("period_end"),
            job_months=items,
            roles=_counts(job_stat["titles"], 6),
            skills=_skills(job_stat["skills"], max(1, job_count)),
            locations=_counts(job_stat["locations"], 6),
            education=_counts(job_stat["education"], 4),
            experience=_counts(job_stat["experience"], 4),
            dataset_kinds=sorted(job_stat["dataset_kinds"]),
            synthetic=synthetic,
            sources=sorted(
                set(job_stat["sources"]) | set(news_stat.get("sources", set()))
            ),
        )
        return IndustryTrendItem(
            industry_id=industry,
            label=INDUSTRY_LABELS[industry],
            title=title,
            summary=summary,
            direction=direction,
            confidence=confidence,
            evidence_level=evidence_level,
            basis=basis,
            period_start=min(
                [d for d in (evidence.news_period_start, evidence.job_period_start) if d],
                default=None,
            ),
            period_end=max(
                [d for d in (evidence.news_period_end, evidence.job_period_end) if d],
                default=None,
            ),
            news_count=news_count,
            news_source_count=news_sources,
            job_count=job_count,
            roles=evidence.roles,
            skills=evidence.skills,
            locations=evidence.locations,
            data_gaps=gaps,
            evidence=evidence,
        )

    @staticmethod
    def _direction(
        job_stat: dict[str, Any], market_supported: bool
    ) -> tuple[str, str]:
        months = sorted(job_stat["months"].items())
        if market_supported and job_stat["count"] >= 10 and len(months) >= 4:
            recent = sum(count for _, count in months[-2:])
            prior = sum(count for _, count in months[:-2])
            if prior:
                change = (recent - prior) / prior
                if change >= 0.2:
                    return "rising", "上升"
                if change <= -0.2:
                    return "cooling", "回落"
            return "stable", "平稳"
        if market_supported:
            return "unclear", "信号待确认"
        return "unclear", "新闻关注度待确认"

    @staticmethod
    def _insufficient_reason(
        news_stat: dict[str, Any], job_stat: dict[str, Any]
    ) -> str:
        parts = []
        if job_stat.get("count", 0) < MIN_MARKET_SAMPLE:
            parts.append(f"岗位样本 {job_stat.get('count', 0)} 条（少于 5）")
        if len(job_stat.get("months", {})) < MIN_MARKET_MONTHS:
            parts.append(f"岗位时间跨度不足 {MIN_MARKET_MONTHS} 个月")
        if news_stat.get("count", 0) < 2:
            parts.append(f"新闻证据 {news_stat.get('count', 0)} 篇（少于 2）")
        if len(news_stat.get("sources", set())) < 2:
            parts.append("新闻来源少于 2 个")
        if news_stat.get("span_days", 0) < NEWS_LONG_SPAN_DAYS:
            parts.append(f"新闻时间跨度不足 {NEWS_LONG_SPAN_DAYS} 天")
        return "；".join(parts) + "。证据不足，暂无法形成可靠趋势。"

    def _attach_jobs_cache(self, jobs: dict[str, dict[str, Any]]) -> None:
        self._jobs_cache = jobs


_service: IndustryTrendsService | None = None


def get_industry_trends_service() -> IndustryTrendsService:
    global _service
    if _service is None:
        _service = IndustryTrendsService()
    return _service


def reset_industry_trends_service() -> None:
    global _service
    _service = None
