from datetime import datetime, timezone
from typing import Any, Literal

from app.schemas.market import SkillDemandItem, SkillDemandOut
from app.schemas.roadmap import SkillGapItem, SkillGapOut, SkillGapProfileSkill
from app.services.market_cleaner import normalize_skill
from app.services.market_service import MIN_SAMPLE

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
HIGH_SHARE = 0.3
MEDIUM_SHARE = 0.2
SOURCE_LABELS = {"manual": "手动录入", "resume": "简历导入"}


def _skill_key(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    normalized = normalize_skill(text)
    if normalized:
        return normalized.lower()
    lowered = text.lower()
    for suffix in ("3", "2", "开发", "编程"):
        if lowered.endswith(suffix):
            base = text[: -len(suffix)].strip()
            normalized = normalize_skill(base)
            if normalized:
                return normalized.lower()
    return lowered


def _profile_skills(
    profile_data: dict[str, Any] | None,
) -> list[SkillGapProfileSkill]:
    skills: list[SkillGapProfileSkill] = []
    for item in (profile_data or {}).get("skills", [])[:30]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        skills.append(
            SkillGapProfileSkill(
                name=name,
                proficiency=str(item.get("proficiency") or ""),
                evidence=str(item.get("evidence") or ""),
                source=str(item.get("source") or ""),
                verification=str(item.get("verification") or ""),
            )
        )
    return skills


def _reason(
    category: Literal["matched", "to_improve", "not_recorded"],
    demand: SkillDemandItem,
    sample_size: int,
    profile_skill: SkillGapProfileSkill | None = None,
) -> str:
    share = f"{demand.share * 100:.0f}%"
    base = f"市场样本 {sample_size} 条中 {demand.count} 条要求（{share}）"
    source = (
        SOURCE_LABELS.get(profile_skill.source, "来源未记录")
        if profile_skill is not None
        else "来源未记录"
    )
    if category == "matched":
        return (
            f"{base}；画像有记录（{source}），资料已确认且附有用户填写或简历导入的证据；"
            "资料确认不等于客观能力验证，当前未做客观验证。"
        )
    if category == "to_improve":
        return (
            f"{base}；画像有记录（{source}），但证据或资料确认不完整，"
            "不能视为已具备。"
        )
    return f"{base}；画像尚未记录。没有记录不等于不具备。"


def _priority(
    category: Literal["matched", "to_improve", "not_recorded"],
    demand: SkillDemandItem,
) -> Literal["high", "medium", "low"]:
    if category == "not_recorded":
        return "high" if demand.share >= HIGH_SHARE else "medium"
    if category == "to_improve":
        return "medium" if demand.share >= MEDIUM_SHARE else "low"
    return "low"


def _sort(items: list[SkillGapItem]) -> list[SkillGapItem]:
    return sorted(
        items,
        key=lambda item: (
            PRIORITY_RANK[item.priority],
            -item.market_share,
            item.name,
        ),
    )


def compute_skill_gap(
    *,
    profile_data: dict[str, Any] | None,
    target_role: str,
    demand: SkillDemandOut,
) -> SkillGapOut:
    profile_skills = _profile_skills(profile_data)
    by_key = {_skill_key(skill.name): skill for skill in profile_skills}
    matched: list[SkillGapItem] = []
    to_improve: list[SkillGapItem] = []
    not_recorded: list[SkillGapItem] = []
    warnings = list(demand.meta.warnings)

    basis: Literal["market", "general"] = "market"
    reference_only = 0 < demand.meta.sample_size < MIN_SAMPLE
    if demand.meta.sample_size == 0 or not demand.items:
        basis = "general"
        warnings.append(
            "当前目标方向没有可用的市场样本，以下不是市场统计；"
            "只能作为通用建议，生成路线前请自行核对"
        )
    else:
        for item in demand.items:
            skill = by_key.get(_skill_key(item.skill))
            if skill is None:
                category = "not_recorded"
                bucket = not_recorded
            elif not skill.evidence.strip() or skill.verification != "confirmed":
                category = "to_improve"
                bucket = to_improve
            else:
                category = "matched"
                bucket = matched
            bucket.append(
                SkillGapItem(
                    name=item.skill,
                    market_count=item.count,
                    market_share=item.share,
                    priority=_priority(category, item),
                    reason=_reason(
                        category, item, demand.meta.sample_size, skill
                    ),
                )
            )

    if reference_only:
        warnings.append(
            "样本量不足，当前统计仅作参考，不能作为充分市场依据；"
            "生成路线需要你确认后再启用"
        )
    if "synthetic" in demand.meta.dataset_kinds:
        warnings.append(
            "市场数据包含 synthetic 合成数据，仅用于链路验证，不能作为真实就业市场结论"
        )

    return SkillGapOut(
        target_role=target_role,
        basis=basis,
        reference_only=reference_only,
        matched=_sort(matched),
        to_improve=_sort(to_improve),
        not_recorded=_sort(not_recorded),
        profile_skills=profile_skills,
        meta=demand.meta,
        warnings=sorted(set(warnings)),
        computed_at=datetime.now(timezone.utc),
    )
