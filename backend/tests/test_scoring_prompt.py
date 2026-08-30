"""El prompt de scoring sale del perfil del usuario, no de una persona concreta."""

from __future__ import annotations

from app.scoring.prompts import SCORING_SYSTEM, build_scoring_system, infer_seniority


def test_generic_prompt_has_no_hardcoded_person() -> None:
    for leftover in ("Canarias", "28K", "FastAPI", "sysadmin con dev", "junior/mid"):
        assert leftover not in SCORING_SYSTEM
    assert "match_score" in SCORING_SYSTEM
    assert "Return ONLY valid JSON" in SCORING_SYSTEM


def test_prompt_reflects_profile_preferences() -> None:
    cv = {
        "personal": {"location": "Berlin, Germany"},
        "languages": [{"name": "German", "level": "C1"}, {"name": "English", "level": "C2"}],
        "skills": {"backend": ["Java", "Spring Boot"], "cloud": ["AWS"]},
        "search_preferences": {
            "salary_min_eur": 55000,
            "regions": ["DE", "REMOTE"],
            "remote_only": True,
            "seniority": "senior",
            "roles": ["Backend Engineer"],
            "exclude_keywords": ["PHP"],
        },
    }
    prompt = build_scoring_system(cv)
    assert "55000 EUR" in prompt
    assert "DE, remote worldwide" in prompt
    assert "REMOTE work only" in prompt
    assert "Berlin, Germany" in prompt
    assert "senior (5-9 years)" in prompt
    assert "Java, Spring Boot, AWS" in prompt
    assert "Backend Engineer" in prompt
    assert "PHP" in prompt
    assert "German (C1)" in prompt


def test_seniority_inferred_from_experience() -> None:
    assert infer_seniority({}) == "junior"
    assert infer_seniority({"experience": [{"start": "2020-01", "end": "2021-06"}]}) == "junior"
    assert infer_seniority({"experience": [{"start": "2018-01", "end": "2021-06"}]}) == "mid"
    assert infer_seniority({"experience": [{"start": "2010-01", "end": "2020-06"}]}) == "lead"
    assert infer_seniority({"search_preferences": {"seniority": "mid"}}) == "mid"
