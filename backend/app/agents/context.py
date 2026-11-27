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

def build_chat_career_context(
    *,
    profile_context: str,
    resume: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    analysis_stale: bool = False,
    gap: dict[str, Any] | None = None,
    roadmap: dict[str, Any] | None = None,
    max_chars: int = 2600,
) -> str:
    """Assemble the user's confirmed career data for the advisor.

    Everything here comes from the current user's persisted records; the AI
    must treat it as reference data, not instructions.
    """
    lines: list[str] = []
    if profile_context:
        lines.append("【已确认职业画像】")
        lines.append(profile_context)

    if resume:
        parsed = resume.get("parsed_data") or {}
        basic = parsed.get("basic") or {}
        skills = [
            str(item.get("name") or "")
            for item in parsed.get("skills", [])
            if item.get("name")
        ]
        parts = []
        if basic.get("name"):
            parts.append(f"姓名：{basic.get('name')}")
        if skills:
            parts.append(f"技能 {len(skills)} 项（{'、'.join(skills[:8])}）")
        projects = len(parsed.get("projects") or [])
        experiences = len(parsed.get("experiences") or [])
        if projects:
            parts.append(f"项目 {projects} 个")
        if experiences:
            parts.append(f"工作/实习 {experiences} 段")
        if parts:
            lines.append("【已确认简历解析】" + "；".join(parts))

    if analysis:
        payload = analysis.get("analysis") or {}
        overview = str(payload.get("overview") or "").strip()
        strengths = [
            str(item.get("statement") or "").strip()
            for item in payload.get("strengths", [])[:3]
            if item.get("statement")
        ]
        gaps = [
            str(item.get("statement") or "").strip()
            for item in payload.get("gaps", [])[:3]
            if item.get("statement")
        ]
        if overview or strengths or gaps:
            header = "【最新 AI 职业分析"
            header += "（资料已更新，分析可能过期）】" if analysis_stale else "】"
            lines.append(header)
            if overview:
                lines.append(overview[:300])
            if strengths:
                lines.append("优势：" + "；".join(strengths)[:300])
            if gaps:
                lines.append("短板：" + "；".join(gaps)[:300])

    if gap:
        to_improve = [
            str(item.get("name") or "")
            for item in gap.get("to_improve", [])[:8]
            if item.get("name")
        ]
        not_recorded = [
            str(item.get("name") or "")
            for item in gap.get("not_recorded", [])[:8]
            if item.get("name")
        ]
        if to_improve or not_recorded:
            lines.append("【技能差距（Market Radar 数据驱动）】")
            if to_improve:
                lines.append("需提升：" + "、".join(to_improve))
            if not_recorded:
                lines.append("尚无记录：" + "、".join(not_recorded))

    if roadmap:
        stages = roadmap.get("stages") or []
        tasks = [
            task for stage in stages for task in (stage.get("tasks") or [])
        ]
        completed = [
            str(task.get("title") or "")
            for task in tasks
            if task.get("status") == "completed"
        ]
        pending = [
            str(task.get("title") or "")
            for task in tasks
            if task.get("status") in ("pending", "in_progress")
        ]
        lines.append(
            f"【当前正式路线】目标岗位：{roadmap.get('target_role') or '-'}；"
            f"任务 {len(tasks)} 个，已完成 {len(completed)} 个"
        )
        if completed:
            lines.append("已完成：" + "、".join(completed[:6]))
        if pending:
            lines.append("待推进：" + "、".join(pending[:6]))

    return "\n".join(lines)[:max_chars]
