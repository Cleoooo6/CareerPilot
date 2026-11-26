from datetime import datetime
from typing import Any

from app.industry_pulse.taxonomy import INDUSTRY_LABELS, INDUSTRY_ORDER
from app.services.industry_trends_service import MARKET_INDUSTRY_MAP

CROSS_INDUSTRY_KEYWORDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("digital_tech_comms", "manufacturing_industry"): ("芯片", "半导体", "硬件", "工业软件", "机器人", "具身智能", "算力"),
    ("digital_tech_comms", "finance_insurance"): ("金融科技", "支付", "风控", "证券", "银行"),
    ("digital_tech_comms", "consumer_retail_services"): ("电商", "零售科技", "消费电子", "手机", "智能硬件"),
    ("digital_tech_comms", "enterprise_professional_services"): ("企业服务", "saas", "数字化", "咨询"),
    ("digital_tech_comms", "health_life_sciences"): ("医疗ai", "智慧医疗", "医学影像", "辅助诊断", "医院信息化"),
    ("digital_tech_comms", "education_research"): ("教育科技", "在线教育", "课程", "学校"),
    ("digital_tech_comms", "auto_smart_mobility"): ("智能驾驶", "自动驾驶", "车载", "车联网"),
    ("energy_environment", "auto_smart_mobility"): ("新能源车", "电动车", "充电"),
    ("culture_media_content", "tourism_hospitality_events"): ("文旅", "旅游"),
    ("arts_design", "culture_media_content"): ("设计", "内容", "版权"),
    ("finance_insurance", "real_estate_construction"): ("房贷", "房地产", "物业"),
    ("agriculture_food", "consumer_retail_services"): ("食品", "零售", "电商"),
    ("transport_logistics", "manufacturing_industry"): ("航空制造", "物流装备"),
    ("sports_industry", "culture_media_content"): ("体育", "赛事"),
    ("sports_industry", "health_life_sciences"): ("运动", "健康"),
    ("sports_industry", "consumer_retail_services"): ("体育消费", "体育用品"),
    ("energy_environment", "manufacturing_industry"): ("新能源装备", "电池", "储能"),
    ("auto_smart_mobility", "transport_logistics"): ("智能出行", "运输"),
    ("health_life_sciences", "education_research"): ("医学教育", "科研"),
    ("agriculture_food", "transport_logistics"): ("农产品", "供应链"),
    ("real_estate_construction", "manufacturing_industry"): ("建筑材料", "工程装备"),
    ("enterprise_professional_services", "finance_insurance"): ("企业金融", "合规"),
    ("arts_design", "digital_tech_comms"): ("数字艺术", "设计工具"),
}

GENERIC_ROLE_TERMS = frozenset(
    {"工程师", "经理", "专员", "分析师", "开发者", "开发", "运营", "产品", "数据"}
)


def _map_target_industry(value: str) -> str | None:
    text = (value or "").strip()
    if text in INDUSTRY_ORDER:
        return text
    for industry_id in INDUSTRY_ORDER:
        label = INDUSTRY_LABELS[industry_id]
        if text == label or label in text:
            return industry_id
    for keyword, industry_id in MARKET_INDUSTRY_MAP.items():
        if keyword in text:
            return industry_id
    return None


def _role_terms(target_role: str, desired_direction: str) -> list[str]:
    terms = []
    for value in (target_role, desired_direction):
        text = (value or "").strip()
        if len(text) >= 2 and text not in GENERIC_ROLE_TERMS:
            terms.append(text)
        base = text
        for suffix in ("工程师", "分析师", "经理", "专员", "开发者", "师"):
            if base.endswith(suffix):
                base = base[: -len(suffix)].strip()
                break
        if len(base) >= 2 and base not in GENERIC_ROLE_TERMS and base not in terms:
            terms.append(base)
    return terms


def _timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _profile_skill_names(profile_data: dict[str, Any] | None) -> list[str]:
    return [
        str(item.get("name") or "").strip()
        for item in (profile_data or {}).get("skills", [])
        if str(item.get("name") or "").strip()
    ]


def match_article(
    item: dict[str, Any],
    *,
    target_industry_id: str | None,
    target_industry_label: str,
    role_terms: list[str],
    target_location: str,
    profile_skills: list[str],
) -> tuple[int, list[str], list[str]]:
    text = f"{item.get('title') or ''}\n{item.get('summary') or ''}".lower()
    industries = list(item.get("industries") or [])
    reasons: list[str] = []
    types: list[str] = []
    score = 0

    if target_industry_id and target_industry_id in industries:
        score += 4
        types.append("target_industry")
        reasons.append(
            f"匹配你的目标行业「{target_industry_label}」；文章行业标签直接包含该行业。"
        )

    role_hit = next((term for term in role_terms if term.lower() in text), None)
    if role_hit:
        score += 3
        types.append("role")
        reasons.append(
            f"与目标岗位方向「{role_hit}」相关；标题或摘要包含该方向词。"
        )

    if target_industry_id:
        for industry in industries:
            keywords = CROSS_INDUSTRY_KEYWORDS.get(
                (target_industry_id, industry)
            ) or CROSS_INDUSTRY_KEYWORDS.get((industry, target_industry_id))
            if not keywords:
                continue
            matched_keywords = [
                keyword for keyword in keywords if keyword.lower() in text
            ]
            if not matched_keywords:
                continue
            note = " / ".join(matched_keywords[:2])
            score += 2
            types.append("cross_industry")
            reasons.append(
                f"文章行业「{INDUSTRY_LABELS.get(industry, industry)}」与你的目标行业"
                f"「{target_industry_label}」存在明确交叉（{note}）；仅为行业关联，"
                "不代表文章涉及你的具体技能。"
            )
            break

    skill_hits = [
        skill
        for skill in profile_skills
        if len(skill) >= 2 and skill.lower() in text
    ]
    if skill_hits:
        score += min(2, len(skill_hits))
        types.append("skill")
        reasons.append(
            "标题或摘要出现你已记录的技能"
            f"「{'、'.join(skill_hits[:3])}」；资料记录不等于能力验证。"
        )

    if target_location and target_location.lower() in text:
        score += 1
        types.append("region")
        reasons.append(f"标题或摘要提到目标地区「{target_location}」。")

    return score, reasons, types


def profile_context(profile_data: dict[str, Any] | None) -> dict[str, Any]:
    data = profile_data or {}
    basic = data.get("basic") or {}
    goals = data.get("goals") or {}
    target_role = str(goals.get("target_role") or "").strip()
    target_industry = str(goals.get("target_industry") or "").strip()
    desired_direction = str(goals.get("desired_direction") or "").strip()
    target_location = str(basic.get("location") or "").strip()
    skills = _profile_skill_names(data)
    target_industry_id = _map_target_industry(target_industry)
    target_industry_label = (
        INDUSTRY_LABELS.get(target_industry_id, target_industry)
        if target_industry_id
        else target_industry
    )
    missing = []
    if not target_role:
        missing.append("目标岗位")
    if not target_industry:
        missing.append("目标行业")
    if not target_location:
        missing.append("目标地区")
    if not skills:
        missing.append("已记录技能")
    return {
        "target_role": target_role,
        "target_industry": target_industry,
        "target_industry_id": target_industry_id,
        "target_industry_label": target_industry_label,
        "desired_direction": desired_direction,
        "target_location": target_location,
        "skills": skills,
        "missing": missing,
        "sufficient": bool(target_role or target_industry),
        "role_terms": _role_terms(target_role, desired_direction),
    }


def rank_personal_items(
    items: list[dict[str, Any]],
    profile_data: dict[str, Any] | None,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int, dict[str, Any], str]:
    context = profile_context(profile_data)
    if not context["sufficient"]:
        reason = (
            "当前 Profile 缺少目标岗位或目标行业，无法判断哪些新闻与你有关。"
            "请先在 Profile 中补充目标方向；系统不会凭空空泛推荐。"
        )
        return [], 0, context, reason

    ranked = []
    seen: set[str] = set()
    for item in items:
        article_id = str(item.get("id") or "")
        if article_id and article_id in seen:
            continue
        if article_id:
            seen.add(article_id)
        score, reasons, types = match_article(
            item,
            target_industry_id=context["target_industry_id"],
            target_industry_label=context["target_industry_label"],
            role_terms=context["role_terms"],
            target_location=context["target_location"],
            profile_skills=context["skills"],
        )
        if score <= 0 or not any(
            match_type in {"target_industry", "role", "cross_industry"}
            for match_type in types
        ):
            continue
        enriched = dict(item)
        enriched["match_reasons"] = reasons
        enriched["match_types"] = types
        ranked.append((score, _timestamp(item.get("published_at")), enriched))

    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    total = len(ranked)
    page = [row[2] for row in ranked[offset : offset + limit]]
    if not total:
        reason = (
            "当前筛选下没有与你的目标行业或目标岗位形成可解释关联的新闻。"
            "系统没有用其他新闻或宽泛关键词凑数。"
        )
    else:
        reason = ""
    return page, total, context, reason