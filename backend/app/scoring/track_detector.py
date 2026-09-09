from __future__ import annotations

import re
import unicodedata

from app.schemas.job import JobTrack, SalaryBand

_ROLE_PATTERNS: dict[JobTrack, tuple[str, ...]] = {
    "quant": (r"\bquant(?:itative)?(?:\b|[ -])", r"quantitatif", r"quantitativ", r"cuantitativ"),
    "analytics_eng": (r"analytics? engineer", r"ingenier[oa] de analitica"),
    "data_engineer": (r"data engineer", r"data platform", r"dateningenieur", r"ingenier[oa] de datos", r"ingenieur donnees", r"\betl\b"),
    "bi": (r"\bbi\b", r"business intelligence", r"power\s?bi", r"business[- ]intelligence"),
    "data_scientist": (r"data scien(?:tist|ce)", r"cientific[oa] de datos", r"datenwissenschaft", r"science des donnees"),
    "ai_ml": (r"\b(?:ai|ml|llm|rag|nlp)\b", r"machine learning", r"artificial intelligence", r"inteligencia artificial", r"intelligence artificielle", r"kunstliche intelligenz"),
    "data_analyst": (r"data analy(?:st|tics)", r"analista de datos", r"datenanalyst", r"analyste (?:de )?donnees"),
    "sysadmin": (r"\b(?:devops|sre|sysadmin)\b", r"system.? admin", r"administrador.*sistemas", r"infrastructure", r"(?:cloud|network|platform) engineer", r"linux admin"),
    "dev": (r"software (?:engineer|developer)", r"(?:frontend|backend|full.?stack|mobile).*developer", r"developpeur", r"entwickler"),
}


def _norm(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower().split())


def detect_track(title: str, description: str | None = None, tags: list[str] | None = None) -> JobTrack:
    for text in (_norm(title), _norm(description or "")):
        for track, patterns in _ROLE_PATTERNS.items():
            if any(re.search(pattern, text) for pattern in patterns):
                return track
    return "dev"


def predict_salary_band(
    title: str,
    company: str | None = None,
    description: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    currency: str | None = None,
    salary_period: str | None = None,
    prefs: dict | None = None,
) -> SalaryBand:
    from app.scoring.compatibility import salary_preferences

    floor, ceiling, target_currency = salary_preferences(prefs or {})
    amount = salary_max if salary_max is not None else salary_min
    if amount is None or salary_period != "year" or currency != target_currency or floor is None:
        return "unknown"
    if amount < floor:
        return "low"
    if ceiling is not None and amount >= ceiling:
        return "high"
    return "mid"
