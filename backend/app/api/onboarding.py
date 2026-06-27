"""Endpoints del onboarding de primer uso (Pilar 1).

Local-first, sin auth (corre solo en localhost). Cada paso acumula un fragmento
en el draft (idempotente). `merge` fusiona; `complete` escribe cv_master.json y
marca la instancia como onboarded. NADA se persiste como perfil hasta `complete`.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.onboarding import detect, draft_store, fusion
from app.onboarding.cv_parser import extract_text
from app.onboarding.github_ingest import fetch_github_fragment
from app.onboarding.linkedin_parser import from_extension, parse_zip

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


@router.post("/merge")
def post_merge() -> dict[str, Any]:
    fragments = draft_store.get_fragments()
    if not fragments:
        raise HTTPException(status_code=400, detail="No hay fragmentos que fusionar")
    # Base = cv_master actual (para conservar search_preferences/narratives).
    base: dict[str, Any] = {}
    cv_path = settings.cv_master_file
    if cv_path.exists():
        try:
            cur = json.loads(cv_path.read_text(encoding="utf-8"))
            if "_README" not in cur:
                base = cur
        except Exception:  # noqa: BLE001
            base = {}
    result = fusion.fuse(fragments, base)
    draft_store.set_merged(result["cv_master"], result["field_sources"], result["conflicts"])
    return result


@router.get("/draft")
def get_draft() -> dict[str, Any]:
    return draft_store.load_draft()


class CompleteBody(BaseModel):
    cv_master: dict[str, Any]


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

    path = settings.cv_master_file
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backups = path.parent / "cv_master_backups"
        backups.mkdir(exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, backups / f"cv_master_{ts}.json")
    path.write_text(json.dumps(cv, ensure_ascii=False, indent=2), encoding="utf-8")

    # Invalida cache en memoria.
    try:
        from app.services import load_cv_master

        load_cv_master.cache_clear()
    except Exception:  # noqa: BLE001
        pass

    detect.mark_onboarded()
    draft_store.clear_draft()
    return {"ok": True, "path": str(path), "onboarded": True}


@router.post("/reset")
def post_reset() -> dict[str, Any]:
    """Solo dev: borra el draft y el marcador para volver a probar el wizard."""
    draft_store.clear_draft()
    marker = settings.onboarding_marker_file
    if marker.exists():
        marker.unlink()
    return {"ok": True}
