from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DatasetKind = Literal["real", "synthetic"]
DatasetFilter = Literal["all", "real", "synthetic"]
DistributionDimension = Literal["education", "experience", "location"]


class MarketSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: str = Field(default="manual_json", max_length=32)
    dataset_kind: DatasetKind
    license_note: str = Field(min_length=1, max_length=2000)
    base_url: str | None = Field(default=None, max_length=500)


class MarketJobIn(BaseModel):
    external_id: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=20000)
    education: str = Field(default="", max_length=100)
    experience: str = Field(default="", max_length=100)
    industry: str = Field(default="", max_length=100)
    salary: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=1000)
    posted_at: datetime | None = None


class MarketImportRequest(BaseModel):
    source: MarketSourceIn
    jobs: list[MarketJobIn] = Field(min_length=1, max_length=500)


class MarketSourceOut(BaseModel):
    name: str
    source_type: str
    dataset_kind: str
    license_note: str
    base_url: str | None


class MarketImportResult(BaseModel):
    batch_id: str
    source: MarketSourceOut
    total: int
    imported: int
    duplicates: int
    failed: int


class MarketCountItem(BaseModel):
    name: str
    count: int
    share: float


class SkillDemandItem(BaseModel):
    skill: str
    count: int
    share: float
    rank: int


class MarketMeta(BaseModel):
    sample_size: int
    sample_sufficient: bool
    period_start: datetime | None
    period_end: datetime | None
    updated_at: datetime | None
    dataset_kinds: list[str]
    sources: list[MarketSourceOut]
    warnings: list[str]


class MarketRoleSkill(BaseModel):
    role: str
    skills: list[SkillDemandItem]


class MarketOverviewOut(BaseModel):
    total_jobs: int
    total_companies: int
    total_roles: int
    total_locations: int
    top_roles: list[MarketCountItem]
    top_skills: list[SkillDemandItem]
    role_skills: list[MarketRoleSkill]
    meta: MarketMeta


class SkillDemandOut(BaseModel):
    items: list[SkillDemandItem]
    meta: MarketMeta


class DistributionOut(BaseModel):
    dimension: str
    items: list[MarketCountItem]
    meta: MarketMeta


class TrendPoint(BaseModel):
    period: str
    count: int


class TrendOut(BaseModel):
    points: list[TrendPoint]
    insufficient_data: bool
    meta: MarketMeta


class RolesOut(BaseModel):
    items: list[str]
    meta: MarketMeta


class SourcesOut(BaseModel):
    items: list[MarketSourceOut]
