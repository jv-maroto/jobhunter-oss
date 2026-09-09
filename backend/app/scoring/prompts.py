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

from app.scoring.compatibility import salary_preferences

_OUTPUT_CONTRACT = """You are an expert job-offer evaluator. Your only task is to compare a candidate
CV (JSON) with a job posting and return ONE JSON object with this exact shape:

- match_score (0-100): how well the candidate fits the posting. USE THE FULL RANGE.
  - 90-100: exceptional match — every requirement is covered, ideal domain, ideal seniority.
  - 75-89: strong fit — stack + role + level align, only nice-to-haves missing.
  - 55-74: partial fit worth reviewing — core stack overlaps, some concrete gap
    (missing 1-2 skills, mild seniority mismatch, or an unclear/incomplete posting).
  - 35-54: weak fit — stack barely overlaps, or clearly wrong role family.
  - <35: hard reject — different discipline, visa blocker, salary far below floor.

  EVIDENCE RULES:
  * Score only documented overlap. Empty missing_skills is not evidence of a strong fit.
  * Incomplete postings have unconfirmed requirements; do not label them a strong fit.
  * Target roles and target seniority describe interests, not proven experience.
  * Distinguish professional delivery, academic projects, and personal projects.
    A degree project in ML does not establish professional production ML experience.
    Skill-group names and each project's evidence/context qualify skill depth.
  * Required language proficiency matters: currently learning/basic German does not
    satisfy fluent/C1 German. Do not assume fluency from a language name alone.
  * Distinguish mandatory qualifications, preferences, alternatives and unknown evidence.
    A lower degree does not satisfy a required higher degree. "Or equivalent experience"
    needs documented equivalent evidence; it is not automatically a rejection or a match.
    Domain-specific years must come from dated professional roles in that domain, without
    double-counting overlapping dates. Skill keywords do not establish production experience.
    Missing evidence is unknown, not a proven absence. Do not score unverified mandatory
    qualifications as a strong fit. Scores describe fit, not interview or hiring probability.
  * Record salary, geography, seniority, employment and language issues in
    rejection_reason; they are not missing technical skills.

- salary_in_range: if the posting mentions a salary, true when it is at or above the
  candidate's minimum (see preferences). null if amount, currency or pay period is missing
  or if comparison requires an exchange rate or assumed working hours.
- remote_compatible: true if the posting's work mode (remote / hybrid / onsite + location)
  is compatible with the candidate's preferences below; null if eligibility is unknown.
- location_compatible: true if the posting's location is inside the candidate's target
  regions, or remote eligibility explicitly includes a target country. Remote alone is
  insufficient: return null for unspecified eligibility. EU/EEA-only is not Switzerland.
- employment_compatible: true only if explicit contract type matches a target employment type;
  null when unknown. Full-time does not establish a permanent contract.
- seniority_compatible: true if explicit level matches the target; null if unstated.
- key_matches: 3-6 concrete overlaps between CV and posting (skills, projects, experience).
- missing_skills: 0-5 skills the posting requires that the candidate clearly lacks.
  Location, seniority, salary and visa are NOT skills — do not list them here.
- rejection_reason: one sentence explaining the primary reason for any score below 70.
  Required when score < 30. Recommended (not required) for 30-69 to help the
  candidate decide fast. NULL for scores >= 70.
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


def _flatten_skills(cv: dict[str, Any], limit: int | None = None) -> list[str]:
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
    return uniq if limit is None else uniq[:limit]


def _target_regions(prefs: dict[str, Any]) -> list[str]:
    """Regiones objetivo legibles (ISO / EU / REMOTE) sin depender del registry."""
    raw: list[str] = []
    if prefs.get("regions"):
        raw = [str(r) for r in prefs["regions"]]
    elif prefs.get("region_preset"):
        preset = str(prefs["region_preset"])
        raw = {
            "only_spain": ["ES"],
            "only_switzerland": ["CH"],
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

    explicit_seniority = str(prefs.get("seniority") or "").lower()
    if explicit_seniority in _SENIORITY_LABELS:
        lines.append(
            f"- Target seniority: {_SENIORITY_LABELS[explicit_seniority]}. This is a search preference, "
            "not a verified count of professional years. Judge relevant professional experience "
            "from dated roles in the matching domain; do not add unrelated occupations or academic projects."
        )
    else:
        lines.append("- Target seniority is unstated. Do not infer technical years from unrelated occupations or academic projects.")

    salary_min, _, salary_currency = salary_preferences(prefs)
    if salary_min:
        lines.append(
            f"- Minimum acceptable salary: {int(salary_min)} {salary_currency or 'currency unspecified'}/year. "
            "Compare only stated annual amounts in the same currency. Never invent an FX rate or annualize with assumed hours/payments. "
            "If the posting states a lower salary, subtract at most 10 points and put the "
            "issue in rejection_reason — do not drop the score to <40 just for salary."
        )

    regions = _target_regions(prefs)
    remote_only = bool(prefs.get("remote_only"))
    residence = prefs.get("residence_country") or personal.get("location")
    if remote_only:
        lines.append(
            "- The candidate wants REMOTE work only: onsite/hybrid postings are incompatible. "
            "Respect geographic hiring restrictions even when the job is remote."
        )
    if regions:
        pretty = ", ".join("remote worldwide" if r == "REMOTE" else r for r in regions)
        lines.append(f"- Target regions/countries: {pretty}.")
    if residence:
        lines.append(f"- The candidate is based in: {residence}.")
    if prefs.get("willing_to_relocate"):
        lines.append("- Open to relocation.")
    lines.append("- Assess work authorization for each posting's hiring country using explicit profile evidence. Authorization for another country or region and relocation interest do not establish eligibility; unknown permits need review.")
    if prefs.get("work_authorization_eu") is False:
        lines.append("- No EU work authorization: penalise postings that require it.")

    skills = _flatten_skills(cv)
    if skills:
        lines.append(f"- Reward postings built around the candidate's stack: {', '.join(skills)}.")

    if prefs.get("employment_types"):
        lines.append(f"- Target employment types: {', '.join(prefs['employment_types'])}. Only explicit posting evidence establishes contract type; unknown stays null.")

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
            "salary_period": job.get("salary_period"),
            "employment_type": job.get("employment_type"),
            "description": job.get("description", "") or "",
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
