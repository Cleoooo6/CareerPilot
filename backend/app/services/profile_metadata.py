from datetime import date
from typing import Any


def today_str() -> str:
    return date.today().isoformat()


def _skill_signature(skill: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(skill.get("name") or "").strip(),
        str(skill.get("proficiency") or "").strip(),
        str(skill.get("evidence") or "").strip(),
        str(skill.get("category") or "").strip(),
    )


def prepare_manual_skills(
    existing: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    old_skills = {
        str(item["id"]): item
        for item in (existing or {}).get("skills", [])
        if item.get("id")
    }
    for skill in incoming.get("skills", []):
        skill_id = str(skill.get("id") or "")
        old = old_skills.get(skill_id)
        changed = old is None or _skill_signature(old) != _skill_signature(skill)
        if old is None:
            skill["source"] = str(skill.get("source") or "manual")
        elif not str(skill.get("source") or "").strip():
            skill["source"] = str(old.get("source") or "")
        skill["verification"] = "confirmed"
        if changed:
            skill["updated_at"] = today_str()
        elif old is not None:
            skill["updated_at"] = str(old.get("updated_at") or "")
    return incoming


def mark_resume_skills(incoming: dict[str, Any]) -> dict[str, Any]:
    for skill in incoming.get("skills", []):
        skill["source"] = "resume"
        skill["verification"] = "confirmed"
        skill["updated_at"] = today_str()
    return incoming
