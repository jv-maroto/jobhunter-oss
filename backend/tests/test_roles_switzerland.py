from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.job import Job, ScoreCache
from app.schemas.job import JobOut, ScoredJobResult, ScrapedJob
from app.schemas.search import SearchProfileIn
from app.scoring.compatibility import constrain_score, job_compatibility
from app.scoring.scorer import _heuristic_result, score_job
from app.scoring.track_detector import detect_track, predict_salary_band
from app.scrapers.country_map import resolve_regions
from app.scrapers.jobspy_scraper import JobspyScraper
from app.scrapers.query_builder import build_search_queries
from app.scrapers.registry import active_platforms, build_jobspy_plans

ROLES = {
    "Data Engineer": "data_engineer",
    "Data Analyst": "data_analyst",
    "Data Scientist": "data_scientist",
    "Analytics Engineer": "analytics_eng",
    "BI Developer": "bi",
    "AI / ML Engineer": "ai_ml",
    "Quantitative Researcher": "quant",
    "Software Developer": "dev",
    "DevOps Engineer": "sysadmin",
}
PREFS = {"region_preset": "only_switzerland", "roles": list(ROLES)[:7], "max_queries": 2}


@pytest.mark.parametrize("title,expected", ROLES.items())
def test_role_classification(title, expected):
    assert detect_track(title, "Python, SQL, Terraform, React", ["devops engineer"]) == expected


def test_all_selected_roles_survive_query_and_plan_limits():
    queries = build_search_queries({"experience": [{"role": "Legacy Developer"}], "skills": {"data": ["SQL"]}}, PREFS)
    assert queries == list(ROLES)[:7]
    assert resolve_regions(PREFS) == ["CH"]
    active = {p["id"] for p in active_platforms(PREFS, ["CH"])}
    assert {"linkedin", "indeed"} <= active
    assert "tecnoempleo" not in active
    plans = build_jobspy_plans(["CH"], queries, ["linkedin", "indeed"], PREFS)
    assert len(plans) == 1
    assert plans[0].country_indeed == "Switzerland"
    assert plans[0].queries == queries
    assert not plans[0].is_remote
    assert build_jobspy_plans(["CH"], queries, ["linkedin"], {"remote_only": True})[0].is_remote
    assert build_search_queries({}, {"queries_auto": False, "queries": queries, "max_queries": 2}) == queries


@pytest.mark.parametrize("location,remote,description,expected", [
    ("Zürich, Schweiz", False, "", True),
    ("Geneva, Switzerland", True, "", True),
    ("Lausanne, Suisse", False, "", True),
    ("Lugano, Svizzera", False, "", True),
    ("Biel/Bienne", False, "", True),
    ("St. Gallen", False, "", True),
    ("Geneva, IL, USA", False, "", False),
    ("Zurich, Kansas, USA", False, "", False),
    ("Remote", True, "Remote from Switzerland.", True),
    ("Remote", True, "Work from CH.", True),
    ("Worldwide", True, "", True),
    ("Remote", True, "We have an office in Switzerland.", None),
    ("Remote", True, "We are based in Switzerland.", None),
    ("Remote", True, "We serve clients worldwide.", None),
    ("Remote", True, "Work from anywhere.", True),
    ("Remote", True, "Fully remote worldwide.", True),
    ("Remote", True, "", None),
    ("Berlin, Germany", False, "", False),
    ("Remote - USA", True, "", False),
    ("Remote", True, "EU-only remote role.", False),
    ("Remote", True, "EU-only remote role. We have a Switzerland office.", False),
    ("Switzerland", True, "Must be based in US.", False),
    ("Switzerland", True, "Applicants must reside in Germany.", False),
    ("Switzerland", True, "Remote in USA only.", False),
    ("Worldwide", True, "Not available in Switzerland.", False),
    ("Worldwide", True, "Switzerland is not eligible.", False),
    ("Worldwide", True, "Candidates must be authorized to work in USA.", False),
])
def test_swiss_geographic_eligibility(location, remote, description, expected):
    job = {"location": location, "remote": remote, "description": description}
    assert job_compatibility(job, PREFS)["location_compatible"] is expected
    scored = constrain_score(ScoredJobResult(match_score=99, location_compatible=True), job, {"search_preferences": PREFS})
    assert scored.location_compatible is expected
    if expected is not True:
        assert scored.match_score < 55


def test_currency_and_pay_period_never_assume_fx_or_annual_hours():
    prefs = {**PREFS, "salary_min": 90000, "salary_max": 120000, "salary_currency": "CHF"}
    base = {"salary_min": 100000, "salary_max": 130000, "currency": "CHF", "salary_period": "year"}
    assert job_compatibility(base, prefs)["salary_in_range"] is True
    assert predict_salary_band("Data Engineer", salary_max=130000, currency="CHF", salary_period="year", prefs=prefs) == "high"
    for replacement in ({"currency": "EUR"}, {"salary_period": "hour"}, {"salary_period": None}, {"currency": None}):
        assert job_compatibility({**base, **replacement}, prefs)["salary_in_range"] is None
    assert predict_salary_band("Senior Engineer", company="Google", location="Zurich") == "unknown"


def test_jobspy_preserves_currency_period_and_missing_values():
    frame = pd.DataFrame([
        {"title": "Data Engineer", "company": "Example", "location": "Zurich, Switzerland", "job_url": "https://example.org/1", "is_remote": float("nan"), "min_amount": float("nan"), "max_amount": float("nan"), "currency": float("nan")},
        {"title": "BI Developer", "company": "Example", "location": "Switzerland", "job_url": "https://example.org/2", "is_remote": True, "min_amount": 90, "max_amount": 110, "currency": "CHF", "interval": "hourly"},
    ])
    plans = build_jobspy_plans(["CH"], ["Data Engineer"], ["google", "indeed"], {"remote_only": True})
    with patch("jobspy.scrape_jobs", return_value=frame) as scrape:
        jobs = JobspyScraper(plans)._fetch_sync()
    assert "Switzerland" in scrape.call_args.kwargs["google_search_term"]
    assert "hours_old" not in scrape.call_args.kwargs
    assert not jobs[0].remote and jobs[0].salary_min is None and jobs[0].currency is None
    assert jobs[1].salary_period == "hour" and jobs[1].currency == "CHF" and jobs[1].salary_max == 110


def test_score_cache_depends_on_cv_preferences_and_posting_content():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    job = {"hash": "job-1", "title": "Data Engineer", "location": "Zurich, Switzerland", "description": "SQL Python"}
    cv = {"skills": {"data": ["SQL"]}, "search_preferences": PREFS}
    router = SimpleNamespace(available_providers=lambda tier: [])
    with Session(engine) as db, patch("app.scoring.scorer.get_router", return_value=router):
        first = score_job(db, job, cv)
        assert score_job(db, job, cv) == first
        second = score_job(db, job, {**cv, "skills": {"data": ["SQL", "Python"]}})
        assert second.match_score > first.match_score
        changed = score_job(db, {**job, "location": "USA"}, cv)
        assert changed.location_compatible is False
        moved = score_job(db, job, {**cv, "search_preferences": {"regions": ["ES"]}})
        assert moved.location_compatible is False
        assert db.scalar(select(func.count()).select_from(ScoreCache)) == 4


def test_heuristic_rejects_foreign_remote_and_does_not_match_single_letters():
    cv = {"skills": {"data": ["R", "C"]}, "search_preferences": PREFS}
    scored = _heuristic_result({"title": "Data Engineer", "description": "Remote cloud", "location": "US", "remote": True}, cv)
    assert scored.location_compatible is False
    assert not {"r", "c"} & set(scored.key_matches)


def test_ingestion_gates_geography_before_ai_and_exposes_salary_period():
    from app.services import ingest_scraped_jobs
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    jobs = [ScrapedJob(source="test", source_url="https://example.org", hash=str(i), title="Data Engineer", company="Example", location=loc, remote=True, salary_max=120000, currency="CHF", salary_period="year") for i, loc in enumerate(["Switzerland", "Remote", "USA"])]
    with Session(engine) as db, patch("app.services.load_cv_master", return_value={"search_preferences": PREFS}), patch("app.services.score_job", return_value=ScoredJobResult(match_score=90)) as scorer:
        assert ingest_scraped_jobs(db, jobs) == (1, 0)
        assert scorer.call_count == 1
        saved = db.scalar(select(Job))
        out = JobOut.model_validate(saved)
        assert out.track == "data_engineer" and out.location_compatible is True
        assert out.salary_period == "year" and out.currency == "CHF"


def test_search_profile_validation():
    assert SearchProfileIn(roles=["Data Engineer", "data engineer"], regions=["ch"]).roles == ["Data Engineer"]
    for data in ({"salary_min": 120000, "salary_max": 100000}, {"max_queries": 0}, {"regions": ["XX"]}, {"salary_currency": "dollars"}):
        with pytest.raises(ValidationError):
            SearchProfileIn(**data)


def test_country_filter_reports_excluded_and_unknown_jobs():
    from app.services import filter_scraped_jobs
    jobs = [ScrapedJob(source="test", source_url="https://example.org", title="Data Engineer", company="Example", location=loc, remote=remote) for loc, remote in [("Switzerland", True), ("USA", True), ("Remote", True), ("Switzerland", False)]]
    kept, counts = filter_scraped_jobs(jobs, {**PREFS, "remote_only": True})
    assert kept == jobs[:1]
    assert counts == {"filtered_geography": 1, "unconfirmed_geography": 1, "filtered_remote": 1, "filtered_employment": 0, "filtered_seniority": 0}


def test_swipe_defaults_to_all_tracks_without_comparing_raw_currencies():
    from app.api.jobs import list_jobs, swipe_jobs
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, patch("app.api.jobs.load_cv_master", return_value={}):
        for i, (title, track) in enumerate(ROLES.items()):
            db.add(Job(source="test", source_url="https://example.org", hash=f"api-{i}", title=title, company="Example", track=track, match_score=80-i, salary_max=100+i, currency="CHF" if i % 2 else "EUR", salary_period="hour" if i % 2 else "year"))
        db.commit()
        all_jobs = swipe_jobs(track=None, remote_only=False, min_band=None, limit=40, db=db)
        assert {j.track for j in all_jobs} == set(ROLES.values())
        assert [j.match_score for j in all_jobs] == sorted((j.match_score for j in all_jobs), reverse=True)
        assert len(swipe_jobs(track="quant", remote_only=False, min_band=None, limit=40, db=db)) == 1
        assert list_jobs(status=None, min_score=None, source=None, track="all", limit=100, offset=0, db=db).total == len(ROLES)


def test_salary_period_migration_is_nullable_and_idempotent():
    from sqlalchemy import inspect, text

    from app.db import ensure_columns
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY, salary_max FLOAT, currency TEXT)"))
        conn.execute(text("INSERT INTO jobs VALUES (1, 100000, 'CHF')"))
    with patch("app.db.engine", engine):
        ensure_columns("jobs", {"salary_period": "VARCHAR(16)"})
        ensure_columns("jobs", {"salary_period": "VARCHAR(16)"})
    assert [c["name"] for c in inspect(engine).get_columns("jobs")].count("salary_period") == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT salary_period FROM jobs")).scalar() is None


@pytest.mark.parametrize("title,contract,description,employment_ok,seniority_ok", [
    ("Junior Data Engineer", "permanent", "", True, True),
    ("Graduate Data Analyst", "full_time", "", None, True),
    ("Data Scientist", None, "We mentor interns through each stage of development.", None, None),
    ("Intern Data Analyst", "full_time", "", False, None),
    ("Stage Data Scientist", None, "", False, None),
    ("Senior Data Engineer", "permanent", "", True, False),
    ("Junior BI Developer", "contract", "", False, True),
    ("AI Engineer", None, "Employment type: permanent", True, None),
    ("AI Engineer", "full_time", "Contract type: permanent", True, None),
])
def test_contract_and_seniority_only_use_explicit_evidence(title, contract, description, employment_ok, seniority_ok):
    job = {"title": title, "location": "Zurich, Switzerland", "employment_type": contract, "description": description}
    prefs = {**PREFS, "employment_types": ["permanent"], "seniority": "junior"}
    flags = job_compatibility(job, prefs)
    assert flags["employment_compatible"] is employment_ok
    assert flags["seniority_compatible"] is seniority_ok
    scored = constrain_score(ScoredJobResult(match_score=99), job, {"search_preferences": prefs})
    if employment_ok is False or seniority_ok is False:
        assert scored.match_score < 30


def test_keyword_exclusions_do_not_match_internal_as_intern():
    prefs = {**PREFS, "exclude_keywords": ["intern"]}
    result = constrain_score(ScoredJobResult(match_score=90), {"location": "Switzerland", "title": "Internal Data Engineer"}, {"search_preferences": prefs})
    assert result.match_score == 90


def test_cover_letter_uses_the_actual_cv_fallback_language(tmp_path):
    import asyncio

    from starlette.requests import Request

    from app.api.jobs import prepare_application
    from app.models.application import Application

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cv_pdf, cover_pdf = tmp_path / "cv.pdf", tmp_path / "cover.pdf"
    cv_pdf.write_bytes(b"%PDF-test")
    cover_pdf.write_bytes(b"%PDF-test")
    with Session(engine) as db:
        job = Job(source="test", source_url="https://example.org", hash="docs-lang", title="Data Engineer", company="Example", location="Switzerland", track="data_engineer")
        db.add(job)
        db.commit()
        with patch("app.api.jobs.load_cv_master", return_value={"personal": {"name": "Example"}}), patch("app.api.jobs._detect_language", return_value="de"), patch("app.api.jobs.generate_cv", return_value=(cv_pdf, "CV source", "en")), patch("app.api.jobs.generate_cover_letter", return_value=(cover_pdf, "Cover content")) as cover:
            result = asyncio.run(prepare_application.__wrapped__(Request({"type": "http"}), job.id, db))
        assert cover.call_args.args[-1] == "en"
        assert cover.call_args.args[1]["track"] == "data_engineer"
        assert result.language == "en"
        assert db.scalar(select(Application)).language == "en"


def test_scoring_requires_language_level_and_distinguishes_academic_work():
    from app.scoring.prompts import build_scoring_system
    cv = {"languages": [{"name": "German", "level": "Currently learning"}], "search_preferences": {**PREFS, "seniority": "junior"}, "skills": {"professional": ["SQL"], "academic": ["PyTorch"]}}
    job = {"location": "Switzerland", "description": "German C1 required. Python and SQL data pipelines."}
    result = constrain_score(ScoredJobResult(match_score=99), job, cv)
    assert result.match_score == 54 and "German C1" in result.rejection_reason
    beginner = {**cv, "languages": [{"name": "German", "level": "Beginner"}]}
    assert constrain_score(ScoredJobResult(match_score=99), job, beginner).match_score < 30
    optional = constrain_score(ScoredJobResult(match_score=80), {**job, "description": "German C1 is a plus."}, cv)
    assert optional.match_score == 80
    prompt = build_scoring_system(cv)
    assert "Target seniority" in prompt and "not a verified count" in prompt
    assert "degree project in ML does not establish professional production ML experience" in prompt
    assert "currently learning/basic German" in prompt
    assert "score MUST be at least 70" not in prompt
    assert "PyTorch" in prompt


def test_incomplete_heuristic_posting_is_not_scored_as_strong_fit():
    skills = ["SQL", "Python", "dbt", "Airflow", "Snowflake", "Spark", "Tableau"]
    cv = {"skills": {"data": skills}, "search_preferences": PREFS}
    job = {"title": "Data Engineer " + " ".join(skills), "description": "", "location": "Switzerland"}
    assert _heuristic_result(job, cv).match_score <= 54


def test_linkedin_fetch_requests_description_for_eligibility():
    plans = build_jobspy_plans(["CH"], ["Data Engineer"], ["linkedin"], {})
    with patch("jobspy.scrape_jobs", return_value=pd.DataFrame()) as scrape:
        assert JobspyScraper(plans)._fetch_sync() == []
    assert scrape.call_args.kwargs["linkedin_fetch_description"] is True
