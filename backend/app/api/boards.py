"""Register known company ATS boards and stage jobs for individual review."""
from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.company_boards.readers import validate_slug
from app.company_boards.service import refresh_board, stamp
from app.db import get_db
from app.models.company_board import CompanyBoard

router = APIRouter(prefix="/search/boards", tags=["company-boards"])


class BoardIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    provider: Literal["greenhouse", "lever", "lever_eu", "ashby"]
    slug: str = Field(min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, value):
        return validate_slug(value)


class BoardOut(BoardIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    last_refresh: dict | None
    created_at: datetime
    updated_at: datetime


class BoardPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["active", "archived"] | None = None


def get_board(db, board_id):
    row = db.get(CompanyBoard, board_id)
    if row is None:
        raise HTTPException(404, "Board not found")
    return row


def change_board(db, row, values):
    if row.last_refresh and row.last_refresh.get("status") == "running":
        raise HTTPException(409, "Board refresh is running")
    previous = row.last_refresh
    result = db.execute(update(CompanyBoard).where(
        CompanyBoard.id == row.id, CompanyBoard.updated_at == row.updated_at,
        or_(CompanyBoard.last_refresh.is_(None), CompanyBoard.last_refresh == JSON.NULL)
        if previous is None else CompanyBoard.last_refresh == previous,
    ).values(**values, updated_at=datetime.utcnow()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Board changed concurrently; reload and retry")
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[BoardOut])
def list_boards(include_archived: bool = False, db: Session = Depends(get_db)):
    stmt = select(CompanyBoard).order_by(CompanyBoard.name, CompanyBoard.id)
    if not include_archived:
        stmt = stmt.where(CompanyBoard.status != "archived")
    return db.scalars(stmt).all()


@router.post("", response_model=BoardOut, status_code=201)
def create_board(body: BoardIn, db: Session = Depends(get_db)):
    row = CompanyBoard(**body.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This provider and board slug are already registered (possibly archived)") from exc
    db.refresh(row)
    return row


@router.patch("/{board_id}", response_model=BoardOut)
def edit_board(board_id: int, body: BoardPatch, db: Session = Depends(get_db)):
    return change_board(db, get_board(db, board_id), body.model_dump(exclude_none=True))


@router.delete("/{board_id}", response_model=BoardOut)
def archive_board(board_id: int, db: Session = Depends(get_db)):
    return change_board(db, get_board(db, board_id), {"status": "archived"})


@router.get("/{board_id}/jobs")
def board_jobs(board_id: int, db: Session = Depends(get_db)):
    row = get_board(db, board_id)
    return {"board_id": row.id, "jobs": row.staged_jobs, "last_refresh": row.last_refresh}


@router.post("/{board_id}/refresh", status_code=202)
def start_refresh(board_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    row = get_board(db, board_id)
    if row.status == "archived":
        raise HTTPException(422, "Restore this board before refreshing")
    run = {"id": uuid4().hex, "status": "running", "started_at": stamp()}
    change_board(db, row, {"last_refresh": run})
    background_tasks.add_task(refresh_board, board_id)
    return {"board_id": board_id, "run": run}
