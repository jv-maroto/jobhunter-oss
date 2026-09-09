from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.schemas.job import EmploymentType, ScoredJobResult
from app.scrapers.country_map import COUNTRY_MAP, resolve_regions

_COUNTRY_ALIASES = {
    "CH": ("switzerland", "schweiz", "suisse", "svizzera", "suiza"),
    "ES": ("spain", "espana"),
    "DE": ("germany", "deutschland"),
    "FR": ("france",),
    "GB": ("united kingdom", "uk"),
    "US": ("united states", "usa", "u.s."),
    "CA": ("canada",),
}
for _code, _info in COUNTRY_MAP.items():
    _COUNTRY_ALIASES.setdefault(_code, (_info["location"].lower(),))
_CITY_ALIASES = {
    "CH": ("zurich", "zuerich", "geneva", "geneve", "basel", "lausanne", "bern", "berne", "zug", "lugano", "lucerne", "luzern", "winterthur", "st gallen", "st. gallen", "sankt gallen", "biel", "bienne", "neuchatel", "fribourg", "schaffhausen", "chur"),
    "ES": ("madrid", "barcelona"),
    "DE": ("berlin", "munich", "munchen"),
    "FR": ("paris",),
    "GB": ("london",),
    "US": ("new york", "san francisco"),
    "CA": ("toronto", "vancouver"),
}


def _norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def location_countries(location: str) -> set[str]:
    normalized = _norm(location)
    found = {
        code for code, aliases in _COUNTRY_ALIASES.items()
        if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized) for alias in aliases)
    }
    for code in _COUNTRY_ALIASES:
        if (re.search(r"(?:^|[,/(\s])" + code + r"(?:$|[,/)\s])", location or "")
                or re.search(r"(?:^|\bin |\bfrom |\bremote[ ,(-]+|, )" + code.lower() + r"(?:$|[,/)\s])", normalized)):
            found.add(code)
    if found:
        return found
    return {code for code, cities in _CITY_ALIASES.items()
            if any(re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", normalized) for city in cities)}


def salary_preferences(prefs: dict) -> tuple[float | None, float | None, str | None]:
    if "salary_min" in prefs or "salary_max" in prefs:
        return prefs.get("salary_min"), prefs.get("salary_max"), prefs.get("salary_currency")
    return prefs.get("salary_min_eur"), prefs.get("salary_max_eur"), "EUR"


def detect_employment_type(job: dict[str, Any]) -> EmploymentType | None:
    patterns = {
        "internship": r"\b(?:intern|internship|praktikum|praktikant|stage|stagiaire|becari[oa])\b",
        "apprenticeship": r"\b(?:apprentice(?:ship)?|ausbildung|alternance|trainee|apprendistato)\b",
        "temporary": r"\b(?:temporary|fixed[- ]term|befristet\w*|cdd|temporaneo)\b",
        "permanent": r"\b(?:permanente?|unbefristet\w*|festanstellung|cdi|indefinido|tempo indeterminato)\b",
        "contract": r"\b(?:contract(?:or)?|freelance)\b",
        "part_time": r"\b(?:part[-_ ]?time|teilzeit)\b",
        "full_time": r"\b(?:full[-_ ]?time|vollzeit)\b",
    }
    hours_type = None
    for text in (str(job.get("title") or ""), str(job.get("employment_type") or "")):
        for kind, pattern in patterns.items():
            if re.search(pattern, _norm(text)):
                if kind in {"full_time", "part_time"}:
                    hours_type = kind
                else:
                    return kind
    description = _norm(str(job.get("description") or ""))
    statements = re.findall(r"(?:employment type|job type|contract type|type de contrat|tipo di contratto|anstellungsart)\s*[:=-]\s*([^\n.;]+)", description)
    for statement in statements:
        for kind, pattern in patterns.items():
            if re.search(pattern, statement):
                return kind
    return hours_type


def job_compatibility(job: dict[str, Any], prefs: dict) -> dict[str, bool | None]:
    targets = set(resolve_regions(prefs))
    countries = targets - {"REMOTE"}
    remote = bool(job.get("remote"))
    location = str(job.get("location") or "")
    listed = location_countries(location)
    description = _norm(str(job.get("description") or ""))
    location_ok: bool | None = bool(listed & countries) if targets and listed else None
    if remote:
        scope = _norm(location)
        worldwide = bool(re.search(r"\b(worldwide|anywhere in the world|work from anywhere|global remote)\b", scope))
        for sentence in re.split(r"[\n.!?;]", description):
            if re.search(r"\b(?:work from anywhere|remote(?:ly)?(?: work)?(?:[- ,]+(?:from|available|open|is|fully|anywhere))*[- ,]+worldwide|worldwide remote)\b", sentence) and not re.search(r"\b(?:not|except|excluding)\b", sentence):
                worldwide = True
            for match in re.finditer(r"\b(?:remote(?:ly)?(?: work)?(?: available)? (?:in|from|within|across)|work from|(?:candidates?|applicants?) (?:must be )?(?:based|located|resident) in|residents? of|restricted to|only in)[: ,(-]+([^\n.!?;]+)", sentence):
                scope += "\n" + match.group(0)
        eligible = location_countries(scope)
        residence = str(prefs.get("residence_country") or "")
        home = location_countries(residence)
        target_remote = countries or home
        if worldwide:
            location_ok = True
        elif eligible:
            location_ok = bool(eligible & target_remote) if target_remote else None
        # ponytail: conservative text eligibility; structured board restrictions can replace this parser.
        restrictions = re.findall(r"(?:must (?:be based|be located|reside|live)(?: in)?|must (?:be )?(?:authorized|eligible|permitted) to work in|restricted to|only in)\s+([^\n.!?;]+)", description)
        restrictions += re.findall(r"([^\n.!?;]+?)\s+(?:residents? )?only\b", scope + "\n" + description)
        for restriction in restrictions:
            restricted = location_countries(restriction)
            if restricted and target_remote and not restricted & target_remote:
                location_ok = False
        exclusions = re.findall(r"([^\n.!?;]+?)\s+(?:is|are)\s+(?:not eligible|excluded|not allowed|not supported)\b", description)
        exclusions += re.findall(r"(?:not (?:available|eligible|open)|cannot (?:work|hire)|excluding|except|not hiring)(?: (?:in|from|to))?\s+([^\n.!?;]+)", description)
        for exclusion in exclusions:
            if location_countries(exclusion) & target_remote:
                location_ok = False
        if countries == {"CH"} and re.search(r"\b(?:eu|eea|european union)[ -]only\b", scope + "\n" + description):
            location_ok = False
    elif targets == {"REMOTE"}:
        location_ok = False

    remote_ok: bool | None = (remote if prefs.get("remote_only") else True)
    if remote and location_ok is not True:
        remote_ok = location_ok
    floor, _, target_currency = salary_preferences(prefs)
    amount = job.get("salary_max") if job.get("salary_max") is not None else job.get("salary_min")
    salary_ok = None
    if floor is not None and amount is not None and job.get("salary_period") == "year" and job.get("currency") == target_currency:
        salary_ok = amount >= floor
    wanted_types = prefs.get("employment_types") or []
    employment = detect_employment_type(job)
    employment_ok = None
    if wanted_types and employment:
        if employment in wanted_types:
            employment_ok = True
        elif employment not in {"full_time", "part_time"}:
            employment_ok = False
    seniority_ok = None
    title = _norm(str(job.get("title") or ""))
    if prefs.get("seniority") == "junior":
        if re.search(r"\b(?:junior|jr|entry[- ]level|graduate|new grad|berufseinsteiger|debutant|neolaureat[oa])\b", title):
            seniority_ok = True
        elif re.search(r"\b(?:senior|sr|staff|principal|lead|head of|director|manager|managerin|leiter|leitung|mid[- ]level)\b", title):
            seniority_ok = False
    return {"location_compatible": location_ok, "remote_compatible": remote_ok, "salary_in_range": salary_ok, "employment_compatible": employment_ok, "seniority_compatible": seniority_ok}


def language_mismatches(job: dict[str, Any], cv: dict, *, checks: list[dict] | None = None) -> list[str]:
    from app.scoring.language_requirements import language_checks

    return list(dict.fromkeys(
        f"{check['requirement']} — required language proficiency exceeds {check['evidence']}"
        for check in (language_checks(job, cv) if checks is None else checks)
        if check["kind"] == "language" and check["importance"] == "required" and check["status"] == "gap"
    ))


def constrain_score(result: ScoredJobResult, job: dict[str, Any], cv: dict, *, assessment: dict[str, Any] | None = None) -> ScoredJobResult:
    prefs = cv.get("search_preferences") or {}
    flags = job_compatibility(job, prefs)
    if flags["seniority_compatible"] is None and result.seniority_compatible is False:
        flags["seniority_compatible"] = False
    result = result.model_copy(update=flags)
    reasons = []
    if flags["location_compatible"] is False:
        reasons.append("Outside target geography or stated remote eligibility")
    elif resolve_regions(prefs) and flags["location_compatible"] is None:
        reasons.append("Target-country or remote eligibility is unconfirmed")
    if flags["remote_compatible"] is False and prefs.get("remote_only"):
        reasons.append("Remote-only preference is not met")
    if flags["employment_compatible"] is False:
        reasons.append("Employment type is outside the selected contract types")
    if flags["seniority_compatible"] is False:
        reasons.append("Stated seniority does not match the selected experience level")
    text = _norm(" ".join(str(job.get(k) or "") for k in ("title", "description")))
    if any(re.search(r"(?<!\w)" + re.escape(_norm(str(keyword))) + r"(?!\w)", text) for keyword in (prefs.get("exclude_keywords") or []) if keyword):
        reasons.append("Matches an excluded keyword")
    from app.scoring.qualification_assessment import assess_qualifications

    assessment = assess_qualifications(job, cv) if assessment is None else assessment
    language_gaps = language_mismatches(job, cv, checks=assessment["checks"])
    reasons.extend(language_gaps)
    required_checks = [check for check in assessment["checks"] if check["importance"] == "required"]
    qualification_gaps = [check for check in required_checks if check["status"] == "gap"]
    qualification_unknowns = [check for check in required_checks if check["status"] == "unknown"]
    if qualification_gaps or qualification_unknowns:
        result.match_score = min(result.match_score, 29 if qualification_gaps else 54)
        for check in (qualification_gaps + qualification_unknowns)[:3]:
            reasons.append(f"{'Qualification gap' if check['status'] == 'gap' else 'Qualification unverified'}: {check['requirement']}")
    if reasons:
        result.match_score = min(result.match_score, 29 if language_gaps or any(v is False for k, v in flags.items() if k != "salary_in_range") else 54)
        label = (result.rejection_reason or "").split(": ", 1)[0] if (result.rejection_reason or "").startswith("Heuristic fit estimate") else ""
        result.rejection_reason = (label + ": " if label else "") + "; ".join(dict.fromkeys(reasons))
    return result
