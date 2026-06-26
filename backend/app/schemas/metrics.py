"""Schemas Pydantic para metricas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobOut
from app.schemas.post import PostOut


class MetricsTodayBlock(BaseModel):
    new_jobs: int = 0
    jobs_above_70: int = 0
    applications_prepared: int = 0
    persons_to_connect: int = 0
    post_scheduled: PostOut | None = None


class ApiCost(BaseModel):
    today: float = 0.0
    month: float = 0.0


class MetricsToday(BaseModel):
    today: MetricsTodayBlock
    api_cost_eur: ApiCost = Field(default_factory=ApiCost)


class MetricsPipeline(BaseModel):
    pipeline: dict[str, list[JobOut]]


class CompanyMetric(BaseModel):
    name: str
    jobs_count: int
    avg_score: float
    best_match: JobOut | None = None


class MetricsCompanies(BaseModel):
    companies: list[CompanyMetric]


class ApiCostAggregate(BaseModel):
    bucket: str  # provider, day, tier
    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cost_eur: float


class ApiCostsResponse(BaseModel):
    since: str
    until: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cached_input_tokens: int
    total_cost_eur: float
    by_provider: list[ApiCostAggregate]
    by_tier: list[ApiCostAggregate]
    by_day: list[ApiCostAggregate]
