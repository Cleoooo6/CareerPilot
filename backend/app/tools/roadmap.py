import asyncio
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.services.roadmap_service import get_roadmap_service
from app.tools.base import ToolError, ToolSpec
from app.tools.registry import get_tool_user_id


def _current_user_id() -> UUID:
    raw = get_tool_user_id()
    if not raw:
        raise ToolError("TOOL_CONTEXT_MISSING", "路线工具缺少用户上下文")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise ToolError("TOOL_CONTEXT_MISSING", "路线工具用户上下文非法") from exc


class SkillGapArgs(BaseModel):
    role: str | None = Field(default=None, max_length=200)


class RoadmapStateArgs(BaseModel):
    pass


class GenerateRoadmapArgs(BaseModel):
    target_role: str | None = Field(default=None, max_length=200)
    regenerate: bool = Field(
        default=False,
        description="仅在用户明确要求重新生成时设为 true；否则复用未变化的草稿",
    )


def _skill_gap(args: SkillGapArgs) -> dict[str, Any]:
    try:
        gap = asyncio.run(
            get_roadmap_service().gap_for_user(_current_user_id(), args.role)
        )
    except AppError as exc:
        raise ToolError(exc.code, exc.message) from exc
    return gap.model_dump(mode="json")


def _current_roadmap(args: RoadmapStateArgs) -> dict[str, Any]:
    return asyncio.run(get_roadmap_service().active_overview(_current_user_id()))


def _generate(args: GenerateRoadmapArgs) -> dict[str, Any]:
    try:
        roadmap, reused = asyncio.run(
            get_roadmap_service().generate_draft(
                _current_user_id(), args.target_role, args.regenerate
            )
        )
    except AppError as exc:
        raise ToolError(exc.code, exc.message) from exc
    message = (
        "已有待确认草稿且当前画像/市场输入未变化，已复用该草稿；"
        if reused
        else "草稿已生成；"
    ) + "正式启用需要用户在 My Roadmap 页面确认。"
    return {
        "draft_id": str(roadmap.id),
        "version": roadmap.version,
        "title": roadmap.title,
        "target_role": roadmap.target_role,
        "generation_mode": roadmap.generation_mode,
        "task_total": roadmap.task_total,
        "stages": [stage.title for stage in roadmap.stages],
        "reused": reused,
        "requires_confirmation": True,
        "message": message,
    }


SkillGapTool = ToolSpec(
    name="get_skill_gap",
    description=(
        "计算当前用户与目标岗位之间的技能差距：已具备、待提升、尚无记录，"
        "并返回市场样本量、数据性质和警告。没有记录不等于不具备。"
    ),
    args_schema=SkillGapArgs,
    handler=_skill_gap,
)

CurrentRoadmapTool = ToolSpec(
    name="get_roadmap",
    description=(
        "读取当前用户的正式成长路线（阶段、任务、完成进度）以及是否存在待确认草稿。"
        "只读，不修改路线。"
    ),
    args_schema=RoadmapStateArgs,
    handler=_current_roadmap,
)

GenerateRoadmapTool = ToolSpec(
    name="generate_roadmap_draft",
    description=(
        "基于已确认画像、技能差距和市场统计生成成长路线草稿；"
        "不会替换正式路线。默认在画像/市场输入未变化时复用现有待确认草稿；"
        "只有用户明确要求重新生成时才传 regenerate=true。"
        "草稿必须由用户在 My Roadmap 页面确认后才会启用。"
    ),
    args_schema=GenerateRoadmapArgs,
    handler=_generate,
)

ROADMAP_TOOLS = (
    SkillGapTool,
    CurrentRoadmapTool,
    GenerateRoadmapTool,
)

__all__ = [
    "CurrentRoadmapTool",
    "GenerateRoadmapTool",
    "ROADMAP_TOOLS",
    "SkillGapTool",
]
