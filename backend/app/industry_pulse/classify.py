import re
from dataclasses import dataclass, field
from typing import Any

from app.industry_pulse.industry_lexicon import (
    BOUNDARY_RULES,
    ENTITY_INDUSTRY,
    EVENT_TERMS,
    INDUSTRY_KEYWORDS,
    MACRO_TERMS,
    NON_INDUSTRY_PATTERNS,
    REVIEW_PATTERNS,
    SECONDARY_ENTITY_ALLOW,
    SIGNAL_GROUPS,
    STRONG_SIGNALS,
)
from app.industry_pulse.sources import FeedSource
from app.industry_pulse.taxonomy import (
    INDUSTRY_ORDER,
    RELEVANCE_INDUSTRY_RELEVANT,
    RELEVANCE_IRRELEVANT,
    RELEVANCE_MACRO_SIGNAL,
    RELEVANCE_NEEDS_REVIEW,
)

RULE_VERSION = "industry-v2.1"

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI": ("人工智能", "ai", "大模型", "智能体", "agent", "机器学习", "生成式ai"),
    "政策": ("政策", "监管", "规划", "部委", "国务院", "政府", "条例", "标准"),
    "招聘": ("招聘", "岗位", "就业", "人才", "用工", "技能", "裁员"),
    "投融资": ("融资", "投资", "并购", "ipo", "上市", "估值", "回购"),
    "技术突破": ("突破", "首次", "发布", "开源", "专利", "创新", "量产"),
}


@dataclass(frozen=True)
class Classification:
    relevance: str
    primary_industry: str | None
    industries: tuple[str, ...]
    tags: tuple[str, ...] = ()
    basis: dict[str, Any] = field(default_factory=dict)
    confidence: str = "medium"


def _matches(text: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    matched: list[str] = []
    for keyword in sorted(keywords, key=len, reverse=True):
        token = keyword.lower()
        if token.isascii():
            if re.search(rf"(?<![a-z]){re.escape(token)}s?(?![a-z])", lowered):
                matched.append(keyword)
        elif token in lowered:
            matched.append(keyword)
    return [
        keyword
        for keyword in matched
        if not any(
            keyword != other and keyword.lower() in other.lower()
            for other in matched
        )
    ]


def _hit(
    text: str, keywords: dict[str, tuple[str, ...]]
) -> dict[str, list[str]]:
    return {industry: _matches(text, terms) for industry, terms in keywords.items()}


def _entity_hit(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for token in _matches(text, tuple(ENTITY_INDUSTRY)):
        for industry in ENTITY_INDUSTRY[token]:
            hits.setdefault(industry, []).append(token)
    return hits


def classify_article(source: FeedSource, title: str, summary: str) -> Classification:
    text = f"{title}\n{summary}"
    title_hits = _hit(title, INDUSTRY_KEYWORDS)
    text_hits = _hit(text, INDUSTRY_KEYWORDS)

    entity_hits = _entity_hit(text)
    title_entity_hits = _entity_hit(title)

    signal_groups = {
        group: _matches(text, terms) for group, terms in SIGNAL_GROUPS.items()
    }
    signals = sorted({term for terms in signal_groups.values() for term in terms})
    strong_signals = sorted(set(signals) & STRONG_SIGNALS)

    macro_terms = _matches(text, MACRO_TERMS)
    event_terms = _matches(title, EVENT_TERMS)
    non_industry = {
        group: _matches(text, terms)
        for group, terms in NON_INDUSTRY_PATTERNS.items()
    }
    review_flags = {
        group: _matches(text, terms)
        for group, terms in REVIEW_PATTERNS.items()
    }
    review_flags = {group: terms for group, terms in review_flags.items() if terms}

    hint = set(source.industries) & set(INDUSTRY_ORDER)
    boundary_notes: list[str] = []
    boundary_added: set[str] = set()
    for rule in BOUNDARY_RULES:
        triggered = _matches(text, rule.triggers)
        if not triggered:
            continue
        boundary_notes.append(f"{rule.key}:{'/'.join(triggered)}")
        for industry in rule.add:
            title_hits.setdefault(industry, []).append(f"boundary:{rule.key}")
            boundary_added.add(industry)
    for rule in BOUNDARY_RULES:
        if not _matches(text, rule.triggers):
            continue
        for industry in rule.suppress:
            if industry in boundary_added:
                continue
            title_hits.pop(industry, None)
            text_hits.pop(industry, None)
            entity_hits.pop(industry, None)

    candidates = {
        industry
        for industry in INDUSTRY_ORDER
        if title_hits.get(industry)
        or text_hits.get(industry)
        or entity_hits.get(industry)
    }
    total_title_entities = sum(
        len(terms) for terms in title_entity_hits.values()
    )
    qualified: list[tuple[int, str]] = []
    for industry in INDUSTRY_ORDER:
        if industry not in candidates:
            continue
        title_terms = title_hits.get(industry, [])
        body_terms = text_hits.get(industry, [])
        entities = entity_hits.get(industry, [])
        title_entities = title_entity_hits.get(industry, [])
        has_signal = bool(signals)
        has_strong = bool(strong_signals)
        if industry in boundary_added and (title_terms or title_entities):
            ok = True
        elif title_entities and (
            title_terms
            or body_terms
            or has_signal
            or total_title_entities >= 2
        ):
            ok = True
        elif entities and title_terms and has_signal:
            # Body-only entity mentions cannot invent a new industry topic.
            ok = True
        elif title_terms and (has_signal or len(title_terms) >= 2):
            ok = True
        elif body_terms and has_signal and len(body_terms) >= 2:
            ok = True
        else:
            ok = False
        if not ok:
            continue
        score = (
            3 * len(title_terms)
            + len(body_terms)
            + (3 if entities else 0)
            + (2 if has_strong else (1 if has_signal else 0))
            + (1 if industry in hint and title_terms else 0)
            + (1 if industry == "health_life_sciences" and len(title_terms) >= 2 else 0)
        )
        qualified.append((score, industry))

    blocked: str | None = None
    if not strong_signals:
        for group in (
            "health_science", "politics", "accident", "weather", "social", "campus"
        ):
            if non_industry.get(group):
                blocked = group
                break
        if review_flags.get("personal"):
            blocked = "personal"

    if blocked:
        return Classification(
            relevance=RELEVANCE_IRRELEVANT,
            primary_industry=None,
            industries=(),
            tags=_tags(text),
            basis=_basis(
                RULE_VERSION, title_hits, text_hits, entity_hits, signal_groups,
                signals, strong_signals, macro_terms, event_terms, non_industry,
                review_flags, boundary_notes, hint, {}, confidence="high",
            ),
            confidence="high",
        )

    ranked = sorted(
        qualified,
        key=lambda item: (-item[0], INDUSTRY_ORDER.index(item[1])),
    )
    selected: list[str] = []
    for _score, industry in ranked:
        if len(selected) >= 3:
            break
        # Secondary labels need a title-level keyword, or an explicit product
        # entity such as 千问; a media/retail conglomerate alone (e.g. Netflix
        # in an AI infrastructure story) is not enough.
        if selected and not title_hits.get(industry):
            allowed_products = {
                token
                for token in title_entity_hits.get(industry, [])
                if token in SECONDARY_ENTITY_ALLOW
            }
            if not allowed_products:
                continue
        selected.append(industry)

    if qualified and selected and not review_flags:
        title_support = any(title_hits.get(ind) for ind in selected)
        title_entity_support = any(
            title_entity_hits.get(ind) for ind in selected
        )
        entity_support = any(entity_hits.get(ind) for ind in selected)
        if strong_signals and (title_entity_support or entity_support):
            confidence = "high"
        elif title_support and (
            signals
            or any(len(title_hits.get(ind, [])) >= 2 for ind in selected)
            or title_entity_support
            or any(ind in boundary_added for ind in selected)
        ):
            confidence = "medium"
        elif title_entity_support and signals:
            confidence = "medium"
        else:
            confidence = "low"

        if confidence != "low":
            relevance = RELEVANCE_INDUSTRY_RELEVANT
            return Classification(
            relevance=relevance,
            primary_industry=selected[0],
            industries=tuple(selected),
            tags=_tags(text),
            basis=_basis(
                RULE_VERSION, title_hits, text_hits, entity_hits, signal_groups,
                signals, strong_signals, macro_terms, event_terms, non_industry,
                review_flags, boundary_notes, hint,
                {ind: score for score, ind in qualified}, confidence,
            ),
            confidence=confidence,
        )

    if qualified or review_flags or candidates:
        relevance = RELEVANCE_NEEDS_REVIEW
        confidence = "low"
    elif macro_terms:
        relevance = RELEVANCE_MACRO_SIGNAL
        confidence = "high"
    elif event_terms:
        relevance = RELEVANCE_NEEDS_REVIEW
        confidence = "low"
    else:
        relevance = RELEVANCE_IRRELEVANT
        confidence = "high"
    return Classification(
        relevance=relevance,
        primary_industry=None,
        industries=(),
        tags=_tags(text),
        basis=_basis(
            RULE_VERSION, title_hits, text_hits, entity_hits, signal_groups,
            signals, strong_signals, macro_terms, event_terms, non_industry,
            review_flags, boundary_notes, hint, {ind: score for score, ind in qualified},
            confidence,
        ),
        confidence=confidence,
    )


def _tags(text: str) -> tuple[str, ...]:
    return tuple(
        label for label, keywords in TOPIC_KEYWORDS.items() if _matches(text, keywords)
    )


def _basis(
    rule_version: str,
    title_hits: dict[str, list[str]],
    text_hits: dict[str, list[str]],
    entity_hits: dict[str, list[str]],
    signal_groups: dict[str, list[str]],
    signals: list[str],
    strong_signals: list[str],
    macro_terms: list[str],
    event_terms: list[str],
    non_industry: dict[str, list[str]],
    review_flags: dict[str, list[str]],
    boundary_notes: list[str],
    hint: set[str],
    scores: dict[str, int],
    confidence: str,
) -> dict[str, Any]:
    return {
        "rule_version": rule_version,
        "matched_terms": {
            industry: sorted(set(text_hits.get(industry, [])))
            for industry in INDUSTRY_ORDER
            if text_hits.get(industry)
        },
        "title_terms": {
            industry: sorted(set(terms))
            for industry, terms in title_hits.items()
            if terms
        },
        "entity_hits": {industry: terms for industry, terms in entity_hits.items()},
        "signal_groups": {group: terms for group, terms in signal_groups.items() if terms},
        "signals": signals,
        "strong_signals": strong_signals,
        "macro_terms": macro_terms,
        "event_terms": event_terms,
        "non_industry": {group: terms for group, terms in non_industry.items() if terms},
        "review_flags": review_flags,
        "boundary_rules": boundary_notes,
        "source_hint": sorted(hint),
        "source_hint_used": bool(set(scores) & hint),
        "scores": scores,
        "confidence": confidence,
    }
