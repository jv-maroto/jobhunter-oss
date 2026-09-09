from __future__ import annotations

from copy import deepcopy

import pytest

from app.schemas.job import ScoredJobResult
from app.scoring.compatibility import constrain_score
from app.scoring.prompts import build_scoring_user_prompt
from app.scoring.qualification_assessment import assess_qualifications
from app.scoring.scorer import _heuristic_result

CV = {
    "education": [{"degree": "Bachelor's degree in Analytics", "completed": True}],
    "experience": [
        {"role": "Data Engineer Intern", "domain": "data engineering", "start": "2024-09", "end": "2025-07", "highlights": ["Python and SQL data pipelines"]},
        {"role": "Emergency Coordinator", "start": "2010-01", "end": "2025-01"},
    ],
    "skills": {"professional": ["Python", "SQL", "Docker", "pandas"], "academic": ["PyTorch", "TensorFlow", "scikit-learn", "R", "machine learning"]},
    "languages": [{"name": "German", "level": "Currently learning"}],
    "search_preferences": {"roles": ["Data Scientist", "Data Engineer"], "regions": ["DE"], "seniority": "junior", "employment_types": ["permanent"]},
}


def posting(description):
    return {"title": "Data Scientist", "location": "Berlin, Germany", "employment_type": "permanent", "description": description}


def test_job_location_and_contract_are_not_candidate_skills():
    result = assess_qualifications(posting("Requirements:\nPython required.\nPermanent Data Engineer role in Toronto, Canada.\nLocation: Toronto, Canada"), CV)
    assert result["recommendation"] == "strong"
    assert len(result["checks"]) == 1
    assert result["checks"][0]["status"] == "met"


def test_mandatory_postgraduate_and_specialist_experience_prevent_inflated_fit():
    job = posting("Requirements: MSc or PhD required; minimum 3 years of professional multiomics experience required. Python, SQL, Docker, pandas, PyTorch, TensorFlow, scikit-learn, R and machine learning.")
    result = assess_qualifications(job, CV)
    assert result["recommendation"] == "unlikely"
    assert any(check["kind"] == "education" and check["status"] == "gap" for check in result["checks"])
    assert any(check["kind"] == "experience" and check["status"] == "unknown" for check in result["checks"])
    assert constrain_score(ScoredJobResult(match_score=99), job, CV).match_score < 30


def test_production_mlops_is_not_established_by_academic_or_skill_evidence():
    cv = deepcopy(CV)
    cv["skills"]["academic"] += ["MLOps", "Kubernetes", "Terraform"]
    cv["projects"] = [{"name": "MLOps coursework", "context": "academic", "description": "Production MLOps prototype using Kubernetes and Terraform"}]
    job = posting("Proven production MLOps experience, Kubernetes and Terraform are required.")
    result = assess_qualifications(job, cv)
    assert result["recommendation"] == "stretch"
    assert next(check for check in result["checks"] if check["kind"] == "experience")["status"] == "unknown"
    assert constrain_score(ScoredJobResult(match_score=99), job, cv).match_score <= 54
    cv["experience"].append({"role": "MLOps Engineer", "highlights": ["Operated production MLOps services with Kubernetes and Terraform"]})
    assert next(check for check in assess_qualifications(job, cv)["checks"] if check["kind"] == "experience")["status"] == "met"


@pytest.mark.parametrize("description,status,score", [
    ("MSc required.", "gap", 29),
    ("MSc or PhD or equivalent experience required.", "unknown", 54),
    ("MSc preferred.", "gap", 92),
    ("MSc is not required.", None, 92),
    ("No MSc required.", None, 92),
])
def test_degree_requirement_alternatives_preferences_and_negations(description, status, score):
    job = posting(description)
    checks = [check for check in assess_qualifications(job, CV)["checks"] if check["kind"] == "education"]
    assert ([check["status"] for check in checks] or [None]) == [status]
    assert constrain_score(ScoredJobResult(match_score=92), job, CV).match_score == score


def test_mixed_requirement_scopes_and_unknown_skills():
    job = posting("MSc required, Python preferred. SQL required, Kubernetes optional. Terraform is not required.")
    checks = assess_qualifications(job, CV)["checks"]
    assert any(check["kind"] == "education" and check["importance"] == "required" and check["status"] == "gap" for check in checks)
    assert any(check["requirement"].startswith("Kubernetes") and check["importance"] == "preferred" for check in checks)
    assert not any("Terraform" in check["requirement"] for check in checks)
    missing = assess_qualifications(posting("Kubernetes required."), CV)["checks"]
    assert missing[0]["status"] == "unknown" and missing[0]["evidence"] is None
    alternative = assess_qualifications(posting("Python or Rust required."), CV)
    assert alternative["recommendation"] == "strong" and alternative["checks"][0]["status"] == "met"


def test_relevant_years_exclude_unrelated_work_and_overlapping_roles():
    job = posting("Minimum 3 years of data engineering experience required.")
    check = next(check for check in assess_qualifications(job, CV)["checks"] if check["kind"] == "experience")
    assert check["status"] == "gap" and "0.8 documented years" in check["evidence"]
    cv = deepcopy(CV)
    cv["experience"] = [{"role": "Data Engineer", "start": "2020-01", "end": "2022-01"}] * 2
    check = assess_qualifications(job, cv)["checks"][0]
    assert check["status"] == "gap" and "2.0 documented years" in check["evidence"]
    cv["experience"] = [{"role": "Data Engineer", "start": "2020-01"}]
    assert assess_qualifications(job, cv)["checks"][0]["status"] == "unknown"
    cv["experience"] = [{"role": "Academic Data Engineer", "start": "2010-01", "end": "2025-01"}]
    assert assess_qualifications(job, cv)["checks"][0]["status"] == "unknown"


def test_degree_field_and_completion_need_evidence():
    cv = {"education": [{"degree": "Master's degree in Computer Science", "completed": True}]}
    assert assess_qualifications(posting("Master's degree in Computer Science required."), cv)["checks"][0]["status"] == "met"
    assert assess_qualifications(posting("Master's degree in Chemistry required."), cv)["checks"][0]["status"] == "unknown"
    equivalent = assess_qualifications(posting("MSc or equivalent experience required."), cv)
    assert equivalent["recommendation"] == "strong" and len(equivalent["checks"]) == 1
    cv["education"][0]["completed"] = False
    assert assess_qualifications(posting("MSc required."), cv)["checks"][0]["status"] == "unknown"


@pytest.mark.parametrize("description,experience", [
    ("Production MLOps experience required.", {"role": "Data Analyst", "highlights": ["Production reporting; no MLOps experience."]}),
    ("Three years of MLOps experience required.", {"role": "MLOps Engineer", "start": "2050-01", "end": "2053-01"}),
    ("Production experience of at least three years in MLOps required.", {"role": "MLOps Researcher", "start": "2020-01", "end": "2024-01", "highlights": ["Local experiments only; no production deployments."]}),
    ("Production MLOps experience required.", {"role": "Data Analyst", "company": "Production MLOps Inc"}),
])
def test_negated_production_and_future_work_do_not_satisfy_experience(description, experience):
    result = assess_qualifications(posting(description), {"experience": [experience]})
    assert result["recommendation"] == "stretch"
    assert next(check for check in result["checks"] if check["kind"] == "experience")["status"] == "unknown"


def test_unconfirmed_skill_groups_are_not_claimed_as_matches():
    result = assess_qualifications(posting("Kubernetes required."), {"skills": {"Unconfirmed tools": ["Kubernetes"]}})
    assert result["checks"][0]["status"] == "unknown"


def test_headings_and_nontechnical_profiles_follow_the_same_contract():
    cv = {"skills": {"professional": ["Wound care", "Patient assessment"]}}
    job = {"title": "Nurse", "description": "Requirements:\nWound care and patient assessment\nPreferred qualifications:\nMedical coding"}
    result = assess_qualifications(job, cv)
    assert result["recommendation"] == "consider"
    assert len([check for check in result["checks"] if check["importance"] == "required" and check["status"] == "met"]) == 2
    for check in result["checks"]:
        assert set(check) == {"kind", "importance", "status", "requirement", "evidence"}
        assert check["requirement"] in job["description"]
    assert assess_qualifications({"description": "About our company."}, {})["recommendation"] == "unknown"


def test_language_scopes_are_not_duplicated_as_skills():
    result = assess_qualifications(posting("Fluent German is required, French is a plus."), CV)
    assert result["recommendation"] == "stretch"
    assert all(check["kind"] == "language" for check in result["checks"])
    assert assess_qualifications(posting("Fluent German is not required."), CV)["checks"] == []


def test_formatted_skillset_and_language_wording_preserve_requirement_scope():
    cv = deepcopy(CV)
    cv["languages"] = [{"name": "English", "level": "Professional working proficiency"},
                       {"name": "German", "level": "Currently learning"}]
    description = "**Your Skillset**\n* MSc/PhD or equivalent\n* Proven experience with production\\-grade MLOps.\n* Proficiency in English required, basic German skills advantageous"
    result = assess_qualifications(posting(description), cv)
    education = next(check for check in result["checks"] if check["kind"] == "education")
    experience = next(check for check in result["checks"] if check["kind"] == "experience")
    languages = [check for check in result["checks"] if check["kind"] == "language"]
    assert (education["importance"], education["status"]) == ("required", "unknown")
    assert (experience["importance"], experience["status"]) == ("required", "unknown")
    assert [(check["importance"], check["status"]) for check in languages] == [("required", "met"), ("preferred", "unknown")]
    assert languages[0]["evidence"] == "English: Professional working proficiency"
    assert result["recommendation"] == "stretch"
    assert all(check["requirement"] in description for check in result["checks"])
    cv["experience"].append({"role": "MLOps Engineer", "highlights": ["Operated production MLOps services"]})
    assert next(check for check in assess_qualifications(posting(description), cv)["checks"] if check["kind"] == "experience")["status"] == "met"


def test_complete_posting_reaches_model_and_heuristics_stay_labelled():
    description = "Company culture and background. " * 250 + "Qualifications: MSc required."
    assert description in build_scoring_user_prompt({}, posting(description))
    job = posting("Requirements: Python, SQL, Docker, pandas, PyTorch, TensorFlow, scikit-learn, R and machine learning. MSc required.")
    result = _heuristic_result(job, CV)
    assert result.match_score <= 54 and result.rejection_reason.startswith("Heuristic fit estimate")
    constrained = constrain_score(result, job, CV)
    assert constrained.match_score == result.match_score
    assert constrained.rejection_reason.startswith("Heuristic fit estimate")
    assert _heuristic_result(posting("Python SQL Docker pandas PyTorch TensorFlow scikit-learn machine learning " * 3), CV).match_score <= 54


def test_precomputed_assessment_is_reused_without_changing_guards(monkeypatch):
    job = posting("MSc required. SQL and Python required.")
    assessment = assess_qualifications(job, CV)
    expected = _heuristic_result(job, CV)
    monkeypatch.setattr("app.scoring.qualification_assessment.assess_qualifications",
                        lambda *_: pytest.fail("The provided assessment must be reused"))
    assert _heuristic_result(job, CV, assessment=assessment) == expected
    assert constrain_score(ScoredJobResult(match_score=99), job, CV, assessment=assessment).match_score < 30


def test_normalization_cache_does_not_cache_profile_or_posting_assessments():
    from app.scoring.qualification_assessment import _norm

    assert _norm(["École"]) == "['ecole']"
    cv = {"skills": {"professional": ["SQL"]}}
    job = posting("SQL required.")
    assert assess_qualifications(job, cv)["checks"][0]["status"] == "met"
    cv["skills"]["professional"] = ["Python"]
    assert assess_qualifications(job, cv)["checks"][0]["status"] == "unknown"
    job["description"] = "Python required."
    assert assess_qualifications(job, cv)["checks"][0]["status"] == "met"
