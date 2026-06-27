"""Mapeo host de la oferta -> plataforma + modo de aplicar preferido.

ATS con formulario propio -> extension (autofill + el user envia). Portales que
redirigen al sitio del empleador o que no son automatizables -> manual. LinkedIn
Easy Apply -> extension (sesion propia del usuario).
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.apply.base import ApplyMode

# (substring del host/url, platform_id, modo). Primer match gana.
HOST_RULES: list[tuple[str, str, ApplyMode]] = [
    ("linkedin.com/jobs", "linkedin", ApplyMode.extension),
    ("linkedin.com", "linkedin", ApplyMode.extension),
    ("greenhouse.io", "greenhouse", ApplyMode.extension),
    ("lever.co", "lever", ApplyMode.extension),
    ("ashbyhq.com", "ashby", ApplyMode.extension),
    ("workable.com", "workable", ApplyMode.extension),
    ("smartrecruiters.com", "smartrecruiters", ApplyMode.extension),
    ("recruitee.com", "recruitee", ApplyMode.extension),
    ("teamtailor.com", "teamtailor", ApplyMode.extension),
    ("personio.", "personio", ApplyMode.extension),
    ("myworkdayjobs.com", "workday", ApplyMode.extension),
    ("icims.com", "icims", ApplyMode.extension),
    ("bamboohr.com", "bamboohr", ApplyMode.extension),
    ("breezy.hr", "breezy", ApplyMode.extension),
    ("welcometothejungle.com", "wttj", ApplyMode.extension),
    ("wellfound.com", "wellfound", ApplyMode.extension),
    ("angel.co", "wellfound", ApplyMode.extension),
    ("smartapply.indeed.com", "indeed", ApplyMode.extension),
    ("factorialhr.com", "factorial", ApplyMode.extension),
    ("pinpointhq.com", "pinpoint", ApplyMode.extension),
    # Portales que redirigen / sin form automatizable -> manual.
    ("indeed.com", "indeed", ApplyMode.manual),
    ("tecnoempleo.com", "tecnoempleo", ApplyMode.manual),
    ("remotive.com", "remotive", ApplyMode.manual),
    ("weworkremotely.com", "weworkremotely", ApplyMode.manual),
    ("jobtechdev.se", "platsbanken", ApplyMode.manual),
    ("glassdoor.", "glassdoor", ApplyMode.manual),
]


def host_to_platform(url: str) -> tuple[str, ApplyMode]:
    """Devuelve (platform_id, modo_aplicar) para una URL de oferta."""
    u = (url or "").lower()
    host = urlparse(u).netloc
    for needle, pid, mode in HOST_RULES:
        if needle in u or needle in host:
            return pid, mode
    # ATS desconocido: por defecto manual (la extension no tiene host_permission).
    return "unknown", ApplyMode.manual
