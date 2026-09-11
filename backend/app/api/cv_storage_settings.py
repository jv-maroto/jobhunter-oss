"""Settings endpoints for CV storage location + naming scheme.

Exposes two operations to the UI:
  GET  /settings/cv-storage  → current config + available schemes
  PUT  /settings/cv-storage  → save new config
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import app_settings as svc
from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NamingOption(BaseModel):
    key: str
    label: str
    example: str


class CvStorageConfig(BaseModel):
    root_dir: str = Field(..., description="Absolute path where per-app folders live")
    naming_scheme: str
    default_root_dir: str
    options: list[NamingOption]


class CvStorageUpdate(BaseModel):
    root_dir: str | None = None
    naming_scheme: str | None = None
    # When true, existing folders are renamed to match the new scheme.
    rename_existing: bool = False


class CvStorageUpdateResult(BaseModel):
    root_dir: str
    naming_scheme: str
    renamed: int = 0
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _default_root() -> Path:
    return (settings.data_path / "applications").resolve()


@router.get("/cv-storage", response_model=CvStorageConfig)
def get_cv_storage(db: Session = Depends(get_db)) -> CvStorageConfig:
    default = _default_root()
    return CvStorageConfig(
        root_dir=str(svc.cv_root_dir(db, fallback=default)),
        naming_scheme=svc.cv_naming_scheme(db),
        default_root_dir=str(default),
        options=[
            NamingOption(key=k, label=label, example=example)
            for k, (label, example) in svc.NAMING_SCHEMES.items()
        ],
    )


def _company_slug(name: str | None, job_id: int) -> str:
    if name:
        s = unicodedata.normalize("NFD", name)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
        s = s[:60].rstrip("-")
        if s:
            return s
    return str(job_id)


@router.put("/cv-storage", response_model=CvStorageUpdateResult)
def put_cv_storage(
    payload: CvStorageUpdate, db: Session = Depends(get_db)
) -> CvStorageUpdateResult:
    warnings: list[str] = []

    # Validate + normalise root_dir
    new_root: Path | None = None
    if payload.root_dir is not None:
        expanded = Path(payload.root_dir).expanduser()
        if not expanded.is_absolute():
            raise HTTPException(
                status_code=422,
                detail=f"root_dir debe ser una ruta absoluta: {payload.root_dir!r}",
            )
        try:
            expanded.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"No se puede crear la carpeta {expanded}: {exc}",
            ) from exc
        # Check writable
        if not os.access(expanded, os.W_OK):
            raise HTTPException(
                status_code=422,
                detail=f"La carpeta {expanded} no es escribible.",
            )
        new_root = expanded.resolve()

    # Validate scheme
    new_scheme: str | None = None
    if payload.naming_scheme is not None:
        if payload.naming_scheme not in svc.NAMING_SCHEMES:
            raise HTTPException(
                status_code=422,
                detail=f"naming_scheme desconocido: {payload.naming_scheme!r}",
            )
        new_scheme = payload.naming_scheme

    old_root = svc.cv_root_dir(db, fallback=_default_root())
    old_scheme = svc.cv_naming_scheme(db)

    # Persist
    pairs = []
    if new_root is not None:
        pairs.append((svc.KEY_CV_ROOT, str(new_root)))
    if new_scheme is not None:
        pairs.append((svc.KEY_CV_NAMING, new_scheme))
    if pairs:
        svc.set_settings(db, pairs)

    final_root = new_root or old_root
    final_scheme = new_scheme or old_scheme

    renamed = 0
    if payload.rename_existing:
        renamed, warnings = _migrate_existing_folders(
            db=db,
            old_root=old_root,
            new_root=final_root,
            new_scheme=final_scheme,
        )

    return CvStorageUpdateResult(
        root_dir=str(final_root),
        naming_scheme=final_scheme,
        renamed=renamed,
        warnings=warnings,
    )


def _migrate_existing_folders(
    db: Session,
    old_root: Path,
    new_root: Path,
    new_scheme: str,
) -> tuple[int, list[str]]:
    """Rename each existing per-application folder under `old_root` to the
    name dictated by `new_scheme`, then move to `new_root` when they differ.

    Returns (count_renamed, warnings).
    """
    warnings: list[str] = []
    if not old_root.exists():
        return 0, ["La carpeta actual no existe todavía."]

    # Build a mapping folder → job (best-effort: name contains the id, or the
    # folder matches known slug patterns).
    jobs_by_id = {
        j.id: j for j in db.execute(select(Job)).scalars().all()
    }

    from datetime import date as _d
    today_iso = _d.today().isoformat()

    renamed_count = 0
    for entry in sorted(old_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue

        # Try to find job id embedded in the folder name
        m = re.search(r"(\d{2,})", entry.name)
        if not m:
            continue
        try:
            candidate_id = int(m.group(1))
        except ValueError:
            continue

        job = jobs_by_id.get(candidate_id)
        if job is None:
            warnings.append(
                f"'{entry.name}' → no encontré el job {candidate_id} en la BD; salto."
            )
            continue

        slug = _company_slug(job.company, job.id)
        new_name = svc.build_folder_name(new_scheme, slug, job.id, today_iso)
        target = new_root / new_name
        if target.resolve() == entry.resolve():
            continue
        if target.exists():
            warnings.append(
                f"'{entry.name}' → destino '{target.name}' ya existe. Salto."
            )
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(target))
            renamed_count += 1
        except OSError as exc:
            warnings.append(f"'{entry.name}': {exc}")
            continue

        # Fix application row paths that reference this folder
        old_frag = f"{old_root}/{entry.name}/"
        new_frag = f"{new_root}/{new_name}/"
        for app in db.execute(
            select(Application).where(Application.job_id == job.id)
        ).scalars().all():
            if app.cv_path and old_frag in app.cv_path:
                app.cv_path = app.cv_path.replace(old_frag, new_frag)
            if app.cover_letter_path and old_frag in app.cover_letter_path:
                app.cover_letter_path = app.cover_letter_path.replace(
                    old_frag, new_frag
                )
    db.commit()
    return renamed_count, warnings
