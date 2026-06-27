"""Construccion de la query de Gmail y pre-filtro barato (sin IA).

Solo clasificamos con el LLM los correos que pasan este pre-filtro (dominio ATS
conocido, asunto con patron de reclutamiento, o nombre de una empresa a la que
el usuario ha aplicado). Asi evitamos gastar tokens en newsletters.
"""

from __future__ import annotations

import re

# Dominios de los principales ATS / portales de empleo.
ATS_DOMAINS = [
    "greenhouse.io", "lever.co", "myworkday.com", "myworkdayjobs.com",
    "smartrecruiters.com", "ashbyhq.com", "recruitee.com", "teamtailor.com",
    "workable.com", "bamboohr.com", "icims.com", "breezy.hr", "personio.com",
    "linkedin.com", "indeed.com", "infojobs.net", "tecnoempleo.com",
    "welcometothejungle.com", "hi.wellfound.com", "wellfound.com",
]

# Patrones de asunto frecuentes en respuestas de candidaturas (ES + EN).
SUBJECT_PATTERNS = [
    r"\bapplication\b", r"\bcandidat", r"\binterview\b", r"\bentrevista\b",
    r"\boffer\b", r"\boferta\b", r"\brejected?\b", r"\brechaz", r"\bproceso\b",
    r"\bvacante\b", r"\bposition\b", r"\bthank you for applying\b",
    r"gracias por (tu|su) (interes|candidatura|solicitud)",
    r"recruit", r"talent", r"hiring", r"\bRE:\b",
]

_SUBJECT_RE = re.compile("|".join(SUBJECT_PATTERNS), re.IGNORECASE)
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(s\.?l\.?u?\.?|s\.?a\.?|inc\.?|ltd\.?|gmbh|llc|ab|oy|bv|corp\.?|co\.?)\b",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    """Normaliza un nombre de empresa para comparar (sin sufijos legales)."""
    name = (name or "").lower().strip()
    name = _LEGAL_SUFFIX_RE.sub("", name)
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name


def build_query(companies: list[str], lookback_days: int) -> str:
    """Query estilo Gmail: ventana temporal + remitentes ATS / empresas."""
    parts: list[str] = [f"newer_than:{max(1, lookback_days)}d"]
    ors: list[str] = [f"from:{d}" for d in ATS_DOMAINS]
    for c in companies:
        c = c.strip()
        if c:
            ors.append(f'"{c}"')
    if ors:
        parts.append("(" + " OR ".join(ors) + ")")
    parts.append("-category:promotions")
    return " ".join(parts)


def passes_prefilter(
    from_email: str, subject: str, snippet: str, companies_norm: set[str]
) -> bool:
    """Filtro barato pre-IA: dominio ATS, asunto relevante o empresa conocida."""
    fe = (from_email or "").lower()
    if any(dom in fe for dom in ATS_DOMAINS):
        return True
    if _SUBJECT_RE.search(subject or ""):
        return True
    haystack = normalize_company(subject + " " + snippet)
    return any(c and c in haystack for c in companies_norm)
