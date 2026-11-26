from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

IndustryId = Literal[
    "digital_tech_comms",
    "finance_insurance",
    "manufacturing_industry",
    "energy_environment",
    "auto_smart_mobility",
    "transport_logistics",
    "health_life_sciences",
    "education_research",
    "agriculture_food",
    "consumer_retail_services",
    "real_estate_construction",
    "culture_media_content",
    "arts_design",
    "sports_industry",
    "tourism_hospitality_events",
    "enterprise_professional_services",
]
IndustryFilter = Literal[
    "all",
    "digital_tech_comms",
    "finance_insurance",
    "manufacturing_industry",
    "energy_environment",
    "auto_smart_mobility",
    "transport_logistics",
    "health_life_sciences",
    "education_research",
    "agriculture_food",
    "consumer_retail_services",
    "real_estate_construction",
    "culture_media_content",
    "arts_design",
    "sports_industry",
    "tourism_hospitality_events",
    "enterprise_professional_services",
]
RegionFilter = Literal["all", "CN", "INTL"]
ContentPolicy = Literal["feed_excerpt", "metadata_only", "blocked"]
RelevanceStatus = Literal[
    "industry_relevant", "macro_signal", "needs_review", "irrelevant"
]
AnalysisStatus = Literal["pending", "analyzed", "failed", "disabled"]


class IndustryPulseArticleOut(BaseModel):
    id: UUID
    source_id: UUID | None
    source_name: str
    source_url: str | None
    industry: IndustryId | None
    primary_industry: IndustryId | None
    industries: list[IndustryId]
    industry_labels: list[str]
    region: Literal["CN", "INTL"]
    content_policy: ContentPolicy
    relevance_status: RelevanceStatus
    classification_basis: dict[str, Any] = Field(default_factory=dict)
    legacy_industry: str | None = None
    taxonomy_version: int
    title: str
    url: str
    canonical_url: str
    summary: str
    published_at: datetime | None
    fetched_at: datetime
    ai_summary: str
    career_impact: str
    tags: list[str] = Field(default_factory=list)
    analysis_status: AnalysisStatus
    analysis_error: str
    analysis_details: dict[str, Any] = Field(default_factory=dict)
    analysis_model: str
    analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    match_reasons: list[str] = Field(default_factory=list)
    match_types: list[str] = Field(default_factory=list)


class IndustryPulseSourceOut(BaseModel):
    key: str
    name: str
    industry: IndustryId
    primary_industry_label: str
    industries: list[IndustryId]
    industry_labels: list[str]
    region: Literal["CN", "INTL"]
    feed_url: str
    homepage_url: str | None
    license_note: str
    content_policy: ContentPolicy
    enabled: bool
    blocked_reason: str
    last_status: Literal["never", "ok", "failed", "blocked"]
    last_error: str
    last_fetched_at: datetime | None
    legacy_industry: str | None = None
    taxonomy_version: int = 2


class IndustryCoverageOut(BaseModel):
    id: IndustryId
    label: str
    scope: str
    majors: list[str]
    source_count: int
    article_count: int


class IndustryPulseRunOut(BaseModel):
    id: UUID
    status: Literal["running", "succeeded", "partial", "failed"]
    started_at: datetime
    finished_at: datetime | None
    sources_total: int
    sources_ok: int
    sources_failed: int
    articles_fetched: int
    articles_inserted: int
    articles_duplicates: int
    articles_skipped_limit: int | None = None
    sources_skipped: int = 0
    stats_legacy: bool = False
    error_message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class IndustryPulseOut(BaseModel):
    items: list[IndustryPulseArticleOut]
    total: int
    limit: int
    offset: int
    industry: IndustryFilter
    region: RegionFilter
    industries: list[IndustryCoverageOut]
    industry_majors_note: str
    sources: list[IndustryPulseSourceOut]
    latest_run: IndustryPulseRunOut | None
    ai_enabled: bool
    llm_mode: str
    ai_unavailable_reason: str
    view: Literal["all", "personal"] = "all"
    profile_sufficient: bool = True
    profile_missing: list[str] = Field(default_factory=list)
    personalization_reason: str = ""
    personal_target_role: str = ""
    personal_target_industry: str = ""
    personal_target_location: str = ""


class IndustryPulseRefreshOut(BaseModel):
    run: IndustryPulseRunOut


class IndustryPulseAnalysisOut(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    event: str = Field(default="", max_length=1000)
    career_impact: str = Field(default="", max_length=1000)
    affected_roles: list[str] = Field(default_factory=list, max_length=10)
    keywords: list[str] = Field(default_factory=list, max_length=10)