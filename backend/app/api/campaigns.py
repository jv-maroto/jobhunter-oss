"""Campaign CRUD; saving never changes global preferences."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import JSON, or_, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.search_campaign import SearchCampaign
from app.search_campaigns.catalog import country_code, coverage

router = APIRouter(prefix="/search", tags=["search-campaigns"])


class CampaignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    roles: list[str] = Field(default_factory=list, max_length=30)
    countries: list[str] = Field(default_factory=list, max_length=249)
    modality: Literal["remote", "hybrid", "onsite", "any"] = "any"
    languages: list[str] = Field(default_factory=list, max_length=30)
    residence_country: str | None = None
    max_queries: int = Field(default=8, ge=1, le=50)
    results_per_query: int = Field(default=20, ge=1, le=100)
    status: Literal["draft", "paused", "archived"] = "draft"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()

    @field_validator("countries")
    @classmethod
    def normalize_countries(cls, values):
        return list(dict.fromkeys(country_code(v) for v in values))

    @field_validator("residence_country")
    @classmethod
    def normalize_residence(cls, value):
        return country_code(value) if value else None

    @field_validator("roles", "languages")
    @classmethod
    def clean_values(cls, values):
        if any(not v.strip() or len(v) > 160 for v in values):
            raise ValueError("Entries must be nonblank and at most 160 characters")
        return list(dict.fromkeys(v.strip() for v in values))


class CampaignOut(CampaignIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    last_run: dict | None = None


def get_campaign(db: Session, campaign_id: int) -> SearchCampaign:
    row = db.get(SearchCampaign, campaign_id)
    if row is None:
        raise HTTPException(404, "Campaign not found")
    return row


def _unchanged(row: SearchCampaign, previous_run: dict | None):
    """Compare the complete revision, including edits concurrent with a run claim."""
    return (
        SearchCampaign.id == row.id,
        SearchCampaign.updated_at == row.updated_at,
        (or_(SearchCampaign.last_run.is_(None), SearchCampaign.last_run == JSON.NULL)
         if previous_run is None else SearchCampaign.last_run == previous_run),
    )


def _require_claim(db: Session, result) -> None:
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Campaign was updated or started concurrently; reload and retry")


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(include_archived: bool = False, db: Session = Depends(get_db)):
    statement = select(SearchCampaign).order_by(SearchCampaign.updated_at.desc(), SearchCampaign.id.desc())
    if not include_archived:
        statement = statement.where(SearchCampaign.status != "archived")
    return db.scalars(statement).all()


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    row = SearchCampaign(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, body: dict, db: Session = Depends(get_db)):
    row = get_campaign(db, campaign_id)
    if row.last_run and row.last_run.get("status") == "running":
        raise HTTPException(409, "Campaign is running")
    current = {key: getattr(row, key) for key in CampaignIn.model_fields}
    try:
        validated = CampaignIn.model_validate({**current, **body})
    except ValueError as exc:
        raise HTTPException(422, "Invalid campaign fields or values") from exc
    changed = db.execute(update(SearchCampaign).where(*_unchanged(row, row.last_run)).values(
        **validated.model_dump(), updated_at=datetime.utcnow()
    ).execution_options(synchronize_session=False))
    _require_claim(db, changed)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/campaigns/{campaign_id}", response_model=CampaignOut)
def archive_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return update_campaign(campaign_id, {"status": "archived"}, db)


@router.get("/coverage")
def get_coverage():
    return coverage()


@router.post("/campaigns/{campaign_id}/run", status_code=202)
def start_campaign(campaign_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.search_campaigns.runner import reserve_run, run_campaign

    row = get_campaign(db, campaign_id)
    previous = row.last_run
    revision = _unchanged(row, previous)
    try:
        result = reserve_run(row)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.expire(row, ["last_run"])
    claimed = db.execute(update(SearchCampaign).where(*revision).values(
        last_run=result, updated_at=datetime.utcnow()
    ).execution_options(synchronize_session=False))
    _require_claim(db, claimed)
    db.commit()
    background_tasks.add_task(run_campaign, campaign_id)
    return {"campaign_id": campaign_id, "run": result}
