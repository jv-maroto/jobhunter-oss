"""Mapa pais/region -> parametros de busqueda (jobspy y otros).

`COUNTRY_MAP` usa codigos ISO-3166-1 alpha-2 como clave. El valor `indeed`
DEBE coincidir EXACTAMENTE con los nombres que acepta python-jobspy
(`country_indeed`): ojo con "UK" (no "United Kingdom") y "USA" (no
"United States"). Pseudo-regiones: "EU" (se expande a la lista EEA) y
"REMOTE" (sin pais, activa boards remotos).
"""

from __future__ import annotations

# ISO alpha-2 -> {indeed: nombre exacto jobspy, location: location por defecto}
COUNTRY_MAP: dict[str, dict[str, str]] = {
    "ES": {"indeed": "Spain", "location": "Spain"},
    "DE": {"indeed": "Germany", "location": "Germany"},
    "FR": {"indeed": "France", "location": "France"},
    "SE": {"indeed": "Sweden", "location": "Sweden"},
    "GB": {"indeed": "UK", "location": "United Kingdom"},
    "IE": {"indeed": "Ireland", "location": "Ireland"},
    "NL": {"indeed": "Netherlands", "location": "Netherlands"},
    "IT": {"indeed": "Italy", "location": "Italy"},
    "PT": {"indeed": "Portugal", "location": "Portugal"},
    "BE": {"indeed": "Belgium", "location": "Belgium"},
    "AT": {"indeed": "Austria", "location": "Austria"},
    "CH": {"indeed": "Switzerland", "location": "Switzerland"},
    "PL": {"indeed": "Poland", "location": "Poland"},
    "DK": {"indeed": "Denmark", "location": "Denmark"},
    "NO": {"indeed": "Norway", "location": "Norway"},
    "FI": {"indeed": "Finland", "location": "Finland"},
}

# Region EEA / "toda Europa" para el preset all_europe.
EU_COUNTRIES: list[str] = [
    "ES", "DE", "FR", "SE", "GB", "IE", "NL", "IT", "PT",
    "BE", "AT", "CH", "PL", "DK", "NO", "FI",
]

REGION_PRESETS: dict[str, list[str]] = {
    "all_europe": EU_COUNTRIES,
    "only_spain": ["ES"],
    "remote_worldwide": ["REMOTE"],
}

# Mapeo de la clave legacy `preferred_countries` -> regions.
_LEGACY_REGION_MAP = {
    "ES": ["ES"],
    "EU": ["EU"],
    "REMOTE": ["REMOTE"],
    "REMOTO": ["REMOTE"],
}


def resolve_regions(prefs: dict | None) -> list[str]:
    """Devuelve la lista efectiva de regiones (ISO + pseudo "REMOTE") a buscar.

    Prioridad: regions explicitas > region_preset > preferred_countries (legacy).
    "EU" se expande a EU_COUNTRIES. Se deduplica conservando el orden.
    """
    prefs = prefs or {}
    raw: list[str] = []

    regions = prefs.get("regions")
    preset = prefs.get("region_preset")
    if regions:
        raw = list(regions)
    elif preset and preset in REGION_PRESETS:
        raw = list(REGION_PRESETS[preset])
    else:
        for c in prefs.get("preferred_countries", []) or []:
            raw.extend(_LEGACY_REGION_MAP.get(str(c).upper(), [str(c).upper()]))

    # Expandir EU y deduplicar.
    expanded: list[str] = []
    for r in raw:
        ru = str(r).upper()
        if ru == "EU":
            expanded.extend(EU_COUNTRIES)
        else:
            expanded.append(ru)

    seen: set[str] = set()
    out: list[str] = []
    for r in expanded:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out


def jobspy_params_for(region: str) -> dict | None:
    """Devuelve {location, country_indeed} para una region jobspy, o None si no aplica."""
    if region == "REMOTE":
        return None
    info = COUNTRY_MAP.get(region.upper())
    if not info:
        return None
    return {"location": info["location"], "country_indeed": info["indeed"]}
