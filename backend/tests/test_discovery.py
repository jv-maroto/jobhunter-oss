import asyncio
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import discovery, services
from app.db import Base
from app.models.job import Job
from app.schemas.job import ScoredJobResult, ScrapedJob


def test_global_ingest_retains_unknown_location_and_bounds_ai_across_batches(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    profile = {"skills": {"backend": ["Python"]}, "search_preferences": {"regions": ["ES"], "remote_only": True}}
    before = deepcopy(profile)
    calls = []
    def score(db, job, cv):
        calls.append(cv)
        return ScoredJobResult(match_score=76, key_matches=["Python"])
    monkeypatch.setattr(services, "score_job", score)
    budget = {"remaining": 1}
    with Session(engine) as db:
        for index, location in enumerate(["", "Tokyo"]):
            job = ScrapedJob(hash=str(index), title="Python Developer", company="Demo", source="indeed", source_url=f"https://example.com/{index}", location=location, description="Python development", availability={"status":"active", "checked_at":datetime.now(timezone.utc).isoformat()})
            assert services.ingest_scraped_jobs(db, [job], cv_override=profile, globally_discovered=True, ai_budget=budget) == (1, 0)
        jobs = db.scalars(select(Job).order_by(Job.id)).all()
        assert [j.location for j in jobs] == ["", "Tokyo"]
        assert all(j.globally_discovered for j in jobs)
        assert len(calls) == 1 and budget["remaining"] == 0
        assert "regions" not in calls[0]["search_preferences"]
        assert jobs[0].match_score == 76
        current = services.current_job_metadata(jobs[0], profile)
        assert current["match_score"] == 76
        assert all(services.discovery_job(job, profile) is not None for job in jobs)
        expired = ScrapedJob(hash="0", title="Python Developer", company="Demo", source="indeed", source_url="https://example.com/0", availability={"status": "expired", "reason": "Closed", "checked_at": "2026-09-22T00:00:00Z"})
        assert services.ingest_scraped_jobs(db, [expired], cv_override=profile, globally_discovered=True, ai_budget=budget) == (0, 0)
        db.refresh(jobs[0])
        assert services.discovery_job(jobs[0], profile) is None
    assert profile == before
    engine.dispose()


def test_reservation_double_click_and_recovery(monkeypatch):
    monkeypatch.setattr(discovery, "begin_task", lambda *_: 5)
    monkeypatch.setattr(discovery, "recover_latest", lambda *_: {"phase": "interrupted", "running": False, "inserted": 3})
    assert discovery.reserve_discovery()
    assert not discovery.reserve_discovery()
    discovery._LOCK.release()
    discovery.restore_discovery()
    assert discovery.discovery_status()["phase"] == "interrupted"
    assert discovery.discovery_status()["inserted"] == 3


def test_broad_run_persists_partial_results_without_profile_mutation(monkeypatch):
    async def fake_verify(jobs, **kwargs):
        return [(job, {"status": "unverified", "reason": "test", "checked_at": None}) for job in jobs]
    monkeypatch.setattr("app.job_availability.verify_scraped_jobs", fake_verify)
    class FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def scalar(self, *args):
            return None
        def scalars(self, *args):
            return []
    profile = {"search_preferences": {"regions": ["ES"], "roles": ["Python Developer", "SQL Analyst"]}}
    before = deepcopy(profile)
    monkeypatch.setattr(discovery, "SessionLocal", FakeSession)
    monkeypatch.setattr(discovery, "load_cv_master", lambda: profile)
    monkeypatch.setattr(discovery, "COUNTRY_MAP", {"ES": {}, "DE": {}})
    monkeypatch.setattr(discovery, "begin_task", lambda *_: 6)
    states = []
    monkeypatch.setattr(discovery, "update_task", lambda task_id, state: states.append(deepcopy(state)))
    queries = []
    async def fetch(code, role):
        queries.append((code, role))
        if code == "DE":
            await asyncio.sleep(0.02)
        return [ScrapedJob(title=role, company=code, source="indeed", source_url="https://example.com/job", location="", description="Python SQL")]
    monkeypatch.setattr(discovery, "fetch_country", fetch)
    budgets = []
    def ingest(jobs, cv, budget):
        budgets.append(budget)
        return len(jobs), 0
    monkeypatch.setattr(discovery, "ingest_partial", ingest)
    assert discovery.reserve_discovery()
    asyncio.run(discovery.run_discovery())
    assert profile == before
    assert len(queries) == 2
    assert any(state["running"] and state["inserted"] == 1 and state["completed_sources"] == 1 for state in states)
    assert states[-1]["running"] is False and states[-1]["inserted"] == 2
    assert budgets[0] is budgets[1]
    assert discovery._LOCK.acquire(blocking=False)
    discovery._LOCK.release()


def test_international_search_terms_translate_and_deduplicate_without_changing_roles():
    roles = ["Desarrollador backend Python con FastAPI", "Desarrollador de aplicaciones de escritorio",
             "Administrador de sistemas", "Desarrollador full-stack", "Desarrollador PHP y PrestaShop",
             "Técnico de soporte L2", "Especialista en integraciones de IA", "Ingeniero DevOps",
             "Analista de ciberseguridad", "Administrador de redes", "Desarrollador de herramientas de automatización",
             "Python developer", "Enfermero"]
    original = list(roles)
    assert discovery.discovery_search_terms(roles) == [
        "Python developer", "systems administrator", "full stack developer", "PHP developer",
        "IT support", "AI engineer", "DevOps engineer", "cyber security analyst",
        "network administrator", "automation developer", "Enfermero"]
    assert roles == original
    assert discovery.discovery_search_terms([]) == []
