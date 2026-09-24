from copy import deepcopy

from app.career.normalization import normalize_profile
from app.scoring.qualification_assessment import assess_qualifications


def checks(description, cv):
    return assess_qualifications({"description": description}, cv)["checks"]


def test_lossless_bilingual_view_is_idempotent_and_does_not_mutate_input():
    profile = {"education": [{"degree_es": "Técnico Superior", "degree_en": "Vocational diploma"}],
               "experience": [{"highlights_es": ["Automatización"], "highlights_en": ["Automation"]}],
               "custom": {"source": "cv", "verified": False}}
    before = deepcopy(profile)
    view = normalize_profile(profile)
    assert profile == before
    assert view["education"][0]["degree"] == "Vocational diploma"
    assert view["experience"][0]["highlights_es"] == ["Automatización"]
    assert view["custom"] == before["custom"]
    assert view["_normalization"]["conflicts"] == []
    assert view == normalize_profile(view)
    assert {"path": "education[0].degree", "source_path": "education[0].degree_en"} in view["_normalization"]["provenance"]


def test_bilingual_vocational_qualification_is_read_without_becoming_bachelor():
    cv = {"education": [{"degree_es": "Técnico Superior", "degree_en": "Vocational diploma"}]}
    assert checks("Vocational diploma required.", cv)[0]["status"] == "met"
    assert checks("Bachelor's degree required.", cv)[0]["status"] == "gap"


def test_contradictory_degrees_and_course_labels_are_not_promoted():
    cv = {"education": [{"degree_en": "Bachelor's degree", "degree_es": "Técnico Superior"}]}
    assert normalize_profile(cv)["_normalization"]["conflicts"]
    assert checks("Bachelor's degree required.", cv)[0]["status"] == "unknown"
    assert checks("Master's degree required.", {"education": [{"degree_en": "Master course in Python"}]})[0]["status"] == "unknown"


def test_all_highlight_variants_are_read_and_academic_work_stays_academic():
    entry = {"role": "Engineer", "highlights": ["Reporting"], "highlights_en": ["Operated production MLOps"]}
    assert checks("Production MLOps experience required.", {"experience": [entry]})[0]["status"] == "met"
    entry["context_es"] = "Proyecto académico"
    assert checks("Production MLOps experience required.", {"experience": [entry]})[0]["status"] == "unknown"


def test_conflicting_dates_do_not_create_years_of_experience():
    cv = {"experience": [{"role_en": "Data Engineer", "start_en": "2020-01", "start_es": "2024-01", "end": "2025-01"}]}
    assert checks("Minimum 3 years of data engineering experience required.", cv)[0]["status"] == "unknown"
