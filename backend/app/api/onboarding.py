"""Endpoints del onboarding de primer uso (Pilar 1).

Local-first, sin auth (corre solo en localhost). Cada paso acumula un fragmento
en el draft (idempotente). `merge` fusiona; `complete` escribe cv_master.json y
marca la instancia como onboarded. NADA se persiste como perfil hasta `complete`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.onboarding import detect, draft_store, fusion
from app.onboarding.cv_parser import extract_text
from app.onboarding.github_ingest import fetch_github_fragment
from app.onboarding.linkedin_parser import from_extension, parse_zip
from app.onboarding.schema import CvMaster
from app.profile_store import read_profile, write_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status")
def get_status() -> dict[str, Any]:
    return {"onboarded": detect.is_onboarded()}


class GithubBody(BaseModel):
    username: str


@router.post("/github")
def post_github(body: GithubBody) -> dict[str, Any]:
    try:
        fragment = fetch_github_fragment(body.username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GitHub API fallo: {exc}") from exc
    draft_store.save_fragment("github", fragment)
    return {"ok": True, "fragment": fragment}


@router.post("/cv")
async def post_cv(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichero vacio")
    text, warnings = extract_text(file.filename or "", data)
    # Import perezoso: el extractor IA toca el router (degrada sin LLM).
    from app.ai.profile_extractor import structure_cv_text

    fragment = structure_cv_text(text, source="cv")
    if warnings:
        fragment.setdefault("warnings", []).extend(warnings)
    draft_store.save_fragment("cv", fragment)
    return {"ok": True, "fragment": fragment, "warnings": warnings, "chars": len(text)}


@router.post("/linkedin")
async def post_linkedin(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichero vacio")
    name = (file.filename or "").lower()
    if name.endswith(".zip"):
        try:
            fragment = parse_zip(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif name.endswith(".pdf"):
        text, warnings = extract_text(file.filename or "", data)
        from app.ai.profile_extractor import structure_cv_text

        fragment = structure_cv_text(text, source="linkedin")
        if warnings:
            fragment.setdefault("warnings", []).extend(warnings)
    else:
        raise HTTPException(
            status_code=400,
            detail="Sube el .zip del export oficial de LinkedIn o el PDF de tu perfil.",
        )
    draft_store.save_fragment("linkedin", fragment)
    return {"ok": True, "fragment": fragment}


@router.post("/linkedin/from-extension")
def post_linkedin_extension(payload: dict[str, Any]) -> dict[str, Any]:
    fragment = from_extension(payload)
    draft_store.save_fragment("linkedin", fragment)
    return {"ok": True, "fragment": fragment}


class LinkedinPasteBody(BaseModel):
    text: str


@router.post("/linkedin/paste")
def post_linkedin_paste(body: LinkedinPasteBody) -> dict[str, Any]:
    """Atajo rapido al ZIP: el usuario pega el texto de su perfil y lo estructura la IA."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Texto vacio")
    from app.ai.profile_extractor import structure_cv_text

    fragment = structure_cv_text(body.text, source="linkedin")
    draft_store.save_fragment("linkedin", fragment)
    return {"ok": True, "fragment": fragment}


@router.post("/merge")
def post_merge() -> dict[str, Any]:
    fragments = draft_store.get_fragments()
    try:
        base = draft_store.load_draft().get("base") or read_profile()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if "_README" in base:
        base = {}
    if not fragments and not base:
        raise HTTPException(status_code=400, detail="No hay perfil ni fragmentos que fusionar")
    result = fusion.fuse(fragments, base)
    draft_store.set_merged(result["cv_master"], result["field_sources"], result["conflicts"])
    return result


@router.get("/draft")
def get_draft() -> dict[str, Any]:
    return draft_store.load_draft()


class CompleteBody(BaseModel):
    cv_master: dict[str, Any]


@router.put("/draft")
def put_draft(body: CompleteBody) -> dict[str, Any]:
    try:
        CvMaster.model_validate(body.cv_master)
        return draft_store.save_review(body.cv_master)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/complete")
def post_complete(body: CompleteBody) -> dict[str, Any]:
    cv = body.cv_master
    if not isinstance(cv, dict) or not (cv.get("personal") or {}).get("name"):
        raise HTTPException(status_code=400, detail="cv_master invalido: falta personal.name")

    cv.pop("_README", None)
    cv.setdefault("_meta", {})
    cv["_meta"].update(
        {
            "schema_version": 2,
            "onboarded_at": datetime.utcnow().isoformat(),
            "sources": list(draft_store.get_fragments().keys()),
        }
    )

    try:
        write_profile(cv)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    detect.mark_onboarded()
    draft_store.clear_draft()
    return {"ok": True, "path": str(settings.cv_master_file), "onboarded": True}


class RolesBody(BaseModel):
    # Opcional: si se aporta un cv_master, se usa ese; si no, draft -> cv_master.json.
    cv_master: dict[str, Any] | None = None


def _current_cv_for_roles() -> dict[str, Any]:
    """CV de referencia para sugerir roles: draft fusionado o cv_master.json."""
    draft = draft_store.load_draft()
    merged = (draft.get("merged") or {}).get("cv_master") if isinstance(draft, dict) else None
    if isinstance(merged, dict) and merged:
        return merged
    cv_path = settings.cv_master_file
    if cv_path.exists():
        try:
            cur = json.loads(cv_path.read_text(encoding="utf-8"))
            if isinstance(cur, dict) and "_README" not in cur:
                return cur
        except Exception:  # noqa: BLE001
            return {}
    return {}


@router.post("/roles")
def post_roles(body: RolesBody | None = None) -> dict[str, Any]:
    """Sugiere 1-4 roles de trabajo a partir del perfil (IA o heuristica).

    Body opcional: {cv_master?}. Si no se aporta, usa el draft fusionado o el
    cv_master.json actual. Devuelve {roles: [{id, label, why}]}.
    """
    from app.onboarding.roles import suggest_roles

    cv = body.cv_master if (body is not None and body.cv_master) else _current_cv_for_roles()
    return {"roles": suggest_roles(cv)}


@router.post("/reset")
def post_reset() -> dict[str, Any]:
    try:
        cv = read_profile()
        backup = write_profile(cv) if cv else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    draft_store.start_from_profile(cv if "_README" not in cv else {})
    marker = settings.onboarding_marker_file
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("in_progress", encoding="utf-8")
    return {"ok": True, "onboarded": False, "backup": str(backup) if backup else None}
