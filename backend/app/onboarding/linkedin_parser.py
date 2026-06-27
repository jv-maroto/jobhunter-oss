"""Parsing del export oficial de LinkedIn ("Get a copy of your data").

Via recomendada (sin riesgo de baneo): el usuario descarga su ZIP de datos y lo
sube. El archivo COMPLETO trae CSVs (Profile.csv, Positions.csv, Skills.csv,
Education.csv, Languages.csv, Certifications.csv); el export "rapido" trae menos
y se avisa. Tambien se acepta el payload que la extension lee del propio perfil.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from typing import Any

logger = logging.getLogger(__name__)


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    """Lee un CSV del ZIP por nombre (case-insensitive, ignora ruta)."""
    target = name.lower()
    for member in zf.namelist():
        base = member.split("/")[-1].lower()
        if base == target:
            with zf.open(member) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
                return list(csv.DictReader(text))
    return []


def _g(row: dict[str, str], *keys: str) -> str:
    """Primer valor no vacio entre varias posibles cabeceras."""
    for k in keys:
        for rk, rv in row.items():
            if rk and rk.strip().lower() == k.lower() and rv and rv.strip():
                return rv.strip()
    return ""


def parse_zip(data: bytes) -> dict[str, Any]:
    """Parsea el ZIP de export de LinkedIn -> ProfileFragment (dict)."""
    fragment: dict[str, Any] = {"source": "linkedin", "warnings": []}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No es un ZIP valido: {exc}") from exc

    profile_rows = _read_csv(zf, "Profile.csv")
    if profile_rows:
        p = profile_rows[0]
        first = _g(p, "First Name")
        last = _g(p, "Last Name")
        personal: dict[str, Any] = {}
        name = f"{first} {last}".strip()
        if name:
            personal["name"] = name
        geo = _g(p, "Geo Location", "Location")
        if geo:
            personal["location"] = geo
            personal["location_short"] = geo
        if personal:
            fragment["personal"] = personal
        headline = _g(p, "Headline")
        if headline:
            fragment.setdefault("personal", {})["title"] = headline
        summary = _g(p, "Summary")
        if summary:
            fragment["summary_en"] = summary

    positions = _read_csv(zf, "Positions.csv")
    experience: list[dict[str, Any]] = []
    for row in positions:
        experience.append(
            {
                "role": _g(row, "Title"),
                "company": _g(row, "Company Name"),
                "start": _g(row, "Started On"),
                "end": _g(row, "Finished On") or "Present",
                "highlights": [h for h in [_g(row, "Description")] if h],
            }
        )
    if experience:
        fragment["experience"] = experience

    skills_rows = _read_csv(zf, "Skills.csv")
    skill_names = [_g(r, "Name") for r in skills_rows if _g(r, "Name")]
    if skill_names:
        fragment["skills"] = {"linkedin": skill_names}

    edu_rows = _read_csv(zf, "Education.csv")
    education = []
    for row in edu_rows:
        education.append(
            {
                "degree": _g(row, "Degree Name"),
                "institution": _g(row, "School Name"),
                "year": _g(row, "End Date", "Start Date"),
            }
        )
    if education:
        fragment["education"] = education

    lang_rows = _read_csv(zf, "Languages.csv")
    languages = []
    for row in lang_rows:
        nm = _g(row, "Name")
        if nm:
            languages.append({"name": nm, "level": _g(row, "Proficiency")})
    if languages:
        fragment["languages"] = languages

    cert_rows = _read_csv(zf, "Certifications.csv")
    certs = []
    for row in cert_rows:
        nm = _g(row, "Name")
        if nm:
            certs.append({"name": nm, "issuer": _g(row, "Authority"), "year": _g(row, "Started On")})
    if certs:
        fragment["certifications"] = certs

    if not positions and not skill_names:
        fragment["warnings"].append(
            "Tu export de LinkedIn no incluye Positions.csv/Skills.csv. "
            "Probablemente pediste el archivo 'rapido'; solicita 'el archivo mayor' "
            "(Get a copy of your data) para importar experiencia y skills."
        )

    logger.info(
        "linkedin zip: %d posiciones, %d skills, %d educacion",
        len(experience),
        len(skill_names),
        len(education),
    )
    return fragment


def from_extension(payload: dict[str, Any]) -> dict[str, Any]:
    """Mapea el payload que la extension lee del propio perfil -> ProfileFragment."""
    fragment: dict[str, Any] = {"source": "linkedin"}
    personal: dict[str, Any] = {}
    if payload.get("name"):
        personal["name"] = payload["name"]
    if payload.get("headline"):
        personal["title"] = payload["headline"]
    if payload.get("location"):
        personal["location"] = payload["location"]
        personal["location_short"] = payload["location"]
    if payload.get("profile_url"):
        personal["linkedin"] = payload["profile_url"]
    if personal:
        fragment["personal"] = personal
    if payload.get("summary"):
        fragment["summary_en"] = payload["summary"]
    if isinstance(payload.get("experience"), list):
        fragment["experience"] = payload["experience"]
    if isinstance(payload.get("skills"), list) and payload["skills"]:
        fragment["skills"] = {"linkedin": [str(s) for s in payload["skills"]]}
    if isinstance(payload.get("education"), list):
        fragment["education"] = payload["education"]
    return fragment
