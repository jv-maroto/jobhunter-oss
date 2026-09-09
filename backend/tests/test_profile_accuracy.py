from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.ai import profile_context, profile_extractor
from app.api import ext, onboarding
from app.config import settings
from app.onboarding import detect, draft_store, fusion, roles
from app.profile_store import read_profile, write_profile


@pytest.fixture
def profile_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "cv_master_path", str(tmp_path / "cv.json"))
    monkeypatch.setattr(settings, "onboarding_draft_path", str(tmp_path / "draft.json"))
    monkeypatch.setattr(settings, "onboarding_marker_path", str(tmp_path / ".onboarded"))
    monkeypatch.setattr(fusion, "generate_summaries", lambda _: {})
    profile_context.cache_clear()
    yield tmp_path
    profile_context.cache_clear()
    from app.services import load_cv_master

    load_cv_master.cache_clear()


def candidate():
    return {
        "personal": {"name": "Example Person", "location": "Example, Spain"},
        "summary_en": "Graduate with data internship and academic ML projects.",
        "experience": [{"role": "Data Intern", "company": "Example", "end": "Jul 2026",
                        "highlights": ["Validated reporting."]}],
        "skills": {"Professional": ["SQL"], "Academic": ["PyTorch"]},
        "education": [{"degree": "Analytics", "institution": "University", "year": "2026"}],
        "projects": [{"name": "Academic model", "context": "academic", "url": ""}],
        "languages": [{"name": "German", "level": "Currently learning"}],
        "search_preferences": {"regions": ["CH"], "roles": ["Data Engineer", "Quant Researcher"]},
        "_meta": {"evidence": {"languages": "User confirmation"}},
    }


def test_partial_import_preserves_reviewed_profile_and_provenance(profile_files):
    original = candidate()
    base = copy.deepcopy(original)
    result = fusion.fuse({"linkedin": {"source": "linkedin", "personal": {"name": "Other"},
                                      "skills": {"Academic": ["pytorch"]}}}, base)
    assert base == original
    assert result["cv_master"] == {**original, "summary_es": "", "certifications": [],
                                    "projects_highlight": original["projects"], "narratives": {}}
    assert result["conflicts"][0]["kept"] == "Example Person"


def test_save_validates_without_defaults_and_invalidates_caches(profile_files):
    write_profile(candidate())
    assert profile_context.project_keywords() == ["academic model"]
    changed = candidate()
    changed["projects"] = [{"name": "Revised model"}]
    write_profile(changed)
    assert read_profile() == changed
    assert "salary_min_eur" not in read_profile()["search_preferences"]
    assert profile_context.project_keywords() == ["revised model"]
    with pytest.raises(ValueError):
        write_profile({"skills": ["invalid shape"]})
    assert read_profile() == changed
    assert len(list((profile_files / "cv_master_backups").glob("*.json"))) == 1


def test_reset_and_review_resume_without_losing_profile(profile_files):
    cv = candidate()
    write_profile(cv)
    detect.mark_onboarded()
    result = onboarding.post_reset()
    assert result["onboarded"] is False and result["backup"]
    assert read_profile() == cv
    assert detect.is_onboarded() is False
    assert draft_store.load_draft()["merged"]["cv_master"] == cv
    cv["search_preferences"]["salary_currency"] = "CHF"
    onboarding.put_draft(onboarding.CompleteBody(cv_master=cv))
    draft_store.save_fragment("linkedin", {"personal": {"name": "Imported Name"}})
    onboarding.put_draft(onboarding.CompleteBody(cv_master=cv))
    assert draft_store.load_draft()["merged"] is None
    merged = onboarding.post_merge()["cv_master"]
    assert merged["personal"]["name"] == "Example Person"
    assert merged["search_preferences"]["regions"] == ["CH"]
    assert merged["search_preferences"]["salary_currency"] == "CHF"
    onboarding.post_complete(onboarding.CompleteBody(cv_master=merged))
    assert detect.is_onboarded() is True
    assert draft_store.load_draft()["merged"] is None


def test_corrupt_profile_or_draft_is_not_overwritten(profile_files):
    settings.cv_master_file.write_text("{broken")
    with pytest.raises(ValueError):
        write_profile(candidate())
    assert settings.cv_master_file.read_text() == "{broken"
    settings.onboarding_draft_file.write_text("{broken")
    with pytest.raises(ValueError):
        draft_store.save_review(candidate())
    assert settings.onboarding_draft_file.read_text() == "{broken"


def test_autofill_has_no_invented_current_job_salary_or_permission(profile_files):
    write_profile(candidate())
    result = ext.get_profile()
    assert result["current_role"] == result["current_company"] == ""
    assert result["salary_min_eur"] is None and result["salary_max_eur"] is None
    assert result["work_authorization_ch"] is None and result["work_authorization_eu"] is None
    assert result["notice_period"] == ""
    assert result["location"] == "Example, Spain"
    assert result["academic_degree"] == "Analytics"
    assert result["languages"] == "German: Currently learning"


def test_extractor_retains_projects_and_rejects_bad_shapes(monkeypatch):
    monkeypatch.setattr(profile_extractor, "llm_available", lambda: True)
    extracted = {"projects": [{"name": "Model", "context": "academic"}]}
    monkeypatch.setattr(profile_extractor, "complete", lambda **_: json.dumps(extracted))
    result = profile_extractor.structure_cv_text("Academic project: Model")
    assert result["projects"] == extracted["projects"]
    assert result["raw_text"] == "Academic project: Model"
    monkeypatch.setattr(profile_extractor, "complete", lambda **_: '{"skills":["bad"]}')
    assert profile_extractor.structure_cv_text("Source text") == {"source": "cv", "raw_text": "Source text"}


def test_saved_roles_are_not_capped_or_reinterpreted(monkeypatch):
    monkeypatch.setattr(roles, "_ai_available", lambda: pytest.fail("Saved choices need no AI"))
    targets = ["Data Engineer", "Data Analyst", "Data Scientist", "Quant Researcher",
               "Analytics Engineer", "BI Developer", "AI Engineer"]
    assert [item["label"] for item in roles.suggest_roles({"search_preferences": {"roles": targets}})] == targets


def test_screening_cache_changes_with_profile_and_rejects_invalid_option(profile_files, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.apply import screening
    from app.db import Base
    from app.models.job import Job

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    calls = []
    monkeypatch.setattr(screening, "_llm_available", lambda: True)

    def complete(**kwargs):
        calls.append(json.loads(kwargs["user"])["perfil"]["languages"][0]["level"])
        return calls[-1]

    monkeypatch.setattr(screening, "complete", complete)
    cv = candidate()
    write_profile(cv)
    with Session(engine) as db:
        job = Job(source="test", source_url="https://example.test/job", hash="screening-test",
                  title="Data Analyst", company="Example", location="Zürich, CH")
        db.add(job)
        db.commit()
        assert screening.answer_question(db, job, "German proficiency?")["answer"] == "Currently learning"
        assert screening.answer_question(db, job, "German proficiency?")["cached"] is True
        cv["languages"][0]["level"] = "Beginner"
        write_profile(cv)
        assert screening.answer_question(db, job, "German proficiency?")["answer"] == "Beginner"
        assert calls == ["Currently learning", "Beginner"]
        assert screening.answer_question(db, job, "German proficiency?", ["Native", "Fluent"])["answer"] == ""


def test_connection_fallback_uses_actual_focus_without_fabricated_stack():
    from app.ai.connection_message import _fallback_message

    result = _fallback_message({"full_name": "Ada Example"}, {"personal": {"title": "Data analytics"}}, "en")
    assert "Ada" in result and "Data analytics" in result
    assert "FastAPI" not in result and "LLM" not in result and len(result) <= 280
    assert "My focus" not in _fallback_message({}, {}, "en")


def test_unknown_swiss_work_permission_never_reaches_ai(profile_files, monkeypatch):
    from app.apply import screening
    from app.models.job import Job

    write_profile(candidate())
    monkeypatch.setattr(screening, "complete", lambda **_: pytest.fail("Unknown permission must stay unanswered"))
    job = Job(title="Data Analyst", company="Example", location="Zürich, Switzerland")
    assert screening.answer_question(None, job, "Do you have the right to work in Switzerland?", ["Yes", "No"]) == {"answer": "", "cached": False}
    assert screening.answer_question(None, job, "Will you require visa sponsorship?", ["Yes", "No"]) == {"answer": "", "cached": False}


def test_preparations_do_not_overwrite_other_roles_or_earlier_documents(profile_files, monkeypatch):
    import asyncio

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from starlette.requests import Request

    from app.api import jobs
    from app.db import Base
    from app.models.job import Job

    monkeypatch.setattr(settings, "data_dir", str(profile_files / "data"))
    monkeypatch.setattr(settings, "cvs_out_dir", "")
    monkeypatch.setattr(jobs, "load_cv_master", candidate)

    def make_cv(_cv, job, folder, _language):
        path = folder / "cv.pdf"
        path.write_text(job["title"])
        return path, job["title"], "en"

    def make_cover(_cv, job, _hooks, folder, _language):
        path = folder / "cover.pdf"
        path.write_text(job["title"])
        return path, job["title"]

    monkeypatch.setattr(jobs, "generate_cv", make_cv)
    monkeypatch.setattr(jobs, "generate_cover_letter", make_cover)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a = Job(source="test", source_url="https://example.test/a", hash="a", title="Data Engineer", company="Same Company")
        b = Job(source="test", source_url="https://example.test/b", hash="b", title="Data Analyst", company="Same Company")
        db.add_all([a, b])
        db.commit()
        paths = []
        for job in [a, b, a]:
            result = asyncio.run(jobs.prepare_application.__wrapped__(Request({"type": "http"}), job.id, db))
            paths.append(Path(result.cv_path))
        assert len(set(paths)) == 3
        assert [path.read_text() for path in paths] == ["Data Engineer", "Data Analyst", "Data Engineer"]
        jobs.delete_job(a.id, db)
        assert paths[1].read_text() == "Data Analyst"
        assert not paths[0].exists() and not paths[2].exists()


def test_missing_document_never_resolves_to_another_job_at_same_company(profile_files, monkeypatch):
    from app.api.jobs import _resolve_pdf_path
    from app.models.job import Job

    monkeypatch.setattr(settings, "data_dir", str(profile_files / "data"))
    other = settings.data_path / "applications" / "same-company" / "cv.pdf"
    other.parent.mkdir(parents=True)
    other.write_text("Another application's CV")
    job = Job(id=77, company="Same Company", cv_path=str(profile_files / "missing.pdf"))
    assert _resolve_pdf_path(job.cv_path, job, "cv", None) is None
    assert other.read_text() == "Another application's CV"


def test_today_counts_only_current_target_jobs(profile_files, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.api import metrics
    from app.db import Base
    from app.models.job import Job

    monkeypatch.setattr(metrics, "load_cv_master", candidate)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for country in ["Switzerland", "Netherlands"]:
            db.add(Job(source="test", source_url="https://example.test", hash=country, title="Data Engineer", company="Example", location=country, match_score=85))
        db.commit()
        result = metrics.today_metrics(db)
        assert result.today.new_jobs == 1
        assert result.today.jobs_above_70 == 1


def test_management_role_does_not_match_junior_target():
    from app.scoring.compatibility import job_compatibility

    assert job_compatibility({"title": "Data Analytics Manager", "location": "Switzerland"}, {"regions": ["CH"], "seniority": "junior"})["seniority_compatible"] is False


def test_swiss_posting_language_phrases_preserve_beginner_boundary():
    from app.scoring.compatibility import language_mismatches

    cv = candidate()
    cv["languages"] = [{"name": "German", "level": "Beginner"}]
    for phrase in ["Du verfügst über sehr gute Deutsch- und Englischkenntnisse.", "Sichere Deutsch- und Englischkenntnisse für den Arbeitsalltag."]:
        gaps = language_mismatches({"description": phrase}, cv)
        assert any("German" in gap for gap in gaps)
    assert not language_mismatches({"description": "Gute Deutschkenntnisse sind von Vorteil."}, cv)


def test_ai_scoring_cap_leaves_honest_usable_estimates(profile_files, monkeypatch):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app import services
    from app.db import Base
    from app.models.job import Job
    from app.schemas.job import ScoredJobResult, ScrapedJob

    write_profile(candidate())
    monkeypatch.setattr(settings, "max_scored_jobs_per_run", 1)
    calls = []
    def score(_db, job, _cv):
        calls.append(job.hash)
        return ScoredJobResult(match_score=82)
    monkeypatch.setattr(services, "score_job", score)
    source = [ScrapedJob(source="test", source_url="https://example.test/" + key, hash=key, title="Data Engineer", company="Example", location="Switzerland", description="Data pipelines and SQL validation. " * 4) for key in ["first", "second"]]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert services.ingest_scraped_jobs(db, source) == (2, 0)
        second = db.scalar(select(Job).where(Job.hash == "second"))
        assert calls == ["first"]
        assert second.match_score > 0 and "Heuristic fit estimate" in second.rejection_reason
