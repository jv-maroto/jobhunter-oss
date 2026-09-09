from __future__ import annotations

import pytest

from app.schemas.job import ScoredJobResult
from app.scoring.compatibility import constrain_score, language_mismatches
from app.scoring.language_requirements import language_checks


@pytest.mark.parametrize("separator", [", ", " and ", "; ", " but "])
def test_language_requirement_is_local_to_its_clause(separator):
    description = f"Fluent German is required{separator}French is a plus."
    cv = {"languages": [{"name": "German", "level": "Beginner"}]}
    checks = language_checks({"description": description}, cv)
    assert checks[0] == {
        "kind": "language", "importance": "required", "status": "gap",
        "requirement": "Fluent German is required", "evidence": "German: Beginner",
    }
    assert checks[1]["importance"] == "preferred"
    assert checks[1]["status"] == "unknown"
    assert all(check["requirement"] in description for check in checks)


@pytest.mark.parametrize("description", [
    "Fluent German is not required.", "No German proficiency is required.",
    "German C1 is not a requirement.", "Gute Deutschkenntnisse sind nicht erforderlich.",
])
def test_negated_language_requirement_does_not_create_a_gap(description):
    cv = {"languages": [{"name": "German", "level": "A1"}]}
    assert language_checks({"description": description}, cv) == []
    assert language_mismatches({"description": description}, cv) == []


@pytest.mark.parametrize("level,status", [
    (None, "unknown"), ("", "unknown"), ("Unspecified", "unknown"),
    ("Currently learning", "unknown"), ("Basic", "gap"), ("B2", "gap"),
    ("Currently learning, basic A1", "gap"), ("C1, still learning", "met"),
    ("C1", "met"), ("Native", "met"),
])
def test_language_proficiency_uses_only_explicit_profile_evidence(level, status):
    cv = {"languages": [{"name": "German", "level": level}] if level is not None else []}
    job = {"description": "German C1 required."}
    check = language_checks(job, cv)[0]
    assert check["status"] == status
    assert bool(language_mismatches(job, cv)) is (status == "gap")


@pytest.mark.parametrize("english_level,english_status", [
    ("Professional working proficiency", "met"), ("", "unknown"), ("Beginner", "unknown"),
])
def test_general_proficiency_and_advantageous_learning_remain_distinct(english_level, english_status):
    description = "Proficiency in English required, basic German skills advantageous"
    checks = language_checks({"description": description}, {"languages": [
        {"name": "English", "level": english_level},
        {"name": "German", "level": "Currently learning"},
    ]})
    assert [(check["importance"], check["status"]) for check in checks] == [
        ("required", english_status), ("preferred", "unknown"),
    ]
    assert checks[0]["evidence"] == (f"English: {english_level}" if english_level else None)
    assert checks[1]["evidence"] == "German: Currently learning"


def test_multilingual_aliases_and_coordinated_levels_are_retained():
    job = {"description": "Sehr gute Deutsch- und Englischkenntnisse erforderlich."}
    cv = {"languages": [{"name": "Deutsch", "level": "A1"}, {"name": "Anglais", "level": "C1"}]}
    checks = language_checks(job, cv)
    assert [(check["evidence"], check["status"]) for check in checks] == [
        ("German: A1", "gap"), ("English: C1", "met"),
    ]
    assert language_checks({"description": "Français C1 obligatoire."}, {
        "languages": [{"name": "Frances", "level": "C1"}],
    })[0]["status"] == "met"


def test_each_language_keeps_its_own_level():
    checks = language_checks({"description": "German B2 and English C1 required."}, {
        "languages": [{"name": "German", "level": "B2"}, {"name": "English", "level": "B2"}],
    })
    assert [check["status"] for check in checks] == ["met", "gap"]


@pytest.mark.parametrize("description", [
    "French is a plus and fluent German is required.",
    "French C1 is not required and fluent German is required.",
])
def test_optional_or_negated_language_does_not_hide_following_requirement(description):
    checks = language_checks({"description": description}, {
        "languages": [{"name": "German", "level": "Basic"}],
    })
    assert checks[-1]["importance"] == "required"
    assert checks[-1]["status"] == "gap"
    assert checks[-1]["requirement"] == "fluent German is required"


def test_unlisted_language_requires_evidence_without_treating_code_as_a_language():
    for description in ["Fluent Japanese required.", "Japanese C1 required."]:
        checks = language_checks({"description": description}, {})
        assert len(checks) == 1
        assert checks[0]["status"] == "unknown"
        assert checks[0]["evidence"] is None
    assert language_checks({"description": "Proficient Python required. Fluent Python required."}, {}) == []


def test_supported_seniority_incompatibility_and_language_gap_cap_are_preserved():
    job = {"title": "Data Engineer", "description": "Five years of experience required."}
    result = constrain_score(ScoredJobResult(
        match_score=92, seniority_compatible=False, location_compatible=True,
    ), job, {})
    assert result.seniority_compatible is False
    assert result.location_compatible is None
    assert result.match_score == 29
    gap = constrain_score(ScoredJobResult(match_score=92), {"description": "German C1 required."}, {
        "languages": [{"name": "German", "level": "Beginner"}],
    })
    assert gap.match_score == 29
    assert "German C1" in gap.rejection_reason
