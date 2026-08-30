"""Seleccion de scrapers a partir del perfil."""

from __future__ import annotations

from app.scrapers import ALL_SCRAPERS
from app.scrapers.registry import _home_country, active_platforms, build_active_scrapers


def test_template_prefs_use_legacy_set() -> None:
    prefs = {"preferred_countries": ["ES", "EU", "Remote"]}
    instances = build_active_scrapers({}, prefs)
    assert len(instances) == len(ALL_SCRAPERS)


def test_dynamic_prefs_pick_from_catalog() -> None:
    prefs = {"regions": ["ES"], "roles": ["Backend Developer"]}
    ids = {p["id"] for p in active_platforms(prefs, ["ES"])}
    assert "tecnoempleo" in ids
    assert "linkedin" in ids
    assert "indeed" in ids
    # Glassdoor devuelve 400 con jobspy: no debe activarse por defecto.
    assert "glassdoor" not in ids
    # Adzuna necesita clave: sin ADZUNA_APP_ID se autodesactiva.
    assert "adzuna" not in ids

    instances = build_active_scrapers({"skills": {"backend": ["Python"]}}, prefs)
    names = {inst.name for inst in instances}
    assert "tecnoempleo" in names
    assert "jobspy" in names


def test_home_country_resolves_to_jobspy_names() -> None:
    assert _home_country({}, ["DE"]) == "Germany"
    assert _home_country({}, ["GB"]) == "UK"
    assert _home_country({"personal": {"location": "Sevilla, España"}}, ["REMOTE"]) == "Spain"
