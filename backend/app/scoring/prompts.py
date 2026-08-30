"""Prompts para scoring.

El system prompt se CONSTRUYE a partir de `cv_master.json` (salario minimo,
paises, remoto, seniority, skills, exclusiones). Antes llevaba escritas a fuego
las preferencias del autor original (region, "junior/mid", "<28K", stack
favorito) y cualquiera que clonara el repo obtenia puntuaciones pensadas para
otra persona.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

_OUTPUT_CONTRACT = """You are an expert job-offer evaluator. Your only task is to compare a candidate
CV (JSON) with a job posting and return ONE JSON object with this exact shape:

- match_score (0-100): how well the candidate fits the posting.
  - 90-100: perfect fit, should apply right away.
  - 70-89: strong fit, worth preparing a tailored application.
  - 40-69: partial fit; apply only if there are few better options.
  - <40: discard.
- salary_in_range: if the posting mentions a salary, true when it is at or above the
  candidate's minimum (see preferences). null if no salary is mentioned.
- remote_compatible: true if the posting's work mode (remote / hybrid / onsite + location)
  is compatible with the candidate's preferences below.
- location_compatible: true if the posting's location is inside the candidate's target
  regions, or the job is remote and open to them.
- key_matches: 3-6 concrete overlaps between CV and posting (skills, projects, experience).
- missing_skills: 0-5 skills the posting requires that the candidate clearly lacks.
- rejection_reason: only when match_score < 30; one sentence explaining why.
- personalization_hooks: 2-4 sentences the candidate could use in a cover letter
  (a related own project, shared stack, a problem they have solved, etc).

Return ONLY valid JSON, no extra text, no markdown."""

_SENIORITY_LABELS = {
    "junior": "junior (0-2 years)",
    "mid": "mid-level (2-5 years)",
    "senior": "senior (5-9 years)",
    "lead": "lead / staff (9+ years)",
}


def _years_of_experience(cv: dict[str, Any]) -> float:
    """Suma aproximada de anios en `experience[]` (start/end en YYYY o YYYY-MM)."""
    total = 0.0
    today = date.today()
    for e in cv.get("experience") or []:
        if not isinstance(e, dict):
            continue
        start = _parse_ym(e.get("start"))
        if start is None:
            continue
        end = _parse_ym(e.get("end")) or today
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if months > 0:
            total += months / 12.0
    return total


def _parse_ym(raw: Any) -> date | None:
    if not raw:
        return None
    s = str(raw).strip().lower()
    if s in {"present", "actual", "actualidad", "now", "current", "hoy"}:
        return None
    m = re.match(r"(\d{4})(?:[-/](\d{1,2}))?", s)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2) or 1)
    month = min(max(month, 1), 12)
    return date(year, month, 1)


def infer_seniority(cv: dict[str, Any]) -> str:
    """`search_preferences.seniority` si existe; si no, por anios de experiencia."""
    prefs = cv.get("search_preferences") or {}
    explicit = str(prefs.get("seniority") or "").strip().lower()
    if explicit in _SENIORITY_LABELS:
        return explicit
    years = _years_of_experience(cv)
    if years < 2:
        return "junior"
    if years < 5:
        return "mid"
    if years < 9:
        return "senior"
    return "lead"


def _flatten_skills(cv: dict[str, Any], limit: int = 12) -> list[str]:
    out: list[str] = []
    skills = cv.get("skills") or {}
    if isinstance(skills, dict):
        for vals in skills.values():
            if isinstance(vals, list):
                out.extend(str(v).strip() for v in vals if str(v).strip())
    elif isinstance(skills, list):
        out.extend(str(v).strip() for v in skills if str(v).strip())
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        uniq.append(s)
    return uniq[:limit]


def _target_regions(prefs: dict[str, Any]) -> list[str]:
    """Regiones objetivo legibles (ISO / EU / REMOTE) sin depender del registry."""
    raw: list[str] = []
    if prefs.get("regions"):
        raw = [str(r) for r in prefs["regions"]]
    elif prefs.get("region_preset"):
        preset = str(prefs["region_preset"])
        raw = {
            "only_spain": ["ES"],
            "all_europe": ["EU"],
            "remote_worldwide": ["REMOTE"],
        }.get(preset, [preset])
    else:
        raw = [str(c) for c in (prefs.get("preferred_countries") or [])]
    return [r.upper() for r in raw if r]


def build_scoring_system(cv_master: dict[str, Any] | None) -> str:
    """System prompt de scoring adaptado al perfil del usuario."""
    cv = cv_master or {}
    prefs = cv.get("search_preferences") or {}
    personal = cv.get("personal") or {}

    lines: list[str] = []

    seniority = infer_seniority(cv)
    lines.append(
        f"- The candidate is {_SENIORITY_LABELS[seniority]}. Penalise strongly when the "
        "posting demands clearly more seniority or years than that; mildly when it is "
        "clearly below (over-qualified)."
    )

    salary_min = prefs.get("salary_min_eur")
    if salary_min:
        lines.append(
            f"- Minimum acceptable salary: {int(salary_min)} EUR/year (or equivalent). "
            "Penalise postings that state a clearly lower salary."
        )

    regions = _target_regions(prefs)
    remote_only = bool(prefs.get("remote_only"))
    residence = prefs.get("residence_country") or personal.get("location")
    if remote_only:
        lines.append(
            "- The candidate wants REMOTE work only: penalise onsite/hybrid postings unless "
            "they are explicitly remote-friendly."
        )
    if regions:
        pretty = ", ".join("remote worldwide" if r == "REMOTE" else r for r in regions)
        lines.append(f"- Target regions/countries: {pretty}.")
    if residence:
        lines.append(f"- The candidate is based in: {residence}.")
    if prefs.get("willing_to_relocate"):
        lines.append("- Open to relocation.")
    if prefs.get("work_authorization_eu") is False:
        lines.append("- No EU work authorization: penalise postings that require it.")

    skills = _flatten_skills(cv)
    if skills:
        lines.append(f"- Reward postings built around the candidate's stack: {', '.join(skills)}.")

    roles = [str(r) for r in (prefs.get("roles") or []) if str(r).strip()]
    if roles:
        lines.append(f"- Target roles: {', '.join(roles)}.")

    excludes = [str(k) for k in (prefs.get("exclude_keywords") or []) if str(k).strip()]
    if excludes:
        lines.append(f"- Discard postings matching these keywords: {', '.join(excludes)}.")

    langs = []
    for entry in cv.get("languages") or []:
        if isinstance(entry, dict) and entry.get("name"):
            lvl = entry.get("level")
            langs.append(f"{entry['name']} ({lvl})" if lvl else str(entry["name"]))
        elif isinstance(entry, str):
            langs.append(entry)
    if langs:
        lines.append(
            f"- Languages the candidate speaks: {', '.join(langs)}. Penalise postings that "
            "require a language not listed."
        )

    lines.append(
        "- Penalise non-technical roles (sales, marketing, L1 support) and unpaid internships "
        "unless the candidate's target roles say otherwise."
    )

    return _OUTPUT_CONTRACT + "\n\nSTRICT RULES (from the candidate's profile):\n" + "\n".join(lines)


# Prompt generico (sin perfil). Se mantiene por compatibilidad con imports antiguos.
SCORING_SYSTEM = build_scoring_system(None)


def build_scoring_user_prompt(cv_master: dict, job: dict) -> str:
    """Construye el bloque de usuario con CV + job description."""
    cv_compact = json.dumps(cv_master, ensure_ascii=False)
    job_block = json.dumps(
        {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "remote": job.get("remote", False),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "currency": job.get("currency"),
            "description": (job.get("description", "") or "")[:6000],
        },
        ensure_ascii=False,
    )
    return (
        "Candidate CV (JSON):\n"
        f"{cv_compact}\n\n"
        "Job posting to evaluate (JSON):\n"
        f"{job_block}\n\n"
        "Return the evaluation JSON."
    )
