from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete as sql_delete
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.interviews.service import request_preparation, run_preparation, serialize
from app.models.application import Application
from app.models.interview import Interview

router = APIRouter(prefix="/interviews", tags=["interviews"])
Stage = Literal["screening", "technical", "behavioral", "final"]


class CreateInterview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: int = Field(gt=0)
    stage: Stage = "screening"
    language: Literal["es", "en"] = "es"
    scheduled_at: datetime | None = None
    notes: str = Field(default="", max_length=20000)

    @field_validator("scheduled_at")
    @classmethod
    def utc_date(cls, value):
        if value and not value.tzinfo:
            raise ValueError("La fecha debe incluir zona horaria")
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None


class PatchInterview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Stage | None = None
    language: Literal["es", "en"] | None = None
    scheduled_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=20000)
    feedback: str | None = Field(default=None, max_length=20000)
    status: Literal["planned", "completed", "cancelled"] | None = None
    _date = field_validator("scheduled_at")(CreateInterview.utc_date.__func__)


def get_interview(db: Session, interview_id: int) -> Interview:
    row = db.get(Interview, interview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Entrevista no encontrada")
    return row


@router.get("")
def list_interviews(application_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    query = select(Interview)
    if application_id is not None:
        query = query.where(Interview.application_id == application_id)
    rows = db.scalars(query.order_by(Interview.created_at.desc())).all()
    return {"items": [serialize(row) for row in rows], "total": len(rows)}


@router.post("", status_code=201)
def create(body: CreateInterview, db: Session = Depends(get_db)) -> dict:
    application = db.get(Application, body.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidatura no encontrada")
    snapshot = application.job_snapshot
    if not snapshot:
        job = application.job
        snapshot = {key: getattr(job, key) for key in ("title", "company", "description", "location", "source_url")}
        snapshot["snapshot_note"] = "Candidatura histórica sin anuncio archivado: capturado al crear la entrevista."
    row = Interview(**body.model_dump(), job_snapshot=snapshot,
                    cv_content=application.cv_content, cover_letter_content=application.cover_letter_content)
    db.add(row)
    db.commit()
    return serialize(row)


@router.get("/{interview_id}")
def detail(interview_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize(get_interview(db, interview_id))


@router.patch("/{interview_id}")
def patch(interview_id: int, body: PatchInterview, db: Session = Depends(get_db)) -> dict:
    row = get_interview(db, interview_id)
    fields = body.model_dump(exclude_unset=True)
    if any(value is None and key != "scheduled_at" for key, value in fields.items()):
        raise HTTPException(status_code=422, detail="Solo scheduled_at puede estar vacío; usa una cadena vacía para borrar notas.")
    if row.prep_status in {"queued", "running"} and {"stage", "language"} & fields.keys():
        raise HTTPException(status_code=409, detail="Espera a que termine la preparación para cambiar idioma o fase.")
    changed = db.execute(update(Interview).where(Interview.id == row.id,
        Interview.updated_at == row.updated_at, Interview.prep_status == row.prep_status
    ).values(**fields, updated_at=datetime.utcnow()).execution_options(synchronize_session=False))
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, "La entrevista cambió. Recarga y reintenta.")
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.delete("/{interview_id}", status_code=204)
def delete(interview_id: int, db: Session = Depends(get_db)) -> Response:
    row = get_interview(db, interview_id)
    if row.prep_status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Espera a que termine la preparación antes de borrar.")
    changed = db.execute(sql_delete(Interview).where(Interview.id == row.id,
        Interview.updated_at == row.updated_at, Interview.prep_status == row.prep_status))
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, "La entrevista cambió. Recarga y reintenta.")
    db.commit()
    return Response(status_code=204)


@router.post("/{interview_id}/prepare")
def prepare(interview_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    row = get_interview(db, interview_id)
    try:
        reused = request_preparation(db, row)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not reused:
        background_tasks.add_task(run_preparation, row.id)
    return {"interview": serialize(row), "reused": reused}
