"""Persistent career analysis API (profile content never accepted from remote URLs)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import JSON, select
from sqlalchemy.orm import Session

from app.career.analysis import fingerprint, request_analysis, run_analysis, serialize, snapshot
from app.career.sources import cached_sources, owner_urls, request_refresh, run_refresh
from app.db import get_db
from app.models.career_analysis import CareerAnalysis
from app.models.career_source import CareerSource, CareerSourceRefresh
from app.profile_store import read_profile

router = APIRouter(prefix="/career", tags=["career"])


@router.get("/analyses/latest")
def latest(db: Session = Depends(get_db)) -> dict:
    profile = read_profile()
    digest = fingerprint(snapshot(profile, cached_sources(db, profile)))
    current = db.scalar(select(CareerAnalysis).where(CareerAnalysis.source_hash == digest))
    latest_row = db.scalar(select(CareerAnalysis).order_by(CareerAnalysis.id.desc()))
    completed = db.scalar(select(CareerAnalysis).where(CareerAnalysis.result.is_not(None), CareerAnalysis.result != JSON.NULL)
                          .order_by(CareerAnalysis.finished_at.desc(), CareerAnalysis.id.desc()))
    row = current or latest_row
    return {"analysis": serialize(row), "last_completed": serialize(completed),
            "current_source_hash": digest, "stale": row is not None and row.source_hash != digest}


@router.post("/analyses")
def create(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    refresh_run = db.get(CareerSourceRefresh, 1)
    if refresh_run and refresh_run.status == "running":
        raise HTTPException(status_code=409, detail="Espera a que termine la actualización de fuentes antes de analizar.")
    try:
        row, reused = request_analysis(db, read_profile())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not reused:
        background_tasks.add_task(run_analysis, row.id)
    return {"analysis": serialize(row), "reused": reused}


@router.get("/analyses/{analysis_id}")
def detail(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(CareerAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    return serialize(row)


@router.get("/sources")
def sources(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(CareerSource).where(CareerSource.owner_url.in_(owner_urls(read_profile())), CareerSource.active.is_(True))
                      .order_by(CareerSource.url)).all()
    run = db.get(CareerSourceRefresh, 1)
    return {"sources": [{key: getattr(row, key) for key in
                         ("id", "url", "kind", "status", "content_hash", "fetched_at", "error", "truncated")} | {"stale": row.status != "ready" and row.content_text is not None} for row in rows],
            "refresh": {key: getattr(run, key) for key in
                        ("status", "started_at", "finished_at", "error")} if run else None}


@router.post("/sources/refresh")
def refresh(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    profile = read_profile()
    if not owner_urls(profile):
        raise HTTPException(status_code=422, detail="Añade una URL de GitHub o portafolio en tu perfil.")
    reused = request_refresh(db)
    if not reused:
        background_tasks.add_task(run_refresh, profile)
    return {"status": "running", "reused": reused}
