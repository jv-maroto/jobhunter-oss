from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.ext import router
from app.apply.orchestrator import apply_to_job, record_applied
from app.db import Base, get_db
from app.ext_auth import require_ext_token
from app.models.application import Application
from app.models.apply_queue import ApplyQueueItem
from app.models.job import Job


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _job(db, identity="one", status="prepared"):
    job = Job(
        source="test", source_url=f"https://example.invalid/jobs/{identity}",
        hash=identity, title="Example role", company="Example", status=status,
    )
    db.add(job)
    db.flush()
    return job


def _client(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_ext_token] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize("invalid", ["missing_queue", "wrong_job", "missing_app", "wrong_app"])
def test_invalid_queue_identity_rejected_before_any_mutation(db, invalid):
    job, other = _job(db), _job(db, "two")
    draft = Application(job_id=job.id, status="prepared", cv_content="Keep this draft")
    other_draft = Application(job_id=other.id, status="prepared")
    db.add_all([draft, other_draft])
    db.flush()
    queue = ApplyQueueItem(job_id=job.id, application_id=draft.id, status="queued")
    if invalid == "wrong_job":
        queue.job_id = other.id
    elif invalid == "missing_app":
        queue.application_id = 9999
    elif invalid == "wrong_app":
        queue.application_id = other_draft.id
    db.add(queue)
    db.commit()
    queue_id = 9999 if invalid == "missing_queue" else queue.id
    with _client(db) as client:
        response = client.post("/ext/applied", json={"job_id": job.id, "queue_id": queue_id})
    assert response.status_code == 409
    assert not db.dirty and not db.new
    db.expire_all()
    assert job.status == other.status == draft.status == other_draft.status == "prepared"
    assert job.applied_at is None and draft.submitted_at is None
    assert queue.status == "queued" and draft.cv_content == "Keep this draft"


@pytest.mark.parametrize("status", ["failed", "queued", "", None])
def test_non_submission_reports_are_rejected_without_mutation(db, status):
    job = _job(db)
    db.commit()
    with _client(db) as client:
        response = client.post("/ext/applied", json={"job_id": job.id, "status": status})
    assert response.status_code == 422
    assert job.status == "prepared" and job.applied_at is None
    assert db.scalars(select(Application)).all() == []


def test_report_uses_bound_draft_and_retries_preserve_evidence_and_later_status(db):
    job = _job(db)
    bound = Application(job_id=job.id, status="prepared", cv_content="Queued CV")
    db.add(bound)
    db.flush()
    queue = ApplyQueueItem(job_id=job.id, application_id=bound.id, status="queued")
    newer = Application(job_id=job.id, status="prepared", cv_content="Newer CV")
    db.add_all([queue, newer])
    db.commit()
    payload = {
        "job_id": job.id, "queue_id": queue.id, "status": "submitted",
        "apply_url": job.source_url, "screening_answers": {"question": "Original answer"},
    }
    with _client(db) as client:
        response = client.post("/ext/applied", json=payload)
        assert response.status_code == 200
        assert response.json()["application_id"] == bound.id
        assert bound.status == "submitted" and job.status == "applied"
        assert bound.provider == "extension" and queue.status == "submitted"
        assert bound.cv_content == "Queued CV" and newer.cv_content == "Newer CV"
        assert newer.status == "prepared" and newer.submitted_at is None
        timestamps = bound.submitted_at, job.applied_at
        assert all(timestamps)
        job.status = bound.status = "interview"
        db.commit()
        response = client.post("/ext/applied", json={**payload, "apply_url": "https://example.invalid/changed"})
        assert response.status_code == 200
    assert (bound.submitted_at, job.applied_at) == timestamps
    assert job.status == bound.status == "interview"
    assert bound.apply_url == job.source_url
    assert bound.screening_answers == {"question": "Original answer"}


def test_unbound_queue_creates_and_reuses_its_own_application(db):
    job = _job(db)
    queue = ApplyQueueItem(
        job_id=job.id, status="queued", materials={"language": "es", "cv_path": "queued.pdf"},
    )
    newer = Application(job_id=job.id, status="prepared", cv_content="Unrelated later draft")
    db.add_all([queue, newer])
    db.commit()
    recorded = record_applied(db, job, "generic", job.source_url, queue_id=queue.id)
    assert recorded.id != newer.id and queue.application_id == recorded.id
    assert recorded.language == "es" and recorded.cv_path == "queued.pdf"
    assert newer.status == "prepared" and newer.submitted_at is None
    submitted_at = recorded.submitted_at
    repeated = record_applied(db, job, "generic", job.source_url, queue_id=queue.id)
    assert repeated.id == recorded.id and repeated.submitted_at == submitted_at
    assert len(db.scalars(select(Application)).all()) == 2


@pytest.mark.parametrize("status", ["prepared", "applied", "interviewing", "offer"])
@pytest.mark.parametrize("existing_date", [None, datetime(2024, 12, 1)])
def test_report_uses_original_submission_date_without_overwriting_pipeline_history(db, status, existing_date):
    job = _job(db, status=status)
    job.applied_at = existing_date
    submitted_at = datetime(2025, 1, 1)
    application = Application(job_id=job.id, status="submitted", submitted_at=submitted_at)
    db.add(application)
    db.commit()
    record_applied(db, job, "generic", job.source_url)
    assert job.applied_at == (existing_date or submitted_at)
    assert job.status == ("applied" if status == "prepared" else status)
    assert application.submitted_at == submitted_at


def test_opening_does_not_submit_or_overwrite_an_existing_manual_record(db):
    job = _job(db, status="detected")
    result = apply_to_job(db, job, provider_override="manual")
    draft = db.get(Application, result.application_id)
    assert draft.status == "prepared" and draft.submitted_at is None
    assert job.status == "detected" and job.applied_at is None
    apply_to_job(db, job, provider_override="extension")
    assert draft.status == "prepared" and job.status == "detected"

    original_time = datetime(2025, 1, 1)
    draft.status, draft.submitted_at, draft.provider = "applied", original_time, "manual"
    draft.apply_url = "https://example.invalid/original"
    job.status, job.applied_at = "interview", original_time
    db.commit()
    apply_to_job(db, job, provider_override="manual")
    record_applied(db, job, "generic", "https://example.invalid/changed")
    assert draft.status == "applied" and draft.provider == "manual"
    assert draft.apply_url == "https://example.invalid/original"
    assert draft.submitted_at == job.applied_at == original_time
    assert job.status == "interview"
