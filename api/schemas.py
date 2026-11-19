"""Typed request/response models for the API (drive the OpenAPI schema)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pipeline.schemas import SignalType, SourceType
from pydantic import BaseModel, Field

T = TypeVar("T")


# ------------------------------- envelopes -------------------------------- #
class Page(BaseModel, Generic[T]):
    """Standard paginated envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorBody(BaseModel):
    type: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


# ------------------------------ competitors ------------------------------- #
class TrackedURLModel(BaseModel):
    url: str
    source_type: SourceType = SourceType.STATIC
    signal_hint: SignalType | None = None


class CompetitorBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = None
    industry: str | None = None
    tier: int = Field(default=2, ge=1, le=3)
    tracked_urls: list[TrackedURLModel] = Field(default_factory=list)


class CompetitorCreate(CompetitorBase):
    id: str | None = Field(default=None, description="Slug; derived from name if omitted.")


class CompetitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain: str | None = None
    industry: str | None = None
    tier: int | None = Field(default=None, ge=1, le=3)
    tracked_urls: list[TrackedURLModel] | None = None


class Competitor(CompetitorBase):
    id: str
    tracked_url_count: int = 0
    signal_count: int = 0
    high_significance_count: int = 0
    last_signal_at: datetime | None = None


# -------------------------------- signals --------------------------------- #
class Signal(BaseModel):
    signal_id: str
    competitor_id: str
    url: str | None = None
    signal_type: SignalType
    title: str | None = None
    summary: str | None = None
    entities: list[str] = Field(default_factory=list)
    significance: int | None = None
    confidence: float | None = None
    extracted_at: datetime | None = None


# -------------------------------- changes --------------------------------- #
class Change(BaseModel):
    change_id: str
    competitor_id: str
    url: str | None = None
    change_type: str
    signal_type: SignalType | None = None
    title: str | None = None
    summary: str | None = None
    significance_score: int | None = None
    weighted_significance: int | None = None
    confidence: float | None = None
    detected_at: datetime | None = None


# ------------------------------- analytics -------------------------------- #
class PricingPoint(BaseModel):
    competitor_id: str
    plan: str
    price: float
    currency: str | None = None
    captured_at: datetime | None = None


class HiringRow(BaseModel):
    competitor_id: str
    role: str
    location: str | None = None
    posted_at: datetime | None = None
    removed_at: datetime | None = None


class CadencePoint(BaseModel):
    week: date
    count: int


class TrendPoint(BaseModel):
    week: date
    total_changes: int
    high_significance_changes: int


class TypeCount(BaseModel):
    signal_type: SignalType
    count: int


class OverviewStats(BaseModel):
    competitors_tracked: int
    signals_total: int
    signals_this_week: int
    high_significance_count: int
    active_alerts: int
    changes_this_week: int
    by_type: list[TypeCount]
    weekly_trend: list[TrendPoint]


# -------------------------------- reports --------------------------------- #
class ReportSummary(BaseModel):
    id: str
    title: str
    week_start: date | None = None
    summary: str | None = None
    created_at: datetime | None = None


class Report(ReportSummary):
    body_md: str | None = None


# -------------------------------- pipeline -------------------------------- #
class PipelineRunRequest(BaseModel):
    provider: str | None = Field(default=None, description="Override LLM provider.")
    limit: int = Field(default=0, ge=0, description="Max candidates to extract (0 = all).")


class PipelineRunResponse(BaseModel):
    status: str
    detail: str


# -------------------------------- research -------------------------------- #
ResearchStatus = Literal["queued", "running", "completed", "partial", "failed"]
SourcePreference = Literal[
    "official_company", "government", "tenders", "regulatory", "news", "industry"
]
TimeWindow = Literal["1m", "3m", "6m", "12m"]


class ResearchCreate(BaseModel):
    objective: str = Field(min_length=10, max_length=1200)
    industry: str | None = Field(default=None, max_length=120)
    geography: str = Field(default="India", max_length=80)
    time_window: TimeWindow = "6m"
    companies: list[str] = Field(default_factory=list, max_length=12)
    source_preferences: list[SourcePreference] = Field(default_factory=list)


class ResearchRunSummary(BaseModel):
    id: str
    objective: str
    industry: str | None = None
    geography: str | None = None
    time_window: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    companies: list[str] = Field(default_factory=list)
    source_preferences: list[str] = Field(default_factory=list)
    status: ResearchStatus
    provider: str
    is_demo: bool = False
    provider_request_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    source_count: int = 0
    finding_count: int = 0


class ResearchReport(BaseModel):
    executive_summary: str | None = None
    industry_overview: str | None = None
    market_trends: list[str] = Field(default_factory=list)
    company_developments: list[str] = Field(default_factory=list)
    product_launches: list[str] = Field(default_factory=list)
    manufacturing_expansion: list[str] = Field(default_factory=list)
    partnerships_and_investment: list[str] = Field(default_factory=list)
    policy_and_regulatory: list[str] = Field(default_factory=list)
    tenders_and_procurement: list[str] = Field(default_factory=list)
    commercial_opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class ResearchRun(ResearchRunSummary):
    result: ResearchReport | None = None


class ResearchSource(BaseModel):
    id: str
    research_run_id: str
    url: str
    domain: str | None = None
    title: str | None = None
    source_type: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    snippet: str | None = None


class ResearchFinding(BaseModel):
    id: str
    research_run_id: str
    title: str
    category: str
    entity: str | None = None
    industry: str | None = None
    summary: str | None = None
    significance: int | None = None
    confidence: float | None = None
    kind: Literal["verified_fact", "analysis"]
    event_date: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class FeedFinding(ResearchFinding):
    run_objective: str | None = None
    is_demo: bool = False
    provider: str | None = None


class CategoryCount(BaseModel):
    category: str
    count: int


class ResearchConfig(BaseModel):
    provider: str
    live_available: bool
    mode: str
