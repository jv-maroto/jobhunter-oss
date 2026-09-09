from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.jobs import list_jobs, swipe_jobs
from app.db import Base
from app.models.application import Application
from app.models.job import Job
from app.services import refresh_job_metadata

ROLES = ["Data Engineer", "Data Analyst", "Data Scientist", "Analytics Engineer", "BI Developer", "AI Engineer", "Quant Researcher"]
CV = {"skills": {"professional": ["SQL", "Python"]}, "search_preferences": {"roles": ROLES, "regions": ["CH"], "seniority": "junior", "employment_types": ["permanent"]}}


def _add(db, title, location, *, status="detected", score=99):
    job = Job(source="test", source_url="https://example.org", hash=f"{title}-{location}-{status}", title=title, company="Example", location=location, description="SQL and Python", track="dev", match_score=score, status=status, notes="Preserve this note", key_matches=["stale match"], predicted_salary_band="high")
    db.add(job)
    db.flush()
    return job


def _list(db, **overrides):
    args = dict(status="detected", min_score=0, source=None, track=None, limit=100, offset=0, db=db)
    args.update(overrides)
    return list_jobs(**args)


def test_discovery_uses_current_profile_before_filters_counts_and_pagination():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        swiss = [_add(db, title, "Zurich, Switzerland", score=80-i) for i, title in enumerate(ROLES)]
        foreign = _add(db, "Junior Data Engineer", "Madrid, Spain", score=100)
        _add(db, "Senior Data Analyst", "Switzerland", score=100)
        _add(db, "Data Engineer Intern", "Switzerland", score=100)
        _add(db, "Software Developer", "Switzerland", score=100)
        _add(db, "Data Analyst", "Remote", score=100)
        history = _add(db, "Senior Data Engineer", "USA", status="applied", score=100)
        db.commit()
        with patch("app.api.jobs.load_cv_master", return_value=CV):
            assert _list(db, status=None).total == 8
            assert history.id in [job.id for job in _list(db, status=None).items]
            page = _list(db, limit=2, offset=1)
            assert page.total == 7
            assert [job.id for job in page.items] == [job.id for job in swiss[1:3]]
            assert all(job.location_compatible is True for job in page.items)
            assert [job.id for job in _list(db, track="quant").items] == [swiss[-1].id]
            assert [job.id for job in _list(db, min_score=80).items] == [swiss[0].id]
            assert [job.id for job in _list(db, status="applied").items] == [history.id]
            assert len(swipe_jobs(track=None, remote_only=False, min_band=None, limit=40, db=db)) == 7
        moved = {**CV, "search_preferences": {**CV["search_preferences"], "regions": ["ES"]}}
        with patch("app.api.jobs.load_cv_master", return_value=moved):
            assert [job.id for job in _list(db).items] == [foreign.id]
        assert foreign.match_score == 100 and foreign.location_compatible is None
        assert swiss[0].track == "dev" and swiss[0].notes == "Preserve this note"


def test_metadata_refresh_is_deterministic_and_preserves_history_and_applications():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pending = _add(db, "Junior Data Engineer", "Switzerland")
        _add(db, "Senior Data Analyst", "Madrid, Spain")
        history = _add(db, "Senior Data Engineer", "USA", status="applied")
        application = Application(job_id=history.id, status="applied", cv_content="Historical CV", cover_letter_content="Historical cover")
        db.add(application)
        db.commit()
        with patch("app.services.score_job", side_effect=AssertionError("Refresh must not call AI")):
            assert refresh_job_metadata(db, CV) == {"examined": 2, "updated": 2}
            assert refresh_job_metadata(db, CV) == {"examined": 2, "updated": 0}
        assert pending.track == "data_engineer"
        assert pending.location_compatible is True and pending.seniority_compatible is True
        assert pending.match_score <= 54
        assert pending.rejection_reason.startswith("Heuristic fit estimate (current profile; no AI evaluation)")
        assert pending.key_matches == ["sql", "python"]
        assert pending.predicted_salary_band == "unknown"
        assert pending.notes == "Preserve this note" and pending.status == "detected"
        assert history.match_score == 99 and history.track == "dev"
        assert history.key_matches == ["stale match"] and history.notes == "Preserve this note"
        assert db.scalar(select(Application)).cv_content == "Historical CV"


def test_duplicate_enrichment_fills_missing_facts_without_ai_or_history_changes():
    from app.schemas.job import ScrapedJob
    from app.services import ingest_scraped_jobs

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pending = _add(db, "Junior Data Engineer", "Switzerland")
        pending.description = ""
        pending.cv_path = "/saved/cv.pdf"
        historical = _add(db, "Junior Data Analyst", "Switzerland", status="applied")
        historical.description = ""
        db.commit()
        rows = [ScrapedJob(source="test", source_url="https://example.org", hash=job.hash, title=job.title, company=job.company, location=job.location, description="Employment type: permanent. SQL and Python pipelines with documented data quality checks and reporting.", salary_min=90000, salary_max=110000, currency="CHF", salary_period="year", employment_type="permanent") for job in (pending, historical)]
        with patch("app.services.load_cv_master", return_value=CV), patch("app.services.score_job", side_effect=AssertionError("Duplicate enrichment must not call AI")):
            assert ingest_scraped_jobs(db, rows) == (0, 2)
        assert pending.description == rows[0].description
        assert pending.salary_min == 90000 and pending.salary_max == 110000
        assert pending.currency == "CHF" and pending.salary_period == "year"
        assert pending.employment_type == "permanent"
        assert pending.rejection_reason.startswith("Heuristic fit estimate")
        assert pending.cv_path == "/saved/cv.pdf" and pending.notes == "Preserve this note"
        assert pending.status == "detected"
        assert historical.description == "" and historical.salary_min is None
        assert historical.status == "applied" and historical.match_score == 99


def test_duplicate_enrichment_preserves_conflicting_nonempty_facts():
    from app.schemas.job import ScrapedJob
    from app.services import ingest_scraped_jobs

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pending = _add(db, "Junior Data Engineer", "Switzerland")
        pending.salary_max, pending.currency, pending.salary_period = 50000, "EUR", "year"
        pending.employment_type = "contract"
        db.commit()
        update = ScrapedJob(source="test", source_url="https://example.org", hash=pending.hash, title=pending.title, company=pending.company, location=pending.location, description="Replacement description", salary_min=90000, salary_max=110000, currency="CHF", salary_period="year", employment_type="permanent")
        with patch("app.services.load_cv_master", return_value=CV), patch("app.services.score_job", side_effect=AssertionError("Unexpected AI")):
            assert ingest_scraped_jobs(db, [update]) == (0, 1)
        assert pending.description == "SQL and Python"
        assert pending.salary_min is None and pending.salary_max == 50000
        assert pending.currency == "EUR" and pending.salary_period == "year"
        assert pending.employment_type == "contract" and pending.match_score == 99


def test_newly_revealed_ineligibility_enriches_existing_duplicate():
    from app.schemas.job import ScrapedJob
    from app.services import ingest_scraped_jobs

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pending = _add(db, "Junior Data Engineer", "Switzerland")
        pending.description, pending.remote = "", True
        db.commit()
        update = ScrapedJob(source="test", source_url="https://example.org", hash=pending.hash, title=pending.title, company=pending.company, location=pending.location, remote=True, description="Remote role. Candidates must be based in USA.")
        with patch("app.services.load_cv_master", return_value=CV), patch("app.services.score_job", side_effect=AssertionError("Unexpected AI")):
            assert ingest_scraped_jobs(db, [update]) == (0, 1)
        assert pending.description == update.description
        assert pending.location_compatible is False and pending.match_score < 30


def test_pipeline_preserves_existing_ineligible_duplicates_for_enrichment():
    import asyncio

    from app.schemas.job import ScrapedJob
    from app.services import scrape_and_ingest

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pending = _add(db, "Junior Data Engineer", "Switzerland")
        pending.description, pending.remote = "", True
        db.commit()
        duplicate = ScrapedJob(source="test", source_url="https://example.org", hash=pending.hash, title=pending.title, company=pending.company, location=pending.location, remote=True, description="Must be based in USA.")
        foreign = ScrapedJob(source="test", source_url="https://example.org", hash="new-foreign", title="Data Analyst", company="Example", location="USA")
        with patch("app.onboarding.detect.is_onboarded", return_value=True), patch("app.services.load_cv_master", return_value=CV), patch("app.services.run_all_scrapers", return_value=[duplicate, foreign]), patch("app.services.ingest_scraped_jobs", return_value=(0, 1)) as ingest, patch("app.services.settings.ai_scraping_enabled", False):
            result = asyncio.run(scrape_and_ingest(db))
        assert ingest.call_args.args[1] == [duplicate]
        assert result["filtered_geography"] == 2 and result["duplicates"] == 1
