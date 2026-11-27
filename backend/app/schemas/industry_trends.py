from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.industry_pulse import IndustryFilter, IndustryId

TrendDirection = Literal["rising", "stable", "cooling", "unclear", "insufficient"]
EvidenceLevel = Literal["strong", "medium", "insufficient"]
TrendBasis = Literal["market_news", "market", "news", "insufficient"]
PersonalMatch = Literal["high", "medium", "low"]


class IndustryCatalogItem(BaseModel):
    id: IndustryId
    label: str


class TrendMonthCount(BaseModel):
    period: str
    count: int


class TrendCountItem(BaseModel):
    name: str
    count: int


class TrendSkillItem(BaseModel):
    skill: str
    count: int
    share: float


class TrendNewsItem(BaseModel):
    id: str
    title: str
    source: str
    published_at: datetime | None
    url: str


class TrendEvidence(BaseModel):
    news_count: int
    news_source_count: int
    news_period_start: datetime | None
    news_period_end: datetime | None
    news_span_days: int
    news_examples: list[TrendNewsItem] = Field(default_factory=list)
    job_count: int
    job_month_count: int
    job_period_start: datetime | None
    job_period_end: datetime | None
    job_months: list[TrendMonthCount] = Field(default_factory=list)
    roles: list[TrendCountItem] = Field(default_factory=list)
    skills: list[TrendSkillItem] = Field(default_factory=list)
    locations: list[TrendCountItem] = Field(default_factory=list)
    education: list[TrendCountItem] = Field(default_factory=list)
    experience: list[TrendCountItem] = Field(default_factory=list)
    dataset_kinds: list[str] = Field(default_factory=list)
    synthetic: bool = False
    sources: list[str] = Field(default_factory=list)


class IndustryTrendItem(BaseModel):
    industry_id: IndustryId
    label: str
    title: str
    summary: str
    direction: TrendDirection
    confidence: Literal["high", "medium", "low"]
    evidence_level: EvidenceLevel
    basis: TrendBasis
    period_start: datetime | None
    period_end: datetime | None
    news_count: int
    news_source_count: int
    job_count: int
    roles: list[TrendCountItem] = Field(default_factory=list)
    skills: list[TrendSkillItem] = Field(default_factory=list)
    locations: list[TrendCountItem] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    evidence: TrendEvidence


class InsufficientIndustry(BaseModel):
    industry_id: IndustryId
    label: str
    reason: str
    news_count: int
    job_count: int


class IndustryTrendsOut(BaseModel):
    generated_at: datetime
    months: int
    industry_filter: IndustryFilter
    items: list[IndustryTrendItem]
    insufficient_industries: list[InsufficientIndustry]
    warnings: list[str]
    industry_catalog: list[IndustryCatalogItem]


class RoadmapTrendSuggestion(BaseModel):
    reason: str
    suggested_skills: list[str] = Field(default_factory=list)
    deprioritize_skills: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    confirm_url: str = "/roadmap"


class PersonalSkillGap(BaseModel):
    name: str
    count: int
    share: float
    recorded: bool
    evidence_note: str


class PersonalTrendItem(BaseModel):
    trend: IndustryTrendItem
    relevance_confidence: PersonalMatch
    why_relevant: list[str] = Field(default_factory=list)
    matched_goals: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[PersonalSkillGap] = Field(default_factory=list)
    affected_roles: list[TrendCountItem] = Field(default_factory=list)
    impact: str
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    roadmap_suggestion: RoadmapTrendSuggestion
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class PersonalIndustryTrendsOut(BaseModel):
    generated_at: datetime
    months: int
    profile_sufficient: bool
    profile_missing: list[str] = Field(default_factory=list)
    target_role: str = ""
    target_industry: str = ""
    target_industry_label: str = ""
    target_location: str = ""
    items: list[PersonalTrendItem]
    insufficient_reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    industry_catalog: list[IndustryCatalogItem]
