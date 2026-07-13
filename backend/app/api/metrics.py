"""Endpoints de metricas."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.api_call import ApiCall
from app.models.job import Job
from app.models.person import Person
from app.models.post import Post
from app.schemas.job import JobOut
from app.schemas.metrics import (
    ApiCost,
    ApiCostAggregate,
    ApiCostsResponse,
    CompanyMetric,
    MetricsCompanies,
    MetricsPipeline,
    MetricsToday,
    MetricsTodayBlock,
)
from app.schemas.post import PostOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/today", response_model=MetricsToday)
def today_metrics(db: Session = Depends(get_db)) -> MetricsToday:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    new_jobs = db.execute(
        select(func.count(Job.id)).where(Job.created_at >= today_start)
    ).scalar() or 0
    jobs_above_70 = db.execute(
        select(func.count(Job.id)).where(Job.match_score >= 70, Job.status == "detected")
    ).scalar() or 0
    applications_prepared = db.execute(
        select(func.count(Job.id)).where(Job.status == "prepared")
    ).scalar() or 0
    persons_to_connect = db.execute(
        select(func.count(Person.id)).where(Person.status.in_(["pending", "queued"]))
    ).scalar() or 0

    next_post = db.execute(
        select(Post)
        .where(Post.status == "scheduled", Post.scheduled_at >= datetime.utcnow())
        .order_by(Post.scheduled_at)
        .limit(1)
    ).scalar_one_or_none()

    # Coste API agregado desde api_calls
    month_start = today_start.replace(day=1)
    cost_today = db.execute(
        select(func.coalesce(func.sum(ApiCall.cost_eur), 0.0)).where(
            ApiCall.created_at >= today_start
        )
    ).scalar() or 0.0
    cost_month = db.execute(
        select(func.coalesce(func.sum(ApiCall.cost_eur), 0.0)).where(
            ApiCall.created_at >= month_start
        )
    ).scalar() or 0.0

    return MetricsToday(
        today=MetricsTodayBlock(
            new_jobs=int(new_jobs),
            jobs_above_70=int(jobs_above_70),
            applications_prepared=int(applications_prepared),
            persons_to_connect=int(persons_to_connect),
            post_scheduled=PostOut.model_validate(next_post) if next_post else None,
        ),
        api_cost_eur=ApiCost(today=float(cost_today), month=float(cost_month)),
    )


# Máximo de tarjetas por columna del Kanban. Evita traer toda la tabla pero
# aplica el límite POR estado, así ninguna columna desaparece cuando hay
# muchos jobs (antes un límite global de 500 ordenado por score borraba los
# jobs de baja puntuación ya movidos a applied/rejected/etc.).
_MAX_PER_STATUS = 300


@router.get("/pipeline", response_model=MetricsPipeline)
def pipeline_metrics(db: Session = Depends(get_db)) -> MetricsPipeline:
    statuses = ["detected", "prepared", "applied", "interviewing", "offer", "rejected", "ghosted"]
    bucket: dict[str, list[JobOut]] = {s: [] for s in statuses}

    for status in statuses:
        jobs = db.execute(
            select(Job)
            .where(Job.status == status)
            .order_by(desc(Job.match_score))
            .limit(_MAX_PER_STATUS)
        ).scalars().all()
        bucket[status] = [JobOut.model_validate(j) for j in jobs]
    return MetricsPipeline(pipeline=bucket)


@router.get("/companies", response_model=MetricsCompanies)
def companies_metrics(db: Session = Depends(get_db)) -> MetricsCompanies:
    rows = (
        db.execute(
            select(Job.company, func.count(Job.id), func.avg(Job.match_score))
            .group_by(Job.company)
            .order_by(desc(func.avg(Job.match_score)))
            .limit(30)
        )
    ).all()

    names = [name for name, _count, _avg in rows]

    # Un único SELECT para todos los jobs de esas empresas (ordenado por score);
    # elegimos el mejor por empresa en memoria en vez de 1 query por empresa (N+1).
    best_by_company: dict[str, Job] = {}
    if names:
        candidates = db.execute(
            select(Job).where(Job.company.in_(names)).order_by(desc(Job.match_score))
        ).scalars().all()
        for j in candidates:
            if j.company not in best_by_company:
                best_by_company[j.company] = j

    out: list[CompanyMetric] = []
    for name, count, avg in rows:
        best = best_by_company.get(name)
        out.append(
            CompanyMetric(
                name=name,
                jobs_count=int(count),
                avg_score=float(avg or 0.0),
                best_match=JobOut.model_validate(best) if best else None,
            )
        )
    return MetricsCompanies(companies=out)


@router.get("/api-costs", response_model=ApiCostsResponse)
def api_costs(
    since: datetime | None = Query(default=None, description="ISO datetime. Default: 30 dias atras"),
    until: datetime | None = Query(default=None, description="ISO datetime. Default: ahora"),
    db: Session = Depends(get_db),
) -> ApiCostsResponse:
    """Agrega coste de llamadas LLM por provider, tier y dia."""
    until = until or datetime.utcnow()
    since = since or (until - timedelta(days=30))

    base_filter = (ApiCall.created_at >= since, ApiCall.created_at <= until)

    # Totales
    totals = db.execute(
        select(
            func.coalesce(func.count(ApiCall.id), 0),
            func.coalesce(func.sum(ApiCall.input_tokens), 0),
            func.coalesce(func.sum(ApiCall.output_tokens), 0),
            func.coalesce(func.sum(ApiCall.cached_input_tokens), 0),
            func.coalesce(func.sum(ApiCall.cost_eur), 0.0),
        ).where(*base_filter)
    ).one()

    def _aggregate(group_col, bucket_name: str) -> list[ApiCostAggregate]:
        rows = db.execute(
            select(
                group_col,
                func.count(ApiCall.id),
                func.coalesce(func.sum(ApiCall.input_tokens), 0),
                func.coalesce(func.sum(ApiCall.output_tokens), 0),
                func.coalesce(func.sum(ApiCall.cached_input_tokens), 0),
                func.coalesce(func.sum(ApiCall.cost_eur), 0.0),
            )
            .where(*base_filter)
            .group_by(group_col)
            .order_by(desc(func.sum(ApiCall.cost_eur)))
        ).all()
        return [
            ApiCostAggregate(
                bucket=bucket_name,
                key=str(key) if key is not None else "unknown",
                calls=int(c),
                input_tokens=int(it),
                output_tokens=int(ot),
                cached_input_tokens=int(ct),
                cost_eur=float(cost),
            )
            for key, c, it, ot, ct, cost in rows
        ]

    by_provider = _aggregate(ApiCall.provider, "provider")
    by_tier = _aggregate(ApiCall.tier, "tier")
    by_day = _aggregate(func.date(ApiCall.created_at), "day")

    return ApiCostsResponse(
        since=since.isoformat(),
        until=until.isoformat(),
        total_calls=int(totals[0]),
        total_input_tokens=int(totals[1]),
        total_output_tokens=int(totals[2]),
        total_cached_input_tokens=int(totals[3]),
        total_cost_eur=float(totals[4]),
        by_provider=by_provider,
        by_tier=by_tier,
        by_day=by_day,
    )
