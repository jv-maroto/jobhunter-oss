"""Fusion de fragmentos (github/linkedin/cv) en un unico cv_master.

Estrategia: pre-merge DETERMINISTA (prioridad de identidad CV > LinkedIn > GitHub,
dedup de skills/experiencia/educacion) que produce cv_master + `field_sources`
(procedencia por campo, para los badges de la pantalla de revision) + `conflicts`
(valores discrepantes para resaltar). Opcionalmente una pasada LLM limpia/unifica
encima. NADA se escribe sin que el usuario confirme en la revision.
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.profile_extractor import generate_summaries

logger = logging.getLogger(__name__)

# Menor numero = mayor prioridad.
_SOURCE_PRIORITY = {"manual": 0, "cv": 1, "linkedin": 2, "github": 3}


def _rank(src: str) -> int:
    return _SOURCE_PRIORITY.get(src or "", 5)


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        k = _norm(it)
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def fuse(fragments: dict[str, dict], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Devuelve {cv_master, field_sources, conflicts, llm_used}."""
    base = base or {}
    frags = list(fragments.values())
    frags_by_priority = sorted(frags, key=lambda f: _rank(f.get("source", "")))

    field_sources: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []

    # ---- personal ----
    personal: dict[str, Any] = {}
    for frag in frags_by_priority:
        src = frag.get("source", "")
        for k, v in (frag.get("personal") or {}).items():
            if not v:
                continue
            key = f"personal.{k}"
            if k not in personal:
                personal[k] = v
                field_sources[key] = src
            elif _norm(personal[k]) != _norm(v):
                conflicts.append(
                    {
                        "field": key,
                        "kept": personal[k],
                        "kept_source": field_sources.get(key),
                        "other": v,
                        "other_source": src,
                    }
                )

    # ---- summaries (mayor prioridad no vacia) ----
    summary_es = ""
    summary_en = ""
    for frag in frags_by_priority:
        if not summary_es and frag.get("summary_es"):
            summary_es = frag["summary_es"]
            field_sources["summary_es"] = frag.get("source", "")
        if not summary_en and frag.get("summary_en"):
            summary_en = frag["summary_en"]
            field_sources["summary_en"] = frag.get("source", "")

    # ---- experience (dedup por empresa+rol, mayor prioridad gana) ----
    experience: list[dict] = []
    exp_seen: set[tuple[str, str]] = set()
    for frag in frags_by_priority:
        for e in frag.get("experience") or []:
            key = (_norm(e.get("company")), _norm(e.get("role")))
            if key == ("", "") or key in exp_seen:
                continue
            exp_seen.add(key)
            experience.append(e)
    if experience:
        field_sources["experience"] = "merged"

    # ---- education / certifications / languages (union dedup) ----
    def _union(field: str, key_fn) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for frag in frags_by_priority:
            for item in frag.get(field) or []:
                k = key_fn(item)
                if not k or k in seen:
                    continue
                seen.add(k)
                out.append(item)
        return out

    education = _union("education", lambda x: _norm(x.get("institution")) + "|" + _norm(x.get("degree")))
    certifications = _union("certifications", lambda x: _norm(x.get("name")))
    languages = _union("languages", lambda x: _norm(x.get("name")))

    # ---- skills (merge categorias, dedup case-insensitive) ----
    skills: dict[str, list[str]] = {}
    for frag in frags_by_priority:
        for cat, vals in (frag.get("skills") or {}).items():
            if not isinstance(vals, list):
                continue
            skills.setdefault(cat, [])
            skills[cat].extend(str(v) for v in vals if v)
    skills = {cat: _dedup_keep_order(vals) for cat, vals in skills.items() if vals}
    if skills:
        field_sources["skills"] = "merged"

    # ---- projects (github y demas) ----
    projects: list[dict] = []
    proj_seen: set[str] = set()
    for frag in frags_by_priority:
        for p in frag.get("projects") or []:
            k = _norm(p.get("name")) + "|" + _norm(p.get("url"))
            if k in proj_seen:
                continue
            proj_seen.add(k)
            projects.append(p)
    if projects:
        field_sources["projects"] = field_sources.get("projects", "github")

    # ---- ensamblado, preservando search_preferences de la base ----
    cv_master: dict[str, Any] = {
        "personal": personal,
        "summary_es": summary_es,
        "summary_en": summary_en,
        "languages": languages,
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "skills": skills,
        "projects": projects,
        "projects_highlight": projects[:3],
        "narratives": base.get("narratives", {}) or {},
        "search_preferences": base.get("search_preferences", {}) or {},
    }

    # ---- pasada LLM opcional: SOLO rellena summaries vacios ----
    # La fusion determinista es la AUTORIDAD: el LLM es lossy con datos de
    # identidad (puede tirar el github/email al "reorganizar"), asi que no le
    # dejamos tocar personal/experience/skills/projects.
    llm_used = False
    if not summary_es or not summary_en:
        summaries = generate_summaries(cv_master)
        if summaries.get("summary_es") and not summary_es:
            cv_master["summary_es"] = summaries["summary_es"]
            field_sources["summary_es"] = "ia"
            llm_used = True
        if summaries.get("summary_en") and not summary_en:
            cv_master["summary_en"] = summaries["summary_en"]
            field_sources["summary_en"] = "ia"
            llm_used = True

    return {
        "cv_master": cv_master,
        "field_sources": field_sources,
        "conflicts": conflicts,
        "llm_used": llm_used,
    }
