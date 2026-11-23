from typing import Any

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_CHARS = 6000
MAX_MESSAGE_CHARS = 2000
PROFILE_INTENTS = frozenset(
    {"career_advice", "resume", "career_planning", "unknown"}
)


def build_history(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = MAX_CONTEXT_MESSAGES,
    max_chars: int = MAX_CONTEXT_CHARS,
    max_message_chars: int = MAX_MESSAGE_CHARS,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    total_chars = 0
    for message in reversed(messages):
        role = str(message.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        content = content[:max_message_chars]
        if total_chars + len(content) > max_chars:
            break
        selected.append({"role": role, "content": content})
        total_chars += len(content)
        if len(selected) >= max_messages:
            break
    selected.reverse()
    return selected


def format_history(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 4,
    max_chars: int = 2000,
) -> str:
    selected = build_history(
        messages,
        max_messages=max_messages,
        max_chars=max_chars,
        max_message_chars=600,
    )
    return "\n".join(
        f"{'用户' if item['role'] == 'user' else '助手'}：{item['content']}"
        for item in selected
    )


def usage_payload(usage: Any) -> dict[str, int | None] | None:
    if usage is None:
        return None
    data = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    if all(value is None for value in data.values()):
        return None
    return data

def should_use_profile(intent: str | None) -> bool:
    return (intent or "unknown") in PROFILE_INTENTS


def build_chat_profile_context(
    data: dict[str, Any] | None, *, max_chars: int = 1200
) -> str:
    if not data:
        return ""
    basic = data.get("basic") or {}
    goals = data.get("goals") or {}
    lines = []
    for label, value in (
        ("姓名", basic.get("name")),
        ("学历", basic.get("education_level")),
        ("专业", basic.get("major")),
        ("毕业时间", basic.get("graduation_year")),
        ("所在地", basic.get("location")),
        ("目标岗位", goals.get("target_role")),
        ("目标行业", goals.get("target_industry")),
        ("求职状态", goals.get("job_status")),
        ("期望方向", goals.get("desired_direction")),
    ):
        if value not in (None, ""):
            lines.append(f"{label}：{value}")
    skills = [
        f"{item.get('name', '')}({item.get('proficiency', '')})"
        for item in data.get("skills", [])
        if item.get("name")
    ]
    if skills:
        lines.append("技能：" + "、".join(skills[:8]))
    for key, label in (
        ("education", "教育"),
        ("projects", "项目"),
        ("experiences", "经历"),
    ):
        items = data.get(key) or []
        summaries = []
        for item in items[:2]:
            parts = [
                str(item.get(field) or "")
                for field in (
                    "school",
                    "degree",
                    "name",
                    "company",
                    "position",
                    "role",
                )
            ]
            summary = " / ".join(part for part in parts if part)
            if summary:
                summaries.append(summary[:120])
        if summaries:
            lines.append(f"{label}：" + "；".join(summaries))
    return "\n".join(lines)[:max_chars]
