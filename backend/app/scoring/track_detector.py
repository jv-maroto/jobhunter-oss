"""Clasificador heurístico: dev vs sysadmin + banda de salario.

No usa LLM — son reglas rápidas que se aplican en ingest. Si más adelante
queremos calidad, podemos delegar a Haiku con prompt caching pero estas
heurísticas cubren el 95% de casos con coste cero.
"""

from __future__ import annotations

import re
from typing import Literal

Track = Literal["dev", "sysadmin"]
SalaryBand = Literal["high", "mid", "low", "unknown"]


# ---------------------------------------------------------------------------
# Track detection (dev vs sysadmin)
# ---------------------------------------------------------------------------

# Strong sysadmin signals (each match +2)
_SYSADMIN_STRONG = {
    "sysadmin", "system administrator", "administrator de sistemas",
    "administrador de sistemas", "infrastructure engineer", "linux administrator",
    "linux engineer", "site reliability", "sre engineer", "sre,",
    "devops engineer", "devops senior", "platform engineer",
    "cloud engineer", "cloud architect", "network engineer",
    "windows server", "active directory", "vmware", "vsphere",
    "ansible", "terraform", "kubernetes administrator", "k8s admin",
    "puppet", "chef config", "nagios", "zabbix", "prometheus admin",
    "veeam", "backup engineer", "operations engineer", "noc engineer",
    "infrastructure operations", "it operations",
}

# Medium sysadmin signals (+1 each)
_SYSADMIN_MEDIUM = {
    "bash scripting", "shell scripting", "monitoring", "grafana",
    "elk stack", "syslog", "nginx", "apache", "iptables", "firewall",
    "ldap", "samba", "rsync", "nfs", "ssh hardening", "cron",
    "ccna", "ccnp", "ccie", "lpic", "rhcsa", "rhce", "comptia",
    "incident response", "ticketing", "jira service",
}

# Strong dev signals (+2 each, sysadmin trumps if equal)
_DEV_STRONG = {
    "full-stack", "full stack", "fullstack", "frontend developer",
    "backend developer", "software engineer", "software developer",
    "react developer", "vue developer", "angular developer",
    "python developer", "node.js developer", "javascript developer",
    "ml engineer", "machine learning engineer", "data scientist",
    "ai engineer", "llm engineer", "rag engineer",
    "mobile developer", "ios developer", "android developer",
    "fastapi", "django framework", "spring boot", "express.js",
    "nextjs developer", "next.js developer",
}

# Medium dev signals
_DEV_MEDIUM = {
    "react", "vue.js", "angular", "tailwind", "typescript",
    "graphql", "rest api design", "celery", "pydantic",
    "ollama", "openai api", "anthropic api", "langchain",
    "stripe integration", "websockets", "openapi",
    "playwright", "cypress", "vitest", "jest",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def detect_track(title: str, description: str | None = None, tags: list[str] | None = None) -> Track:
    """Devuelve 'sysadmin' o 'dev' según el contenido. Default 'dev'."""
    blob = " ".join([_norm(title), _norm(description or ""), _norm(" ".join(tags or []))])

    sys_score = 0
    for kw in _SYSADMIN_STRONG:
        if kw in blob:
            sys_score += 2
    for kw in _SYSADMIN_MEDIUM:
        if kw in blob:
            sys_score += 1

    dev_score = 0
    for kw in _DEV_STRONG:
        if kw in blob:
            dev_score += 2
    for kw in _DEV_MEDIUM:
        if kw in blob:
            dev_score += 1

    # Title-only heuristics override if very explicit
    t = _norm(title)
    if any(p in t for p in ("devops", "sre", "sysadmin", "system admin", "infrastructure", "cloud engineer", "network engineer", "linux admin", "platform engineer")):
        return "sysadmin"
    if any(p in t for p in ("full stack", "full-stack", "fullstack", "software engineer", "react developer", "frontend", "backend developer", "ml engineer", "ai engineer")):
        return "dev"

    # Tie → dev (default career direction)
    return "sysadmin" if sys_score > dev_score else "dev"


# ---------------------------------------------------------------------------
# Salary band prediction for jobs with no listed salary
# ---------------------------------------------------------------------------

# Companies known to pay well (and often hire sysadmin/devops remote EU)
_HIGH_PAY_COMPANIES = {
    "canonical", "red hat", "redhat", "gitlab", "github", "datadog",
    "automattic", "doist", "buffer", "zapier", "elastic", "hashicorp",
    "cloudflare", "fastly", "stripe", "shopify", "auth0", "okta",
    "mongodb", "confluent", "snowflake", "databricks", "splunk",
    "vmware broadcom", "ibm", "oracle", "microsoft", "google",
    "amazon web services", "aws ", "meta", "netflix", "spotify",
    "atlassian", "n26", "revolut", "binance", "kraken", "coinbase",
    "factorial", "travelperk", "typeform", "holaluz",
    "voicemod", "jobandtalent", "cabify", "glovo",
    "open sistemas", "arquimea", "plain concepts", "capgemini",
    "deloitte", "ey ", "kpmg", "accenture",
    "sap ", "siemens", "bosch ",
}

# Mid-tier signals (decent but not top)
_MID_PAY_COMPANIES = {
    "everis", "indra", "ntt data", "altia", "viewnext", "minsait",
    "atos ", "gft", "babel ",
}

# Seniority keywords boost salary expectation
_SENIOR_TITLE = re.compile(
    r"\b(senior|staff|principal|lead|head\s+of|director|architect)\b", re.I
)
_JUNIOR_TITLE = re.compile(r"\b(junior|jr\.?|entry\s+level|trainee|intern)\b", re.I)

# Description signals
_HIGH_PAY_HINTS = (
    "competitive salary", "top of market", "above market",
    "stock options", "rsus", "equity package",
    "60k", "70k", "80k", "90k", "100k",
    "60.000", "70.000", "80.000", "90.000", "100.000",
    "60 000", "70 000", "80 000",
    "$120", "$130", "$140", "$150",
)
_LOW_PAY_HINTS = (
    "scholarship", "becario", "becaria", "trainee", "internship",
    "prácticas remuneradas", "intern position",
)

# Locations that historically pay more (per role)
_HIGH_PAY_LOC = (
    "united kingdom", "uk", "london", "switzerland", "zurich",
    "germany", "berlin", "munich", "amsterdam", "netherlands",
    "stockholm", "sweden", "denmark", "copenhagen",
    "united states", "usa", "san francisco", "new york",
    "remote eu", "remote europe", "remote worldwide", "remote global",
)
_LOW_PAY_LOC = (
    "india", "philippines", "pakistan", "bangladesh", "egypt",
    "mexico", "argentina", "colombia", "peru",
)


def predict_salary_band(
    title: str,
    company: str | None = None,
    description: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    currency: str | None = None,
) -> SalaryBand:
    """Devuelve 'high' | 'mid' | 'low' | 'unknown'.

    Si hay rango listado lo usamos directo (en EUR equivalente):
      - >= 45000 → high
      - >= 25000 → mid
      - < 25000  → low
    Si no, heurística por empresa + título + descripción + location.
    """
    if salary_max or salary_min:
        amt = salary_max or salary_min or 0
        cur = (currency or "EUR").upper()
        # Quick FX (rough — we're banding, not invoicing)
        if cur == "USD":
            amt *= 0.92
        elif cur == "GBP":
            amt *= 1.17
        elif cur in ("CHF",):
            amt *= 1.05
        if amt >= 45000:
            return "high"
        if amt >= 25000:
            return "mid"
        return "low"

    score = 0  # >2 = high, 0-2 = mid, <0 = low
    t = _norm(title)
    c = _norm(company or "")
    d = _norm(description or "")
    loc = _norm(location or "")

    # Company tier
    if any(brand in c for brand in _HIGH_PAY_COMPANIES):
        score += 2
    elif any(brand in c for brand in _MID_PAY_COMPANIES):
        score += 1

    # Title seniority
    if _SENIOR_TITLE.search(t):
        score += 2
    elif _JUNIOR_TITLE.search(t):
        score -= 2

    # Description signals
    if any(h in d for h in _HIGH_PAY_HINTS):
        score += 2
    if any(h in d for h in _LOW_PAY_HINTS):
        score -= 3

    # Location
    if any(h in loc for h in _HIGH_PAY_LOC):
        score += 1
    if any(h in loc for h in _LOW_PAY_LOC):
        score -= 2

    if score >= 3:
        return "high"
    if score >= 1:
        return "mid"
    if score <= -2:
        return "low"
    return "unknown"
