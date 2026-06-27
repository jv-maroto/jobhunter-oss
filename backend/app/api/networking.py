"""Endpoints de NETWORKING.

Sustituye la antigua pagina LinkedIn. Mantiene la cola de "personas a conectar"
(modelo Person) y, ademas, SUGIERE estrategicamente a quien conectar segun:

- Las skills del cv_master (load_cv_master).
- Las empresas a las que el usuario ha aplicado (Jobs con status applied/interviewing).

A partir de esos datos genera "arquetipos" de personas objetivo (p.ej.
"Backend Lead en {empresa}", "Reclutador {skill}") y los rankea por relevancia a
las skills del candidato. Reutiliza ademas las Persons existentes (pending/queued).

La redaccion del campo `reason` usa IA (tier=generation) si hay algun provider
disponible; si no, cae a una heuristica local. Todos los imports de IA son
perezosos (dentro de funciones) para no romper entornos sin las libs de IA.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.job import Job
from app.models.person import Person
from app.schemas.person import PersonOut
from app.services import load_cv_master

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/networking", tags=["networking"])

# Estados de Job que cuentan como "has aplicado / estas en proceso".
_APPLIED_STATUSES = ("applied", "interviewing")
# Estados de Person que siguen "vivos" para sugerir.
_ACTIVE_PERSON_STATUSES = ("pending", "queued")
# Limites para no inflar respuestas ni el coste de IA.
_MAX_SUGGESTIONS = 24
_MAX_COMPANIES = 8


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NetworkingSuggestion(BaseModel):
    """Una sugerencia de a quien conectar."""

    full_name: str | None = None
    headline: str
    company: str | None = None
    reason: str
    priority: int
    kind: str  # "person" | "archetype"
    skill_match: list[str] = []


class SuggestionsResponse(BaseModel):
    suggestions: list[NetworkingSuggestion]
    skills_used: list[str] = []
    companies_used: list[str] = []
    ai_used: bool = False


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str
    headline: str = ""
    company: str | None = None
    profile_url: str | None = None


# ---------------------------------------------------------------------------
# Helpers de extraccion de perfil
# ---------------------------------------------------------------------------


def _extract_skills(cv: dict[str, Any]) -> list[str]:
    """Aplana cv_master["skills"] (dict de categorias o lista) a una lista unica."""
    out: list[str] = []
    skills = cv.get("skills", {}) if isinstance(cv, dict) else {}
    if isinstance(skills, dict):
        for value in skills.values():
            if isinstance(value, list):
                out.extend(str(s) for s in value)
            elif isinstance(value, str):
                out.append(value)
    elif isinstance(skills, list):
        out.extend(str(s) for s in skills)

    seen: set[str] = set()
    result: list[str] = []
    for s in out:
        clean = s.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _extract_roles(cv: dict[str, Any]) -> list[str]:
    """Roles objetivo: search_preferences.roles + experience[].role."""
    roles: list[str] = []
    prefs = cv.get("search_preferences", {}) if isinstance(cv, dict) else {}
    for r in prefs.get("roles", []) or []:
        if isinstance(r, str) and r.strip():
            roles.append(r.strip())
    for exp in cv.get("experience", []) or []:
        if isinstance(exp, dict):
            role = exp.get("role")
            if isinstance(role, str) and role.strip():
                roles.append(role.strip())

    seen: set[str] = set()
    result: list[str] = []
    for r in roles:
        key = r.lower()
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def _skill_match(text: str, skills: list[str]) -> list[str]:
    """Skills del candidato que aparecen mencionadas en `text`."""
    if not text:
        return []
    low = text.lower()
    return [s for s in skills if s.lower() in low]


def _profile_title(cv: dict[str, Any]) -> str:
    personal = cv.get("personal", {}) if isinstance(cv, dict) else {}
    return str(personal.get("title") or "tu perfil")


# ---------------------------------------------------------------------------
# Heuristica de razones (fallback sin IA)
# ---------------------------------------------------------------------------


def _heuristic_reason(headline: str, company: str | None, skill_match: list[str]) -> str:
    stack = ", ".join(skill_match[:3]) if skill_match else "tu stack"
    if company:
        return (
            f"Aplicaste a {company}: un contacto interno como {headline} aumenta la "
            f"visibilidad de tu candidatura y comparte tecnologias de tu perfil ({stack})."
        )
    return (
        f"Perfil alineado con tu stack ({stack}). Conectar con {headline} abre la puerta "
        "a referrals y oportunidades en tu area."
    )


# ---------------------------------------------------------------------------
# Razones via IA (opcional, batch, con fallback)
# ---------------------------------------------------------------------------

_REASON_SYSTEM = (
    "Eres un coach de networking tecnico. Recibes el perfil de un candidato y una lista "
    "de personas/arquetipos objetivo a los que podria conectar para avanzar su busqueda "
    "de empleo. Para cada uno, redacta un motivo BREVE (max 220 caracteres), concreto y "
    "accionable en espanol, explicando POR QUE conectar y como ayuda. Evita relleno. "
    'Devuelve UNICAMENTE JSON con esta forma: {"reasons": {"0": "...", "1": "..."}} '
    "donde la clave es el indice de la persona en la lista."
)


def _ai_reasons(
    targets: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[int, str]:
    """Intenta redactar `reason` para cada target con IA (tier=generation).

    Devuelve {indice -> reason}. Si no hay IA o falla, devuelve {} (el caller usa
    la heuristica). Imports perezosos para entornos sin libs de IA.
    """
    if not targets:
        return {}
    try:
        from app.ai.client import parse_json_block, run_sync
        from app.ai.router import get_router

        router_ = get_router()
        if not router_.available_providers("generation"):
            return {}

        payload = {
            "candidate": profile,
            "targets": [
                {
                    "index": i,
                    "headline": t.get("headline"),
                    "company": t.get("company"),
                    "skill_match": t.get("skill_match", []),
                    "kind": t.get("kind"),
                }
                for i, t in enumerate(targets)
            ],
        }
        response = run_sync(
            router_.complete_for(
                tier="generation",
                system=_REASON_SYSTEM,
                user=json.dumps(payload, ensure_ascii=False),
                max_tokens=1200,
                temperature=0.5,
                json_mode=True,
            )
        )
        data = parse_json_block(response.content)
        raw = data.get("reasons", {}) if isinstance(data, dict) else {}
        out: dict[int, str] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    idx = int(k)
                except (TypeError, ValueError):
                    continue
                text = str(v).strip()
                if text:
                    out[idx] = text[:300]
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Networking: IA de reasons fallida, uso heuristica: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Construccion de sugerencias
# ---------------------------------------------------------------------------


def _person_suggestions(
    db: Session, skills: list[str]
) -> list[dict[str, Any]]:
    """Sugerencias derivadas de Persons existentes (pending/queued)."""
    stmt = (
        select(Person)
        .where(Person.status.in_(_ACTIVE_PERSON_STATUSES))
        .order_by(desc(Person.priority), desc(Person.created_at))
    )
    persons = db.execute(stmt).scalars().all()
    items: list[dict[str, Any]] = []
    for p in persons:
        match = _skill_match(f"{p.headline} {p.company or ''}", skills)
        priority = int(p.priority) + min(len(match) * 4, 20)
        items.append(
            {
                "full_name": p.full_name,
                "headline": p.headline or "Contacto",
                "company": p.company,
                "reason": (p.reason or "").strip(),
                "priority": min(priority, 99),
                "kind": "person",
                "skill_match": match,
            }
        )
    return items


def _archetype_suggestions(
    companies: list[str], skills: list[str], roles: list[str]
) -> list[dict[str, Any]]:
    """Arquetipos derivados de empresas aplicadas + skills + roles."""
    items: list[dict[str, Any]] = []
    top_skills = skills[:6]

    # 1) Por cada empresa a la que aplicaste: contactos internos clave.
    for company in companies[:_MAX_COMPANIES]:
        items.append(
            {
                "full_name": None,
                "headline": f"Engineering Lead / Hiring Manager en {company}",
                "company": company,
                "reason": "",
                "priority": 88,
                "kind": "archetype",
                "skill_match": top_skills[:3],
            }
        )
        items.append(
            {
                "full_name": None,
                "headline": f"Tech Recruiter en {company}",
                "company": company,
                "reason": "",
                "priority": 84,
                "kind": "archetype",
                "skill_match": top_skills[:2],
            }
        )

    # 2) Arquetipos por rol objetivo (peers / seniors de tu mismo rol).
    for role in roles[:3]:
        items.append(
            {
                "full_name": None,
                "headline": f"Senior {role} (red de pares)",
                "company": None,
                "reason": "",
                "priority": 70,
                "kind": "archetype",
                "skill_match": _skill_match(role, skills) or top_skills[:2],
            }
        )

    # 3) Arquetipos por skill estrella (reclutadores especializados).
    for skill in top_skills[:4]:
        items.append(
            {
                "full_name": None,
                "headline": f"Reclutador especializado en {skill}",
                "company": None,
                "reason": "",
                "priority": 66,
                "kind": "archetype",
                "skill_match": [skill],
            }
        )

    return items


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedup por (headline.lower, company.lower) conservando la mayor priority."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for it in items:
        key = (it["headline"].strip().lower(), (it.get("company") or "").strip().lower())
        prev = best.get(key)
        if prev is None or it["priority"] > prev["priority"]:
            best[key] = it
    return list(best.values())


@router.get("/suggestions", response_model=SuggestionsResponse)
def get_suggestions(
    limit: int = Query(default=_MAX_SUGGESTIONS, ge=1, le=50),
    ai: bool = Query(default=True, description="Usar IA para redactar razones"),
    db: Session = Depends(get_db),
) -> SuggestionsResponse:
    """Sugiere a quien conectar segun skills + empresas aplicadas."""
    cv = load_cv_master()
    skills = _extract_skills(cv)
    roles = _extract_roles(cv)

    company_rows = db.execute(
        select(Job.company)
        .where(Job.status.in_(_APPLIED_STATUSES))
        .where(Job.company.isnot(None))
        .distinct()
    ).all()
    companies = [c for (c,) in company_rows if c and c.strip()]

    items = _person_suggestions(db, skills) + _archetype_suggestions(
        companies, skills, roles
    )
    items = _dedupe(items)

    # Ranking: prioridad explicita + relevancia a skills.
    items.sort(
        key=lambda it: (it["priority"], len(it["skill_match"])),
        reverse=True,
    )
    items = items[:limit]

    # Redaccion de razones para los que no traen una (o todos si hay IA).
    ai_used = False
    if ai:
        profile = {
            "title": _profile_title(cv),
            "top_skills": skills[:10],
            "roles": roles[:5],
            "applied_companies": companies[:_MAX_COMPANIES],
        }
        needing = [it for it in items if not it["reason"]]
        ai_map = _ai_reasons(needing, profile)
        if ai_map:
            ai_used = True
            for local_idx, it in enumerate(needing):
                if local_idx in ai_map:
                    it["reason"] = ai_map[local_idx]

    for it in items:
        if not it["reason"]:
            it["reason"] = _heuristic_reason(
                it["headline"], it.get("company"), it["skill_match"]
            )

    return SuggestionsResponse(
        suggestions=[NetworkingSuggestion(**it) for it in items],
        skills_used=skills[:12],
        companies_used=companies[:_MAX_COMPANIES],
        ai_used=ai_used,
    )


@router.get("/people", response_model=list[PersonOut])
def list_people(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    """Lista Persons (status != ignored) ordenadas por priority."""
    stmt = (
        select(Person)
        .where(Person.status != "ignored")
        .order_by(desc(Person.priority), desc(Person.created_at))
        .limit(limit)
    )
    return [PersonOut.model_validate(p) for p in db.execute(stmt).scalars().all()]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "person"


@router.post("/people", response_model=PersonOut)
def create_person(body: PersonCreate, db: Session = Depends(get_db)) -> PersonOut:
    """Crea una Person manualmente."""
    profile_url = (body.profile_url or "").strip()
    if not profile_url:
        # profile_url es unique + NOT NULL: sintetizamos uno estable y unico.
        stamp = int(datetime.utcnow().timestamp())
        profile_url = f"manual://{_slugify(body.full_name)}-{stamp}"

    match = _skill_match(
        f"{body.headline} {body.company or ''}", _extract_skills(load_cv_master())
    )
    person = Person(
        full_name=body.full_name.strip() or "Contacto",
        headline=(body.headline or "").strip(),
        company=(body.company or None),
        profile_url=profile_url,
        reason=_heuristic_reason(body.headline or "este contacto", body.company, match),
        status="pending",
        priority=60 + min(len(match) * 5, 25),
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return PersonOut.model_validate(person)
