"""Endpoints de persons."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.person import Person
from app.schemas.person import PersonOut, PersonPatch

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("", response_model=list[PersonOut])
def list_persons(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    stmt = select(Person).order_by(desc(Person.priority), desc(Person.created_at)).limit(limit)
    if status:
        stmt = stmt.where(Person.status == status)
    return [PersonOut.model_validate(p) for p in db.execute(stmt).scalars().all()]


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db)) -> PersonOut:
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonOut.model_validate(p)


@router.patch("/{person_id}", response_model=PersonOut)
def patch_person(person_id: int, patch: PersonPatch, db: Session = Depends(get_db)) -> PersonOut:
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    if patch.status:
        p.status = patch.status
        if patch.status == "sent" and not p.sent_at:
            p.sent_at = datetime.utcnow()
    if patch.notes is not None:
        p.notes = patch.notes
    db.commit()
    db.refresh(p)
    return PersonOut.model_validate(p)


@router.post("/{person_id}/mark-sent", response_model=PersonOut)
def mark_sent(person_id: int, db: Session = Depends(get_db)) -> PersonOut:
    p = db.get(Person, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    p.status = "sent"
    p.sent_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return PersonOut.model_validate(p)
