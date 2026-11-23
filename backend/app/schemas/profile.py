from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _item_id() -> str:
    return uuid4().hex


def _normalize_items(value, *, string_field: str) -> list[dict]:
    if value in (None, ""):
        return []
    if isinstance(value, BaseModel):
        return [value]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        return [{string_field: value}]
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, (dict, BaseModel)):
            normalized.append(item)
        elif isinstance(item, str) and item.strip():
            normalized.append({string_field: item})
    return normalized


class BasicInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", max_length=100)
    education_level: str = Field(default="", max_length=50)
    major: str = Field(default="", max_length=100)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    location: str = Field(default="", max_length=100)

    @field_validator("graduation_year", mode="before")
    @classmethod
    def normalize_year(cls, value):
        if value in (None, ""):
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())[:4]
        return int(digits) if digits else None


class CareerGoals(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_role: str = Field(default="", max_length=200)
    target_industry: str = Field(default="", max_length=200)
    job_status: str = Field(default="", max_length=50)
    desired_direction: str = Field(default="", max_length=500)


class SkillItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_item_id)
    name: str = Field(default="", max_length=100)
    proficiency: str = Field(default="", max_length=30)
    evidence: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=50)
    source: str = Field(default="", max_length=20)
    verification: str = Field(default="", max_length=20)
    updated_at: str = Field(default="", max_length=20)


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_item_id)
    school: str = Field(default="", max_length=150)
    degree: str = Field(default="", max_length=50)
    major: str = Field(default="", max_length=100)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=1000)


class ProjectItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_item_id)
    name: str = Field(default="", max_length=150)
    role: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)
    tech_stack: str = Field(default="", max_length=500)
    achievements: str = Field(default="", max_length=1000)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_item_id)
    company: str = Field(default="", max_length=150)
    position: str = Field(default="", max_length=100)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=2000)


class ProfileData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    basic: BasicInfo = Field(default_factory=BasicInfo)
    goals: CareerGoals = Field(default_factory=CareerGoals)
    skills: list[SkillItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)

    @field_validator("basic", mode="before")
    @classmethod
    def normalize_basic(cls, value):
        return value if isinstance(value, (dict, BasicInfo)) else {}

    @field_validator("goals", mode="before")
    @classmethod
    def normalize_goals(cls, value):
        return value if isinstance(value, (dict, CareerGoals)) else {}

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        return _normalize_items(value, string_field="name")

    @field_validator("education", mode="before")
    @classmethod
    def normalize_education(cls, value):
        return _normalize_items(value, string_field="school")

    @field_validator("projects", mode="before")
    @classmethod
    def normalize_projects(cls, value):
        return _normalize_items(value, string_field="name")

    @field_validator("experiences", mode="before")
    @classmethod
    def normalize_experiences(cls, value):
        return _normalize_items(value, string_field="company")


class ProfileSaveRequest(BaseModel):
    data: ProfileData


class ProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    data: ProfileData
    created_at: datetime
    updated_at: datetime


class ProfileStateOut(BaseModel):
    profile: ProfileOut | None


SectionName = Literal["basic", "goals", "skills", "education", "projects", "experiences"]
ALL_SECTIONS: tuple[SectionName, ...] = (
    "basic",
    "goals",
    "skills",
    "education",
    "projects",
    "experiences",
)


class ResumeParseOut(BaseModel):
    id: UUID
    user_id: UUID
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    parse_mode: str
    provider: str
    model: str
    parsed_data: ProfileData
    text_length: int
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ResumeParseListOut(BaseModel):
    items: list[ResumeParseOut]


class ResumeUpdateRequest(BaseModel):
    parsed_data: ProfileData


class ResumeConfirmRequest(BaseModel):
    sections: list[SectionName] = Field(default_factory=lambda: list(ALL_SECTIONS))
    draft: ProfileData | None = None


ClaimBasis = Literal["fact", "inference", "suggestion"]
ClaimConfidence = Literal["high", "medium", "low"]


class AnalysisClaim(BaseModel):
    statement: str = Field(max_length=1000)
    basis: ClaimBasis
    confidence: ClaimConfidence


class ProfileFit(BaseModel):
    summary: str = Field(default="", max_length=1500)
    evidence: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class ProfileAnalysisResult(BaseModel):
    overview: str = Field(default="", max_length=2000)
    strengths: list[AnalysisClaim] = Field(default_factory=list)
    gaps: list[AnalysisClaim] = Field(default_factory=list)
    fit: ProfileFit = Field(default_factory=ProfileFit)
    directions: list[AnalysisClaim] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ProfileAnalysisOut(BaseModel):
    id: UUID
    user_id: UUID
    profile_id: UUID
    provider: str
    model: str
    llm_mode: str
    analysis: ProfileAnalysisResult
    created_at: datetime


class ProfileAnalysisListOut(BaseModel):
    items: list[ProfileAnalysisOut]

class ProfileRevisionOut(BaseModel):
    id: UUID
    user_id: UUID
    profile_id: UUID
    version: int
    change_source: str
    created_at: datetime


class ProfileRevisionDetailOut(ProfileRevisionOut):
    data: ProfileData


class ProfileRevisionListOut(BaseModel):
    items: list[ProfileRevisionOut]
