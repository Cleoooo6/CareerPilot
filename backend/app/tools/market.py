from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.market_service import get_market_service
from app.tools.base import ToolError, ToolSpec


class MarketInsightsArgs(BaseModel):
    role: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=100)
    dataset_kind: Literal["all", "real", "synthetic"] = "all"


class SkillDemandArgs(BaseModel):
    role: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=12, ge=1, le=30)


class CareerMarketRequirementsArgs(BaseModel):
    role: str | None = Field(default=None, max_length=200)


def _insights(args: MarketInsightsArgs) -> dict[str, Any]:
    return get_market_service().get_market_insights(args.role, args.location)


def _skill_demand(args: SkillDemandArgs) -> dict[str, Any]:
    return get_market_service().get_skill_demand(args.role, args.limit)


def _requirements(args: CareerMarketRequirementsArgs) -> dict[str, Any]:
    return get_market_service().get_career_market_requirements(args.role)


MarketInsightsTool = ToolSpec(
    name="get_market_insights",
    description="读取 CareerPilot Market Radar 数据库中的岗位总览、角色与技能需求。结果包含样本量、来源、周期和警告，不包含实时互联网数据。",
    args_schema=MarketInsightsArgs,
    handler=_insights,
)

SkillDemandTool = ToolSpec(
    name="get_skill_demand",
    description="读取 Market Radar 数据库中的技能需求排名，必须结合样本量和来源解释，不得编造数字。",
    args_schema=SkillDemandArgs,
    handler=_skill_demand,
)

CareerMarketRequirementsTool = ToolSpec(
    name="get_career_market_requirements",
    description="读取 Market Radar 数据库中目标职业方向的技能、学历和经验要求分布；数据不足时返回警告。",
    args_schema=CareerMarketRequirementsArgs,
    handler=_requirements,
)

MARKET_TOOLS = (
    MarketInsightsTool,
    SkillDemandTool,
    CareerMarketRequirementsTool,
)

__all__ = [
    "CareerMarketRequirementsTool",
    "MARKET_TOOLS",
    "MarketInsightsTool",
    "SkillDemandTool",
    "ToolError",
]
