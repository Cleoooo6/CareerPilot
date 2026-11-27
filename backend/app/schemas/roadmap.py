from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.market import MarketMeta

Priority = Literal["high", "medium", "low"]
TaskStatus = Literal["pending", "in_progress", "completed", "abandoned"]
TaskType = Literal["learning", "practice", "review"]
RoadmapStatus = Literal["draft", "active", "archived", "discarded"]
GapBasis = Literal["market", "general"]


class RoadmapTaskLLM(BaseModel):
    title: str = Field(min_length=4, max_length=300)
    description: str = Field(default="", max_length=2000)
    task_type: TaskType = "learning"
    priority: Priority = "medium"
    estimated_time: str = Field(default="", max_length=100)
    acceptance_criteria: str = Field(min_length=6, max_length=1000)

    @field_validator("title", "acceptance_criteria", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoadmapStageLLM(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    goal: str = Field(default="", max_length=1000)
    duration: str = Field(default="", max_length=100)
    priority: Priority = "medium"
    tasks: list[RoadmapTaskLLM] = Field(min_length=1, max_length=8)

    @field_validator("title", "goal", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoadmapDraftLLM(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    summary: str = Field(default="", max_length=2000)
    stages: list[RoadmapStageLLM] = Field(min_length=1, max_length=6)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_shape(self):
        task_total = sum(len(stage.tasks) for stage in self.stages)
        if task_total < 2:
            raise ValueError("路线至少包含 2 个可执行任务")
        if task_total > 30:
            raise ValueError("路线任务不能超过 30 个")
        stage_titles = [stage.title.strip().lower() for stage in self.stages]
        if len(set(stage_titles)) != len(stage_titles):
            raise ValueError("阶段标题不能重复")
        task_titles = [
            task.title.strip().lower()
            for stage in self.stages
            for task in stage.tasks
        ]
        if len(set(task_titles)) != len(task_titles):
            raise ValueError("任务标题不能重复")
        return self


class SkillGapItem(BaseModel):
    name: str
    market_count: int
    market_share: float
    priority: Priority
    reason: str


class SkillGapProfileSkill(BaseModel):
    name: str
    proficiency: str
    evidence: str
    source: str
    verification: str


class SkillGapOut(BaseModel):
    target_role: str
    basis: GapBasis
    reference_only: bool = False
    matched: list[SkillGapItem]
    to_improve: list[SkillGapItem]
    not_recorded: list[SkillGapItem]
    profile_skills: list[SkillGapProfileSkill]
    meta: MarketMeta
    warnings: list[str]
    computed_at: datetime


class RoadmapTaskOut(BaseModel):
    id: UUID
    stage_id: UUID
    position: int
    title: str
    description: str
    task_type: TaskType
    priority: Priority
    estimated_time: str
    acceptance_criteria: str
    status: TaskStatus
    completed_at: datetime | None
    outcome: str
    created_at: datetime
    updated_at: datetime


class RoadmapStageOut(BaseModel):
    id: UUID
    position: int
    title: str
    goal: str
    duration: str
    priority: Priority
    tasks: list[RoadmapTaskOut]


class RoadmapOut(BaseModel):
    id: UUID
    user_id: UUID
    target_role: str
    status: RoadmapStatus
    version: int
    title: str
    summary: str
    gap: SkillGapOut | None = None
    generation_mode: Literal["mock", "real"]
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    stages: list[RoadmapStageOut]
    task_total: int
    task_completed: int
    stale: bool | None = None
    stale_reason: str | None = None


class RoadmapSummaryOut(BaseModel):
    id: UUID
    target_role: str
    status: RoadmapStatus
    version: int
    title: str
    generation_mode: Literal["mock", "real"]
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    task_total: int
    task_completed: int


class RoadmapStateOut(BaseModel):
    roadmap: RoadmapOut | None


class RoadmapSummaryListOut(BaseModel):
    items: list[RoadmapSummaryOut]


class RoadmapGenerateRequest(BaseModel):
    target_role: str | None = Field(default=None, max_length=200)
    regenerate: bool = False


class RoadmapTaskUpdateRequest(BaseModel):
    status: TaskStatus
    outcome: str | None = Field(default=None, max_length=4000)


class RoadmapTaskUpdateOut(BaseModel):
    task: RoadmapTaskOut
    roadmap_id: UUID
    roadmap_version: int
