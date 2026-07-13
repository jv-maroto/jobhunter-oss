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
    """Vuelve a dejar la instancia como recien instalada, para rehacer el wizard.

    ANTES ESTO NO FUNCIONABA: solo borraba el draft y el marcador, pero
    `is_onboarded()` mira TAMBIEN cv_master.json y, al tener ya un nombre real,
    seguia devolviendo True -> el wizard no volvia nunca.

    Ahora ademas archivamos el cv_master actual (con backup timestamped, nunca se
    pierde) y dejamos una plantilla con `_README`, que es la señal que usa
    `detect.is_onboarded()` para saber que la instancia esta sin configurar.
    """
    draft_store.clear_draft()

    marker = settings.onboarding_marker_file
    if marker.exists():
        marker.unlink()

    backup_path: str | None = None
    cv_path = settings.cv_master_file
    if cv_path.exists():
        backups = cv_path.parent / "cv_master_backups"
        backups.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = backups / f"cv_master_{ts}.json"
        shutil.copy2(cv_path, dest)
        backup_path = str(dest)
        logger.info("onboarding reset: cv_master respaldado en %s", dest)

    cv_path.parent.mkdir(parents=True, exist_ok=True)
    cv_path.write_text(
        json.dumps(
            {
                "_README": (
                    "Instancia reseteada: completa el onboarding para regenerar tu "
                    "perfil. Tu CV anterior esta en app/data/cv_master_backups/."
                ),
                "personal": {"name": "", "email": ""},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Invalida la cache en memoria del perfil.
    try:
        from app.services import load_cv_master

        if hasattr(load_cv_master, "cache_clear"):
            load_cv_master.cache_clear()
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "onboarded": detect.is_onboarded(), "backup": backup_path}
