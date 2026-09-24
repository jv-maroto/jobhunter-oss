from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.job_freshness import parse_posted_at, source_priority, stale_listing


def test_date_objects_keep_real_publication_date():
    assert parse_posted_at(date(2020, 1, 1)) == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert parse_posted_at("invalid") is None
    assert parse_posted_at(None) is None
    assert stale_listing(SimpleNamespace(posted_at=date(2020, 1, 1), description=""))


def test_closed_and_recent_jobs():
    now = datetime.now(timezone.utc)
    assert stale_listing(SimpleNamespace(posted_at=now, description="No longer accepting applications"))
    assert not stale_listing(SimpleNamespace(posted_at=now - timedelta(days=2), description="Apply now"))
    assert not stale_listing(SimpleNamespace(posted_at=None, description="Apply now"))


def test_preferred_sources():
    assert source_priority("linkedin") < source_priority("tecnoempleo")
    assert source_priority("indeed") < source_priority("tecnoempleo")


def test_unknown_publication_uses_discovery_date_for_backlog():
    assert stale_listing(SimpleNamespace(posted_at=None, created_at=datetime(2020, 1, 1), description=""))


def test_preferred_duplicate_replaces_only_discovery_source():
    from unittest.mock import patch

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db import Base
    from app.models.job import Job
    from app.schemas.job import ScrapedJob
    from app.services import ingest_scraped_jobs

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        existing = Job(hash="same", source="tecnoempleo", source_url="https://example.com/old",
                       title="Developer", company="Company", location="Spain", status="detected")
        db.add(existing)
        db.commit()
        incoming = ScrapedJob(hash="same", source="indeed", source_url="https://example.com/new",
                              title="Developer", company="Company", location="Spain")
        with patch("app.services.load_cv_master", return_value={}), patch("app.services.current_job_metadata", return_value={}):
            assert ingest_scraped_jobs(db, [incoming]) == (0, 1)
        assert existing.source == "indeed"
        assert existing.source_url == incoming.source_url
        existing.status = "applied"
        db.commit()
        incoming.source = "linkedin"
        incoming.source_url = "https://example.com/other"
        with patch("app.services.load_cv_master", return_value={}):
            ingest_scraped_jobs(db, [incoming])
        assert existing.source_url == "https://example.com/new"
