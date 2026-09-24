import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.career import analysis
from app.db import Base
from app.models import career_source  # noqa: F401
from app.models.career_analysis import CareerAnalysis


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'career.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(analysis, "SessionLocal", sessions)
    return sessions


PROFILE = {"experience": [{"role": "Backend Developer", "highlights_es": ["API de pedidos"]}],
           "projects": [{"name": "Demo", "technologies": ["Python"]}]}


def test_profile_version_ignores_preferences_and_contacts():
    modified = {**PROFILE, "search_preferences": {"regions": ["JP"]},
                "personal": {"email": "private@example.com"}}
    assert analysis.fingerprint(analysis.snapshot(PROFILE)) == analysis.fingerprint(analysis.snapshot(modified))
    changed = {**PROFILE, "projects": [{"name": "New project"}]}
    assert analysis.fingerprint(analysis.snapshot(PROFILE)) != analysis.fingerprint(analysis.snapshot(changed))


def test_reuse_and_restart_preserves_result(factory, monkeypatch):
    calls = []
    monkeypatch.setattr(analysis, "generate", lambda source: calls.append(source) or {"method": "llm", "summary": "ok"})
    with factory() as db:
        row, reused = analysis.request_analysis(db, PROFILE)
        assert not reused
        row_id = row.id
    analysis.run_analysis(row_id)
    analysis.run_analysis(row_id)
    assert analysis.recover_interrupted() == 0
    with factory() as db:
        row, reused = analysis.request_analysis(db, PROFILE)
        assert reused and row.status == "completed" and row.result["summary"] == "ok"
    assert len(calls) == 1


def test_interrupted_retry_and_failure_preserves_prior_result(factory, monkeypatch):
    with factory() as db:
        row, _ = analysis.request_analysis(db, PROFILE)
        row.result = {"method": "llm", "summary": "previous valid"}
        db.commit()
        row_id = row.id
    assert analysis.recover_interrupted() == 1
    with factory() as db:
        row, reused = analysis.request_analysis(db, PROFILE)
        assert row.id == row_id and not reused and row.status == "queued"
    def fail(source):
        raise RuntimeError("private provider error")
    monkeypatch.setattr(analysis, "generate", fail)
    analysis.run_analysis(row_id)
    with factory() as db:
        row = db.get(CareerAnalysis, row_id)
        assert row.status == "failed"
        assert row.result["summary"] == "previous valid"
        assert "private" not in row.error
        assert len(db.scalars(select(CareerAnalysis)).all()) == 1


def test_baseline_honest_and_evidence_backed(monkeypatch):
    monkeypatch.setattr("app.ai.router.ai_available", lambda: False)
    result = analysis.generate(analysis.snapshot(PROFILE))
    assert result["method"] == "baseline"
    assert result["roles"][0]["title"] == "Backend Developer"
    assert result["roles"][0]["evidence_ids"][0] in {e["id"] for e in result["evidence"]}
    assert any("no se ha inspeccionado" in x for x in result["limitations"])


def test_llm_cannot_reference_invented_evidence(monkeypatch):
    monkeypatch.setattr("app.ai.router.ai_available", lambda: True)
    monkeypatch.setattr("app.ai.client.complete", lambda **kw: '{"summary":"ok","roles":[{"title":"CTO","fit":"direct","reason":"x","evidence_ids":["invented"],"gaps":[]}],"limitations":[]}')
    with pytest.raises(ValueError, match="evidencias inexistentes"):
        analysis.generate(analysis.snapshot(PROFILE))


def test_empty_profile_rejected(factory):
    with factory() as db, pytest.raises(ValueError, match="Añade"):
        analysis.request_analysis(db, {"personal": {"email": "x@example.com"}})


def test_api_returns_latest_and_stale_profile(factory, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api import career
    from app.db import get_db

    app = FastAPI()
    app.include_router(career.router)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(career, "read_profile", lambda: PROFILE)
    monkeypatch.setattr(analysis, "generate", lambda source: {"method": "llm", "summary": "ok"})
    with TestClient(app) as client:
        assert client.get("/career/analyses/latest").json()["analysis"] is None
        response = client.post("/career/analyses", json={})
        assert response.status_code == 200
        analysis_id = response.json()["analysis"]["id"]
        assert client.get(f"/career/analyses/{analysis_id}").json()["status"] == "completed"
        assert client.post("/career/analyses", json={}).json()["reused"] is True
        monkeypatch.setattr(career, "read_profile", lambda: {**PROFILE, "summary_es": "Nuevo dato"})
        latest = client.get("/career/analyses/latest").json()
        assert latest["stale"] is True
        assert latest["last_completed"]["result"]["summary"] == "ok"
        assert client.get("/career/analyses/999999").status_code == 404


def test_latest_valid_result_excludes_json_null(factory, monkeypatch):
    from datetime import datetime

    from sqlalchemy import text

    from app.api import career

    monkeypatch.setattr(career, "read_profile", lambda: PROFILE)
    with factory() as db:
        good = CareerAnalysis(source_hash="good", source_snapshot={}, status="completed",
                              result={"summary": "valid"}, finished_at=datetime(2026, 1, 1))
        bad = CareerAnalysis(source_hash="bad", source_snapshot={}, status="failed",
                             finished_at=datetime(2026, 2, 1))
        db.add_all([good, bad])
        db.commit()
        # Older deployments stored JSON null rather than SQL NULL.
        db.execute(text("UPDATE career_analyses SET result = 'null' WHERE source_hash = 'bad'"))
        db.commit()
        latest = career.latest(db)
        assert latest["last_completed"]["result"]["summary"] == "valid"
