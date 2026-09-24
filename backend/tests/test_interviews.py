import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import interviews
from app.db import Base, get_db, init_db
from app.interviews import service
from app.models.application import Application
from app.models.interview import Interview
from app.models.job import Job


@pytest.fixture
def setup(tmp_path, monkeypatch):
    init_db()
    engine = create_engine(f"sqlite:///{tmp_path / 'interviews.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    monkeypatch.setattr("app.ai.router.ai_available", lambda: False)
    app = FastAPI()
    app.include_router(interviews.router)
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    with factory() as db:
        job = Job(source="test", source_url="https://example.com/job", hash="job", title="Backend", company="Example", description="Python API")
        db.add(job)
        db.flush()
        application = Application(job_id=job.id, cv_content="Built an API with Python", cover_letter_content="My real experience")
        db.add(application)
        db.commit()
        application_id = application.id
    with TestClient(app) as client:
        yield client, factory, application_id


def create(client, application_id):
    response = client.post("/interviews", json={"application_id": application_id})
    assert response.status_code == 201, response.text
    return response.json()


def test_snapshot_stays_frozen_crud_and_timezone(setup):
    client, factory, application_id = setup
    row = create(client, application_id)
    with factory() as db:
        application = db.get(Application, application_id)
        application.cv_content = "Later document"
        application.job.description = "Changed announcement"
        db.commit()
    detail = client.get(f"/interviews/{row['id']}").json()
    assert detail["cv_content"] == "Built an API with Python"
    assert detail["job_snapshot"]["description"] == "Python API"
    response = client.patch(f"/interviews/{row['id']}", json={"scheduled_at": "2026-10-01T15:00:00+02:00", "notes": "Ask about remote", "feedback": "Practice APIs"})
    assert response.status_code == 200
    assert response.json()["scheduled_at"] == "2026-10-01T13:00:00Z"
    assert client.patch(f"/interviews/{row['id']}", json={"cv_content": "forged"}).status_code == 422
    assert client.patch(f"/interviews/{row['id']}", json={"scheduled_at": "2026-10-01T15:00:00"}).status_code == 422
    assert client.get("/interviews").json()["total"] == 1
    assert client.delete(f"/interviews/{row['id']}").status_code == 204
    assert client.get(f"/interviews/{row['id']}").status_code == 404


def test_preparation_reused_and_stale_on_language_change(setup):
    client, factory, application_id = setup
    row = create(client, application_id)
    path = f"/interviews/{row['id']}"
    assert client.post(path + "/prepare").json()["reused"] is False
    prep = client.get(path).json()
    assert prep["prep_status"] == "completed"
    assert prep["prep_result"]["method"] == "baseline"
    assert client.post(path + "/prepare").json()["reused"] is True
    patched = client.patch(path, json={"language": "en"}).json()
    assert patched["prep_stale"] is True
    assert client.post(path + "/prepare").json()["reused"] is False
    assert client.get(path).json()["prep_result"]["summary"] == "Manual preparation: AI unavailable."


def test_failure_preserves_old_result_and_interrupted_retry(setup, monkeypatch):
    client, factory, application_id = setup
    row = create(client, application_id)
    path = f"/interviews/{row['id']}"
    client.post(path + "/prepare")
    client.patch(path, json={"stage": "technical"})
    def fail(value):
        raise ValueError("provider secret error")
    monkeypatch.setattr(service, "generate", fail)
    client.post(path + "/prepare")
    failed = client.get(path).json()
    assert failed["prep_status"] == "failed" and failed["prep_result"]["method"] == "baseline"
    assert "secret" not in failed["prep_error"]
    with factory() as db:
        interview = db.get(Interview, row["id"])
        service.request_preparation(db, interview)
    assert client.patch(path, json={"stage": "final"}).status_code == 409
    service.recover_preparations()
    assert client.get(path).json()["prep_status"] == "interrupted"
    assert client.post(path + "/prepare").json()["reused"] is False


def test_invalid_evidence_rejected(monkeypatch):
    monkeypatch.setattr("app.ai.router.ai_available", lambda: True)
    monkeypatch.setattr("app.ai.client.complete", lambda **kwargs: '{"summary":"x","questions":[{"question":"x","focus":"x","source_ids":["invented"],"answer_outline":[]}],"practice_tasks":[],"limitations":[]}')
    with pytest.raises(ValueError, match="Unknown evidence"):
        service.generate({"stage": "technical", "language": "en", "job_snapshot": {"title": "Backend"}})


def test_single_prose_outline_normalizes_without_losing_content():
    question = service.Question.model_validate({"question": "Tell us about an API", "focus": "Evidence", "source_ids": ["cv_content"], "answer_outline": "Choose a real project and explain your contribution."})
    assert question.answer_outline == ["Choose a real project and explain your contribution."]
