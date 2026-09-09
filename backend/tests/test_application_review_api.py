from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import applications
from app.db import Base, get_db
from app.models.application import Application
from app.models.job import Job


@pytest.fixture
def review_api(tmp_path, monkeypatch):
    monkeypatch.setattr(applications.settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(
        applications, "load_cv_master",
        lambda: {"personal": {"name": "Test Applicant", "email": "test@example.test"}},
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        app = FastAPI()
        app.include_router(applications.router)
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db, applications.settings.data_path
    engine.dispose()


def _job(db, number, **values):
    job = Job(
        source="test", source_url=f"https://example.test/jobs/{number}", hash=str(number),
        title="Data Analyst", company="Example", location="Outside current preferences",
        description="Historical description", status="prepared", match_score=0,
        updated_at=datetime(2026, 1, 1),
    )
    for name, value in values.items():
        setattr(job, name, value)
    db.add(job)
    db.flush()
    return job


def _application(db, job, directory, *, content="Saved cover", **values):
    directory.mkdir(parents=True)
    cv = b"%PDF-1.7\n" + directory.name.encode() + b" original CV\n%%EOF"
    (directory / "cv.pdf").write_bytes(cv)
    (directory / "cover.pdf").write_bytes(b"%PDF-1.7\n" + content.encode())
    application = Application(
        job_id=job.id, cv_path=str(directory / "cv.pdf"),
        cover_letter_path=str(directory / "cover.pdf"), cover_letter_content=content,
        cv_content="Original source", **values,
    )
    db.add(application)
    db.flush()
    job.cv_path = application.cv_path
    job.cover_letter_path = application.cover_letter_path
    return application


def test_register_keeps_history_without_profile_filters_and_paginates(review_api, monkeypatch):
    client, db, data = review_api
    start = datetime(2026, 1, 1)
    jobs = [_job(db, i, created_at=start + timedelta(days=i)) for i in range(105)]
    _job(db, "discovery", status="detected")
    _job(db, "saved", status="detected", saved_by_user=True, created_at=start - timedelta(days=1))
    latest = jobs[-1]
    old = _application(db, latest, data / "applications" / "old", created_at=start)
    new = _application(
        db, latest, data / "applications" / "new", created_at=start + timedelta(days=110),
        status="submitted", submitted_at=start + timedelta(days=111),
        cv_source_filename="selected.pdf", cv_sha256="a" * 64, cv_mode="existing",
    )
    db.commit()

    assessment = {"recommendation": "stretch", "checks": [], "summary": "Current evidence"}
    monkeypatch.setattr(applications, "current_job_metadata", lambda job, profile: {
        "match_score": 99, "track": "quant", "location_compatible": False,
        "qualification_assessment": assessment,
    })
    first = client.get("/applications", params={"limit": 100}).json()
    assert first["total"] == 106
    assert len(first["items"]) == 100
    assert first["items"][0]["application_id"] == new.id
    assert first["items"][0]["cv_url"] == f"/applications/{new.id}/cv"
    assert first["items"][0]["cv_source_filename"] == "selected.pdf"
    assert first["items"][0]["prepared_at"].endswith("+00:00")
    assert first["items"][0]["job"]["qualification_assessment"] == assessment
    assert first["items"][0]["job"]["match_score"] == 0
    assert first["items"][0]["job"]["track"] == "dev"
    assert first["items"][1]["application_id"] is None
    assert first["items"][1]["cv_url"] is None
    last = client.get("/applications", params={"limit": 100, "offset": 100}).json()
    assert last["total"] == 106 and len(last["items"]) == 6
    assert any(item["job"]["saved_by_user"] for item in first["items"] + last["items"])
    detail = client.get(f"/applications/{old.id}").json()
    assert detail["application_id"] == old.id
    assert detail["job"]["qualification_assessment"] == assessment
    assert detail["job"]["match_score"] == 0
    assert client.get("/applications?limit=0").status_code == 422


def test_register_orders_recent_job_changes_and_stable_ties(review_api):
    client, db, data = review_api
    start = datetime(2026, 1, 1)
    first = _job(db, 1, created_at=start)
    second = _job(db, 2, created_at=start)
    _application(
        db, second, data / "applications" / "submitted",
        created_at=start, submitted_at=start + timedelta(days=1),
    )
    db.flush()
    second.updated_at = start
    db.commit()
    assert [item["job"]["id"] for item in client.get("/applications").json()["items"]] == [second.id, first.id]
    first.notes = "Follow-up recorded"
    first.updated_at = start + timedelta(days=2)
    db.commit()
    assert [item["job"]["id"] for item in client.get("/applications").json()["items"]] == [first.id, second.id]
    second.updated_at = first.updated_at
    db.commit()
    assert [item["job"]["id"] for item in client.get("/applications").json()["items"]] == [second.id, first.id]


def test_due_queue_includes_saved_jobs_and_excludes_future_terminal_actions(review_api):
    client, db, _ = review_api
    due = datetime(2026, 4, 1, 10)
    earliest = _job(db, 1, status="detected", next_action="Reply", next_action_at=due)
    second = _job(db, 2, next_action="Follow up", next_action_at=due + timedelta(hours=1))
    _job(db, 3, next_action="Future", next_action_at=due + timedelta(days=1))
    _job(db, 4, status="rejected", next_action="Obsolete", next_action_at=due)
    _job(db, 5, status="offer", next_action="Obsolete", next_action_at=due)
    _job(db, 6, status="ghosted", next_action="Obsolete", next_action_at=due)
    _job(db, 7)
    db.commit()
    result = client.get("/applications", params={"due_before": "2026-04-01T14:00:00+02:00"})
    assert result.status_code == 200
    assert result.json()["total"] == 2
    assert [item["job"]["id"] for item in result.json()["items"]] == [earliest.id, second.id]


def test_version_list_is_job_bound_ordered_capped_and_preserves_submitted_files(review_api):
    client, db, data = review_api
    start = datetime(2026, 1, 1)
    job = _job(db, 1, status="applied")
    submitted = _application(
        db, job, data / "applications" / "submitted", content="Submitted cover",
        status="submitted", created_at=start, submitted_at=start,
    )
    original_cv = (data / "applications" / "submitted" / "cv.pdf").read_bytes()
    original_cover = (data / "applications" / "submitted" / "cover.pdf").read_bytes()
    draft = _application(
        db, job, data / "applications" / "draft", status="draft",
        created_at=start + timedelta(days=1),
    )
    latest = _application(
        db, job, data / "applications" / "latest", status="draft",
        created_at=draft.created_at,
    )
    other = _application(
        db, _job(db, 2), data / "applications" / "other",
        created_at=start + timedelta(days=10),
    )
    older = [
        Application(job_id=job.id, status="prepared", created_at=start - timedelta(days=i + 1))
        for i in range(101)
    ]
    db.add_all(older)
    db.commit()
    response = client.get(f"/applications/{submitted.id}/versions")
    assert response.status_code == 200
    versions = response.json()
    assert isinstance(versions, list) and len(versions) == 100
    assert [item["application_id"] for item in versions] == [
        latest.id, draft.id, submitted.id, *[item.id for item in older[:97]],
    ]
    assert all(item["job"]["id"] == job.id and item["application_id"] != other.id for item in versions)
    assert [item["status"] for item in versions[:3]] == ["draft", "draft", "submitted"]
    assert versions[2]["submitted_at"] == start.replace(tzinfo=timezone.utc).isoformat()
    assert client.get(versions[2]["cv_url"]).content == original_cv
    assert client.get(versions[2]["cover_url"]).content == original_cover
    assert (data / "applications" / "submitted" / "cv.pdf").read_bytes() == original_cv
    assert (data / "applications" / "submitted" / "cover.pdf").read_bytes() == original_cover
    assert client.get(f"/applications/{submitted.id}").json()["application_id"] == submitted.id
    assert client.get("/applications/999999/versions").status_code == 404


def test_documents_stay_bound_to_selected_row_and_safe_path(review_api):
    client, db, data = review_api
    job = _job(db, 1)
    old = _application(db, job, data / "applications" / "old", content="Old")
    new = _application(db, job, data / "applications" / "new", content="New")
    old.cv_content = "Existing CV 'original.pdf' copied unchanged for role 'bi'. SHA-256: " + "b" * 64 + "."
    db.commit()
    for application, marker in [(old, b"old original CV"), (new, b"new original CV")]:
        assert marker in client.get(f"/applications/{application.id}/cv").content
    detail = client.get(f"/applications/{old.id}").json()
    assert detail["cv_source_filename"] == "original.pdf"
    assert detail["cv_sha256"] == "b" * 64 and detail["cv_mode"] == "existing"
    assert b"Old" in client.get(f"/applications/{old.id}/cover").content
    assert b"New" in client.get(f"/applications/{new.id}/cover").content
    old.cv_path = "/old/container/data/applications/old/cv.pdf"
    db.commit()
    assert b"old original CV" in client.get(f"/applications/{old.id}/cv").content
    assert old.cv_path == "/old/container/data/applications/old/cv.pdf"
    (data / "applications" / "old" / "cv.pdf").unlink()
    assert client.get(f"/applications/{old.id}/cv").status_code == 410
    outside = data / "private.pdf"
    outside.write_bytes(b"PRIVATE")
    link = data / "applications" / "linked.pdf"
    link.symlink_to(outside)
    loop = data / "applications" / "loop.pdf"
    loop.symlink_to(loop)
    for path in [outside, link, loop, data / "applications" / ".." / "private.pdf"]:
        old.cv_path = str(path)
        db.commit()
        assert client.get(f"/applications/{old.id}/cv").status_code == 410
    old.cv_path = None
    db.commit()
    assert client.get(f"/applications/{old.id}/cv").status_code == 404
    assert client.get("/applications/9999").status_code == 404


def test_cover_patch_isolated_from_newer_application_and_preserves_submission(review_api, monkeypatch):
    client, db, data = review_api
    job = _job(db, 1, status="applied")
    submitted = datetime(2026, 3, 1, 12)
    old = _application(
        db, job, data / "applications" / "old", status="draft",
        created_at=submitted - timedelta(days=1),
    )
    new = _application(
        db, job, data / "applications" / "new", created_at=submitted,
        status="submitted", submitted_at=submitted,
    )
    db.commit()
    old_cv_path, job_cv_path, old_cover_path = old.cv_path, job.cv_path, old.cover_letter_path
    old_cv_digest = hashlib.sha256((data / "applications" / "old" / "cv.pdf").read_bytes()).hexdigest()

    def render(content, profile, job_data, out_dir, pdf_path, language):
        assert language == "en" and profile["personal"]["name"] == "Test Applicant"
        assert job_data["company"] == "Example"
        assert not (out_dir / "cv.pdf").exists()
        pdf_path.write_bytes(b"%PDF-1.7\n" + content.encode())

    monkeypatch.setattr(applications, "_compile_cover_pdf", render)
    for content in ["Revised letter", "Revised letter again"]:
        response = client.patch(f"/applications/{old.id}/cover", json={"cover_letter_content": content})
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "draft" and result["submitted_at"] is None
        assert client.get(f"/applications/{old.id}").json()["cover_letter_content"] == content
        assert content.encode() in client.get(result["cover_url"]).content
    db.refresh(old)
    db.refresh(job)
    assert old.cv_path == old_cv_path and old.cv_content == "Original source"
    assert hashlib.sha256((data / "applications" / "old" / "cv.pdf").read_bytes()).hexdigest() == old_cv_digest
    assert job.cv_path == job_cv_path and job.cover_letter_path == new.cover_letter_path
    assert (data / "applications" / "old" / "cover.pdf").read_bytes() == b"%PDF-1.7\nSaved cover"
    assert old.cover_letter_path != old_cover_path and job.status == "applied"
    submitted_review = client.get(f"/applications/{new.id}").json()
    assert submitted_review["submitted_at"] == submitted.replace(tzinfo=timezone.utc).isoformat()
    assert submitted_review["status"] == "submitted"
    assert submitted_review["cover_letter_content"] == "Saved cover"
    latest = _application(
        db, job, data / "applications" / "latest", created_at=submitted + timedelta(days=1),
    )
    db.commit()
    response = client.patch(f"/applications/{latest.id}/cover", json={"cover_letter_content": "Latest revision"})
    assert response.status_code == 200
    db.refresh(latest)
    db.refresh(job)
    assert job.cover_letter_path == latest.cover_letter_path
    assert client.get(f"/applications/{new.id}").json()["cover_letter_content"] == "Saved cover"
    assert (data / "applications" / "new" / "cover.pdf").read_bytes() == b"%PDF-1.7\nSaved cover"


def test_submitted_and_non_draft_covers_are_read_only_before_side_effects(review_api, monkeypatch):
    client, db, data = review_api
    submitted = datetime(2026, 3, 1, 12)

    def forbidden(*args):
        raise AssertionError("Read-only application must not load a profile or render documents")

    monkeypatch.setattr(applications, "load_cv_master", forbidden)
    monkeypatch.setattr(applications, "_compile_cover_pdf", forbidden)
    states = [
        ("submitted", submitted), ("submitted", None), ("prepared", submitted),
        ("draft", submitted), ("rejected", None), ("offer", None), ("ghosted", None),
        ("queued", None),
    ]
    for number, (status, timestamp) in enumerate(states):
        job = _job(db, number)
        application = _application(
            db, job, data / "applications" / str(number), status=status, submitted_at=timestamp,
        )
        db.commit()
        before_row = {column.name: getattr(application, column.name) for column in Application.__table__.columns}
        before_job = {column.name: getattr(job, column.name) for column in Job.__table__.columns}
        before_paths = set(data.rglob("*"))
        before_files = {path: path.read_bytes() for path in before_paths if path.is_file()}
        response = client.patch(f"/applications/{application.id}/cover", json={"cover_letter_content": "Overwrite"})
        assert response.status_code == 409
        assert response.json()["detail"] == "Submitted application documents are read-only. Prepare a new version to edit the cover letter."
        db.refresh(application)
        db.refresh(job)
        assert {column.name: getattr(application, column.name) for column in Application.__table__.columns} == before_row
        assert {column.name: getattr(job, column.name) for column in Job.__table__.columns} == before_job
        assert set(data.rglob("*")) == before_paths
        assert {path: path.read_bytes() for path in before_files} == before_files


def test_invalid_or_failed_cover_patch_keeps_previous_saved_version(review_api, monkeypatch):
    client, db, data = review_api
    job = _job(db, 1)
    application = _application(db, job, data / "applications" / "existing")
    db.commit()
    previous = application.cover_letter_path
    before_dirs = set((data / "applications").rglob("cover.pdf"))
    calls = []

    def fail_render(*args):
        calls.append(True)
        args[4].write_bytes(b"partial output")
        raise applications.CVGenerationError("compiler failed")

    monkeypatch.setattr(applications, "_compile_cover_pdf", fail_render)
    for body in [{"cover_letter_content": " "}, {"cover_letter_content": "x" * 20001},
                 {"cover_letter_content": "Valid", "cv_path": "/other.pdf"}]:
        assert client.patch(f"/applications/{application.id}/cover", json=body).status_code == 422
    assert not calls
    failed = client.patch(f"/applications/{application.id}/cover", json={"cover_letter_content": "Changed"})
    assert failed.status_code == 500 and len(calls) == 1
    db.refresh(application)
    assert application.cover_letter_path == previous
    assert application.cover_letter_content == "Saved cover"
    assert set((data / "applications").rglob("cover.pdf")) == before_dirs
    assert b"Saved cover" in client.get(f"/applications/{application.id}/cover").content

    def render(*args):
        args[4].write_bytes(b"%PDF-1.7\nChanged")

    def fail_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(applications, "_compile_cover_pdf", render)
    monkeypatch.setattr(db, "commit", fail_commit)
    failed = client.patch(f"/applications/{application.id}/cover", json={"cover_letter_content": "Changed"})
    assert failed.status_code == 500
    db.refresh(application)
    assert application.cover_letter_path == previous
    assert application.cover_letter_content == "Saved cover"
    assert set((data / "applications").rglob("cover.pdf")) == before_dirs


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst compiler unavailable")
def test_cover_patch_renders_literal_text_with_real_compiler(review_api):
    PdfReader = pytest.importorskip("pypdf").PdfReader
    client, db, data = review_api
    application = _application(db, _job(db, 1), data / "applications" / "literal")
    db.commit()
    content = 'Hello [team].\n\n#read("../../private.txt") @literal $x$'
    response = client.patch(f"/applications/{application.id}/cover", json={"cover_letter_content": content})
    assert response.status_code == 200
    db.refresh(application)
    text = "\n".join(page.extract_text() for page in PdfReader(application.cover_letter_path).pages)
    assert 'read("../../private.txt")' in text
    assert "Hello [team]" in text and "test@example.test" in text
