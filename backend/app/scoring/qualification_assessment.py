from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from app.scoring.language_requirements import language_checks

_DEGREES = (
    (1, r"\b(?:high school|secondary school)\b"),
    (2, r"\b(?:associate(?:'s)?|vocational diploma)\b"),
    (3, r"\b(?:bachelor(?:'s)?|b\.?sc\.?)\b"),
    (4, r"\b(?:master(?:'s)?|m\.?sc\.?)\b"),
    (5, r"\b(?:ph\.?d\.?|doctorate|doctoral degree)\b"),
)
_PREFERRED = r"\b(?:preferred|desirable|optional|advantageous|a plus|nice[- ]to[- ]have|ideally|von vorteil|wunschenswert|un atout)\b"
_REQUIRED = r"\b(?:required|mandatory|must|essential|minimum|at least|you (?:have|bring|hold)|we require)\b"
_NEGATED = r"\b(?:not (?:required|necessary|essential)|(?:do|does) not require|no .{0,70} (?:required|necessary|needed)|without .{0,50} experience)\b"
_YEARS = re.compile(r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*\+?\s*(?:[-–]\s*\d+\s*)?(?:years?|yrs?)\b", re.I)
_NUMBER_WORDS = dict(zip("one two three four five six seven eight nine ten".split(), range(1, 11)))
_ACADEMIC = r"\b(?:academic|coursework|student project|personal project|hobby)\b"
_PRODUCTION = r"\b(?:production|commercial|professional|industry|hands[- ]on)\b"


def _norm(value: Any) -> str:
    return _normalize_text(str(value or ""))


@lru_cache(maxsize=512)
def _normalize_text(value: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return " ".join(text.lower().replace("’", "'").replace("\\-", "-").replace("production-grade", "production").split())


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")


def _contains(needle: str, haystack: str) -> bool:
    return bool(needle and re.search(r"(?<!\w)" + re.escape(_norm(needle)) + r"(?!\w)", _norm(haystack)))


def _clauses(description: str):
    section = "unclear"
    # ponytail: conservative prose parser; unsupported wording stays unknown for human review.
    for line in description.splitlines():
        clean = re.sub(r"^[\s#*>•-]+", "", line).strip()
        heading, _, tail = clean.partition(":")
        label = _norm(heading).strip("* ")
        if re.fullmatch(r"(?:required |minimum )?(?:requirements|qualifications|your profile|your skillset|what you bring|must have|essential skills)", label):
            section = "required"
            clean = tail
        elif re.fullmatch(r"(?:preferred qualifications|nice[- ]to[- ]have|optional|desirable skills)", label):
            section = "preferred"
            clean = tail
        elif re.fullmatch(r"(?:responsibilities|what we offer|benefits|about us|about the company|your tasks)", label):
            section = "unclear"
            clean = tail
        for clause in re.split(r"[;\n]|(?<=[.!?])\s+(?=[A-Z])", clean):
            clause = clause.strip(" *•-")
            if not clause:
                continue
            normalized = _norm(clause)
            if re.match(r"(?:location|job (?:type|location)|employment type|salary|compensation)\s*:", normalized):
                continue
            if re.match(r"(?:permanent|temporary|full[- ]time|part[- ]time)\b.{0,100}\b(?:role|position|job)\b", normalized) and not re.search(_REQUIRED + r"|\b(?:skills?|experience|knowledge)\b", normalized):
                continue
            mixed = bool(re.search(_PREFERRED, normalized) and re.search(_REQUIRED, normalized))
            shared = section if mixed else ("preferred" if re.search(_PREFERRED, normalized) else ("required" if re.search(_REQUIRED, normalized) else section))
            for part in re.split(r",|\s+(?:but|whereas|while)\s+|(?<=required)\s+and\s+|(?<=preferred)\s+and\s+", clause, flags=re.I):
                part = part.strip()
                if part:
                    text = _norm(part)
                    importance = "preferred" if re.search(_PREFERRED, text) else ("required" if re.search(_REQUIRED, text) else shared)
                    yield part, importance


def _check(kind: str, importance: str, requirement: str, status: str, evidence: str | None) -> dict:
    return {"kind": kind, "importance": importance, "status": status,
            "requirement": requirement[:360], "evidence": evidence[:500] if evidence else None}


def _experience_alternative(clause: str) -> bool:
    match = re.search(r"\bor\b([^,.;]+)\bexperience\b", _norm(clause))
    return bool(match and not re.search(r"\b(?:and|plus)\b|&", match.group(1)))


def _education(clause: str, importance: str, cv: dict) -> dict | None:
    levels = [rank for rank, pattern in _DEGREES if re.search(pattern, _norm(clause))]
    if not levels:
        return None
    candidate = []
    for entry in cv.get("education") or []:
        if not isinstance(entry, dict):
            continue
        degree = str(entry.get("degree") or entry.get("qualification") or "")
        if entry.get("completed") is False or re.search(r"\b(?:pursuing|expected|in progress|incomplete|ph\.?d\.? candidate|scrum master)\b", _norm(_text(entry))):
            continue
        ranks = [rank for rank, pattern in _DEGREES if re.search(pattern, _norm(degree))]
        if ranks:
            candidate.append((max(ranks), degree))
    if not candidate:
        return _check("education", importance, clause, "unknown", None)
    rank, evidence = max(candidate)
    status = "met" if rank >= min(levels) else "gap"
    if status == "gap" and (re.search(r"\b(?:equivalent|comparable)\b", _norm(clause)) or _experience_alternative(clause)):
        status = "unknown"
        evidence += "; equivalent experience has not been established"
    field = re.search(r"\bin\s+(.+?)(?=\s+(?:required|preferred|is|with|or (?:a |an )?(?:related|equivalent))\b|[,.;]|$)", _norm(clause))
    if status == "met" and field and not any(_contains(field.group(1), degree) for level, degree in candidate if level >= min(levels)):
        status = "unknown"
        evidence += "; the requested field or its equivalence is unconfirmed"
    return _check("education", importance, clause, status, evidence)


def _month(value: Any, *, current: bool = False) -> int | None:
    raw = str(value or "").strip()
    if _norm(raw) in {"present", "current", "now"} or (not raw and current):
        today = date.today()
        return today.year * 12 + today.month - 1
    for fmt in ("%Y-%m", "%Y-%m-%d", "%b %Y", "%B %Y", "%Y/%m"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.year * 12 + parsed.month - 1
        except ValueError:
            continue
    return None  # Year-only or missing dates do not establish a precise duration.


def _professional_entries(cv: dict) -> list[dict]:
    entries = [entry for entry in cv.get("experience") or [] if isinstance(entry, dict)]
    return [entry for entry in entries if not re.search(_ACADEMIC, _norm(" ".join(str(entry.get(key) or "") for key in ("context", "employment_type", "role", "title"))))]


def _experience_text(entry: dict) -> str:
    return "; ".join(_text(entry[key]) for key in (
        "role", "title", "domain", "highlights", "bullets", "description", "summary",
        "technologies", "skills", "responsibilities", "context", "context_detail", "claim_boundaries",
    ) if entry.get(key))


def _domain_tokens(text: str) -> set[str]:
    stop = {"of", "in", "with", "and", "or", "the", "a", "an", "relevant", "professional", "proven", "hands", "on", "practical", "experience", "working", "work", "required", "minimum", "least", "industry", "commercial"}
    return {word.removesuffix("ing") for word in re.findall(r"[a-z][a-z0-9+#-]*", _norm(text)) if word not in stop}


def _supports_experience(entry: dict, tokens: set[str], production: bool) -> bool:
    text = _norm(_experience_text(entry))
    if not tokens or not tokens <= _domain_tokens(text):
        return False
    for token in tokens | ({"production"} if production else set()):
        if re.search(r"\b(?:no|not|without|never|non[- ])\b.{0,60}\b" + re.escape(token), text):
            return False
    if production:
        if re.search(r"\b(?:prototype|coursework|academic|simulation|local experiments)\b", text):
            return False
        return bool(re.search(r"\bproduction\b", text))
    return True


def _experience(clause: str, importance: str, cv: dict) -> dict | None:
    normalized = _norm(clause)
    years = _YEARS.search(normalized)
    professional = bool(re.search(_PRODUCTION, normalized))
    production = bool(re.search(r"\bproduction\b", normalized))
    if not re.search(r"\b(?:experience|track record|expertise)\b", normalized):
        return None
    entries = _professional_entries(cv)
    if years:
        required = float(_NUMBER_WORDS.get(years.group(1), years.group(1)))
        domain = normalized[years.end():].split(",")[0]
        domain = re.sub(r"\b(?:is|are)\b.*$", "", domain)
        tokens = _domain_tokens(domain)
        relevant = [entry for entry in entries if tokens and tokens <= _domain_tokens(" ".join(str(entry.get(key) or "") for key in ("domain", "role", "title"))) and _supports_experience(entry, tokens, production)]
        months = set()
        undated = False
        today = date.today()
        current_month = today.year * 12 + today.month - 1
        for entry in relevant:
            start, end = _month(entry.get("start")), _month(entry.get("end"), current=entry.get("current") is True)
            if start is None or end is None or end < start or start > current_month:
                undated = True
            else:
                months.update(range(start, min(end, current_month)))
        if not relevant:
            return _check("experience", importance, clause, "unknown", "No dated professional role establishes the requested domain experience")
        duration = len(months) / 12
        evidence = f"{duration:.1f} documented years in matching roles: " + "; ".join(str(entry.get("role") or entry.get("title") or entry.get("domain")) for entry in relevant)
        status = "met" if duration >= required else ("unknown" if undated else "gap")
        return _check("experience", importance, clause, status, evidence)
    before, _, after = re.split(r"\b(experience|expertise|track record)\b", normalized, maxsplit=1)
    domain = re.sub(r"^.*?\b(?:production|commercial|professional|industry|hands[- ]on)\b", "", before)
    if not _domain_tokens(domain):
        domain = after
    tokens = _domain_tokens(domain)
    if not professional:
        entries += [entry for entry in cv.get("projects") or [] if isinstance(entry, dict)]
    for entry in entries:
        evidence = _experience_text(entry)
        if _supports_experience(entry, tokens, production):
            return _check("experience", importance, clause, "met", evidence)
    evidence = "Professional production evidence is not established by listed skills or academic projects" if production else "The requested experience is not established by documented roles or projects"
    return _check("experience", importance, clause, "unknown", evidence)


def _skill_checks(clause: str, importance: str, cv: dict) -> list[dict]:
    normalized = _norm(clause)
    if importance == "unclear" and not re.search(r"\b(?:skills?|proficien\w*|knowledge|experience (?:with|in))\b", normalized):
        return []
    parts = re.split(r",|\s+and\s+|\s*&\s*", clause)
    skills = cv.get("skills") or {}
    evidence_sources = []
    if isinstance(skills, dict):
        evidence_sources.extend((str(skill), f"{group}: {skill}") for group, values in skills.items() if isinstance(values, list) for skill in values)
    elif isinstance(skills, list):
        evidence_sources.extend((str(skill), str(skill)) for skill in skills)
    evidence_sources.extend((_experience_text(entry), _experience_text(entry)) for entry in _professional_entries(cv))
    evidence_sources.extend((_experience_text(entry), _experience_text(entry)) for entry in cv.get("projects") or [] if isinstance(entry, dict))
    checks = []
    for part in parts:
        part = part.strip(" .*•-")
        text = _norm(part)
        if any(re.search(pattern, text) for _, pattern in _DEGREES) or _YEARS.search(text) or re.search(r"\b(?:experience|track record|expertise|fluent|native|language)\b", text):
            continue
        term = re.sub(r"^(?:(?:you )?(?:must |should )?(?:have |know |bring |hold )|(?:strong |good |excellent )?(?:skills? in|knowledge of|proficiency in|proficient in)|(?:required|preferred|essential)(?: skills)?\s*:)\s*", "", text)
        term = re.sub(r"\s+(?:(?:is|are) )?(?:required|mandatory|essential|preferred|desirable|optional|is a plus|would be a plus|is not required)\b.*$", "", term).strip()
        if not term or len(term.split()) > 7:
            continue
        alternatives = re.split(r"\s+or\s+", term)
        evidence = next((source for value, source in evidence_sources if not re.search(r"\b(?:unconfirmed|not confirmed|to learn|learning goals|planned|desired|no experience)\b", _norm(source)) and any(_contains(option, value) and not re.search(r"\b(?:no|not|without)\b.{0,30}" + re.escape(option), _norm(value)) for option in alternatives)), None)
        checks.append(_check("skills", importance, part, "met" if evidence else "unknown", evidence))
    return checks


def assess_qualifications(job: dict[str, Any], cv: dict[str, Any]) -> dict[str, Any]:
    """Compare explicit posting qualifications against supplied candidate evidence.

    Unknown means unverified, never absent. Preferences and ambiguous requirements
    remain separate from mandatory gaps; this is not an interview probability.
    """
    checks = language_checks(job, cv)
    language_requirements = {_norm(check["requirement"]) for check in checks}
    for clause, importance in _clauses(str(job.get("description") or "")):
        if re.search(_NEGATED, _norm(clause)):
            continue
        education = _education(clause, importance, cv)
        experience = None if education and _experience_alternative(clause) else _experience(clause, importance, cv)
        checks.extend(check for check in (education, experience) if check is not None)
        if not any(_norm(clause).rstrip(".") == requirement.rstrip(".") or _norm(clause) in requirement for requirement in language_requirements):
            checks.extend(_skill_checks(clause, importance, cv))
    checks = list({(check["kind"], check["requirement"], check["importance"]): check for check in checks}.values())
    required = [check for check in checks if check["importance"] == "required"]
    gaps = [check for check in required if check["status"] == "gap"]
    unknowns = [check for check in required if check["status"] == "unknown"]
    if gaps:
        recommendation, summary = "unlikely", f"{len(gaps)} mandatory qualification gap(s) in the documented profile."
    elif unknowns:
        recommendation, summary = "stretch", f"{len(unknowns)} mandatory qualification(s) need evidence or clarification."
    elif not required:
        recommendation, summary = "unknown", "Mandatory qualifications are not established by the posting; review the full requirements."
    elif any(check["status"] != "met" or check["importance"] == "unclear" for check in checks):
        recommendation, summary = "consider", "Parsed mandatory qualifications are supported; other qualifications remain for review."
    else:
        recommendation, summary = "strong", "The parsed mandatory qualifications have supporting profile evidence."
    return {"recommendation": recommendation, "checks": checks, "summary": summary}
