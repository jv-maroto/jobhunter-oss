from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import jobs
from app.db import Base, get_db
from app.integrations.gmail.base import EmailMessage
from app.integrations.gmail.pipeline import process_email, undo_event
from app.models.application import Application
from app.models.job import Job


@pytest.fixture
def workspace(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    profile = {"skills": {"professional": ["SQL", "Python"]},
               "search_preferences": {"roles": ["Data Engineer"], "regions": ["DE"]}}
    monkeypatch.setattr(jobs, "load_cv_master", lambda: profile)
    app = FastAPI()
    app.include_router(jobs.router)
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield db, client
    engine.dispose()


def posting(**overrides):
    return {"title": "Data Engineer", "company": "Example Company",
            "description": "Build reliable data pipelines with SQL and Python.",
            "location": "Toronto, Canada", **overrides}


def make_job(db, **overrides):
    job = Job(source="test", source_url="https://example.com/jobs/123", hash="test-job",
              title="Data Engineer", company="Example Company", **overrides)
    db.add(job)
    db.commit()
    return job


def test_manual_import_deduplicates_url_and_content_without_hiding_saved_jobs(workspace):
    db, client = workspace
    created = client.post("/jobs/import", json=posting(url="https://EXAMPLE.com:443/jobs/ABC/?utm_source=test&ref=42#top"))
    assert created.status_code == 200
    job = created.json()["job"]
    assert created.json()["created"] is True
    assert job["source_url"] == "https://example.com/jobs/ABC?ref=42"
    assert job["saved_by_user"] is True and job["status"] == "detected"
    assert job["applied_at"] is None and job["location_compatible"] is False
    duplicate = client.post("/jobs/import", json=posting(url="https://example.com/jobs/ABC?ref=42", description="Updated posting"))
    assert duplicate.json()["created"] is False
    assert duplicate.json()["job"]["id"] == job["id"]
    pasted = client.post("/jobs/import", json=posting(description="  Build reliable data pipelines\nwith SQL and Python.  "))
    assert pasted.json()["created"] is False
    assert db.scalar(select(Job)).description == posting()["description"]
    listed = client.get("/jobs", params={"status": "detected"}).json()["items"]
    assert [entry["id"] for entry in listed] == [job["id"]]
    assert list(db.scalars(select(Application))) == []


def test_import_existing_scraped_job_preserves_source_and_historical_state(workspace):
    db, client = workspace
    job = make_job(db, status="interviewing", notes="Keep notes", applied_at=datetime(2026, 1, 3))
    response = client.post("/jobs/import", json=posting(url=job.source_url))
    assert response.status_code == 200 and response.json()["created"] is False
    db.refresh(job)
    assert job.source == "test" and job.saved_by_user is True
    assert job.status == "interviewing" and job.applied_at == datetime(2026, 1, 3)
    assert job.notes == "Keep notes" and job.description == posting()["description"]
    assert client.get(f"/jobs/{job.id}").json()["applied_at"].endswith("+00:00")


@pytest.mark.parametrize("invalid", [
    {"title": "   "}, {"company": ""}, {"description": ""}, {"remote": "false"},
    {"url": "javascript:alert(1)"}, {"url": "file:///tmp/job"},
    {"url": "http://127.0.0.1/job"}, {"url": "http://localhost/job"},
    {"url": "http://127.0.0.1./job"}, {"url": "http://localhost./job"},
    {"url": "http://127.1/job"}, {"url": "https://@example.com/job"},
    {"url": "https://user:password@example.com/job"}, {"title": "x" * 513},
])
def test_import_rejects_invalid_input_without_creating_jobs(workspace, invalid):
    db, client = workspace
    assert client.post("/jobs/import", json=posting(**invalid)).status_code == 422
    assert list(db.scalars(select(Job))) == []


def test_submission_dates_notes_reminders_and_reopening_preserve_history(workspace):
    db, client = workspace
    job = make_job(db, status="prepared")
    application = Application(job_id=job.id, status="prepared", cv_path="original.pdf")
    db.add(application)
    db.commit()
    response = client.patch(f"/jobs/{job.id}", json={
        "status": "applied", "application_id": application.id,
        "applied_at": "2026-02-02T14:30:00+02:00", "notes": "Submitted on the careers site",
        "next_action": "Check the application status", "next_action_at": "2026-02-09T10:00:00Z",
    })
    assert response.status_code == 200
    db.refresh(application)
    assert application.status == "submitted" and application.submitted_at == datetime(2026, 2, 2, 12, 30)
    assert job.applied_at == application.submitted_at
    assert response.json()["next_action_at"] == "2026-02-09T10:00:00+00:00"
    assert client.patch(f"/jobs/{job.id}", json={"status": "applied"}).status_code == 200
    assert application.submitted_at == datetime(2026, 2, 2, 12, 30)
    assert client.patch(f"/jobs/{job.id}", json={"status": "prepared"}).status_code == 200
    db.refresh(job)
    drafts = list(db.scalars(select(Application).where(Application.job_id == job.id).order_by(Application.id)))
    assert len(drafts) == 2 and drafts[-1].status == "prepared"
    assert job.applied_at is None and drafts[-1].submitted_at is None
    assert drafts[0].status == "submitted" and drafts[0].submitted_at == datetime(2026, 2, 2, 12, 30)
    assert drafts[-1].cv_path == drafts[0].cv_path == "original.pdf"
    assert client.patch(f"/jobs/{job.id}", json={"notes": None, "next_action": None}).status_code == 200
    assert job.notes is None and job.next_action is None and job.next_action_at is None


def test_reminder_validation_terminal_cleanup_and_application_ownership(workspace):
    db, client = workspace
    job = make_job(db, status="prepared")
    other = Job(source="test", source_url="", hash="other", title="Analyst", company="Other")
    db.add(other)
    db.flush()
    foreign = Application(job_id=other.id, status="prepared")
    db.add(foreign)
    db.commit()
    response = client.patch(f"/jobs/{job.id}", json={"status": "applied", "application_id": foreign.id})
    assert response.status_code == 409 and job.status == "prepared" and job.applied_at is None
    assert client.patch(f"/jobs/{job.id}", json={"next_action_at": "2026-06-01T10:00:00Z"}).status_code == 422
    response = client.patch(f"/jobs/{job.id}", json={"next_action": "Follow up", "next_action_at": "2026-06-01T10:00:00Z"})
    assert response.status_code == 200
    assert client.patch(f"/jobs/{job.id}", json={"status": "rejected"}).status_code == 200
    assert job.next_action is None and job.next_action_at is None
    application = db.scalar(select(Application).where(Application.job_id == job.id))
    assert application.status == "rejected" and application.submitted_at is None


def test_gmail_state_updates_link_application_and_undo_restores_followup(workspace):
    db, client = workspace
    job = make_job(db, status="applied", applied_at=datetime(2026, 3, 1),
                   next_action="Ask for an update", next_action_at=datetime(2026, 3, 10))
    application = Application(job_id=job.id, status="submitted", submitted_at=job.applied_at)
    db.add(application)
    db.commit()
    message = EmailMessage("message-1", "thread-1", "recruiting@example.com", "Example Company",
                           "Application update", "Update", "Update", datetime(2026, 3, 5))
    event = process_email(db, message, {"type": "rechazo", "company": job.company, "confidence": 1}, "test")
    assert job.status == application.status == "rejected"
    assert event.application_id == application.id
    assert job.next_action_at is None and job.applied_at == datetime(2026, 3, 1)
    assert undo_event(db, event) is True
    assert job.status == "applied" and application.status == "submitted"
    assert job.next_action == "Ask for an update" and job.next_action_at == datetime(2026, 3, 10)
    assert job.applied_at == application.submitted_at == datetime(2026, 3, 1)


def test_application_workflow_migration_preserves_old_rows_and_is_idempotent(monkeypatch):
    from app import db as database

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT)")
        connection.exec_driver_sql("CREATE TABLE applications (id INTEGER PRIMARY KEY, job_id INTEGER)")
        connection.exec_driver_sql("INSERT INTO jobs VALUES (1, 'Existing historical role')")
        connection.exec_driver_sql("INSERT INTO applications VALUES (1, 1)")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()
    database.init_db()
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT title, saved_by_user, next_action, next_action_at FROM jobs").one()
        assert row == ("Existing historical role", 0, None, None)
        row = connection.exec_driver_sql("SELECT job_id, cv_source_filename, cv_sha256, cv_mode FROM applications").one()
        assert row == (1, None, None, None)
    engine.dispose()


def test_gmail_company_only_ambiguity_requires_review_and_unique_match_still_works(workspace):
    db, _client = workspace
    first = make_job(db, status="applied", applied_at=datetime(2026, 3, 1))
    second = Job(source="test", source_url="https://example.com/jobs/456", hash="second-role",
                 title="Data Analyst", company=first.company, status="interviewing")
    unique = Job(source="test", source_url="https://example.org/jobs/789", hash="unique-role",
                 title="Data Engineer", company="Distinct Employer", status="applied")
    db.add_all([second, unique])
    db.flush()
    first_application = Application(job_id=first.id, status="submitted", submitted_at=first.applied_at)
    second_application = Application(job_id=second.id, status="interviewing")
    db.add_all([first_application, second_application])
    db.commit()
    message = EmailMessage("ambiguous", "thread", "recruiting@example.com", first.company,
                           "Application update", "Update", "Update", datetime(2026, 3, 5))
    event = process_email(db, message, {"type": "rechazo", "company": first.company, "confidence": 1}, "test")
    assert event.status == "pending_review" and event.match_method == "ambiguous_company"
    assert event.job_id is None and event.application_id is None
    assert first.status == "applied" and second.status == "interviewing"
    assert first_application.status == "submitted" and second_application.status == "interviewing"
    message.gmail_id = "unique"
    message.from_name = unique.company
    message.from_email = "recruiting@example.org"
    event = process_email(db, message, {"type": "rechazo", "company": unique.company, "confidence": 1}, "test")
    assert event.status == "auto_applied" and event.job_id == unique.id
    assert event.match_method == "company" and unique.status == "rejected"
