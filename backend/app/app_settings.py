"""Read/write app-wide settings persisted in SQLite via AppSetting.

Values are stored as plain strings and cast in helpers. Everything the
user can tweak from /settings without restarting the backend lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting

# ---------------------------------------------------------------------------
# CV storage keys
# ---------------------------------------------------------------------------
KEY_CV_ROOT = "cv_storage.root"           # Absolute path where {folder}/ lives
KEY_CV_NAMING = "cv_storage.naming"       # One of NAMING_SCHEMES

# Predefined folder naming schemes. Each entry: (key, human label, example).
NAMING_SCHEMES: dict[str, tuple[str, str]] = {
    "company_id": (
        "Empresa + ID  (recomendado)",
        "acme-3028",
    ),
    "company": (
        "Solo empresa",
        "acme",
    ),
    "id_only": (
        "Solo ID de la oferta",
        "job-3028",
    ),
    "date_company": (
        "Fecha + empresa",
        "2026-09-10-acme",
    ),
    "date_company_id": (
        "Fecha + empresa + ID",
        "2026-09-10-acme-3028",
    ),
    "date_id": (
        "Fecha + ID",
        "2026-09-10-job-3028",
    ),
}
DEFAULT_NAMING = "company_id"


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row is not None else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def set_settings(db: Session, pairs: Iterable[tuple[str, str]]) -> None:
    """Batch upsert; single commit."""
    for k, v in pairs:
        row = db.get(AppSetting, k)
        if row is None:
            db.add(AppSetting(key=k, value=v))
        else:
            row.value = v
    db.commit()


# ---------------------------------------------------------------------------
# CV storage — typed accessors
# ---------------------------------------------------------------------------

def cv_root_dir(db: Session, fallback: Path) -> Path:
    """Absolute Path where per-application folders live."""
    v = get_setting(db, KEY_CV_ROOT, "").strip()
    if not v:
        return fallback
    return Path(v).expanduser().resolve()


def cv_naming_scheme(db: Session) -> str:
    v = get_setting(db, KEY_CV_NAMING, "").strip()
    return v if v in NAMING_SCHEMES else DEFAULT_NAMING


# ---------------------------------------------------------------------------
# Folder name builder — used by jobs.py to place CVs in the user's format
# ---------------------------------------------------------------------------

def build_folder_name(
    scheme: str,
    company_slug: str,
    job_id: int,
    today_iso: str,
) -> str:
    """Turn a scheme key + inputs into the final folder name."""
    slug = company_slug or "unknown"
    if scheme == "company_id":
        return f"{slug}-{job_id}" if slug != str(job_id) else f"job-{job_id}"
    if scheme == "company":
        return slug if slug != str(job_id) else f"job-{job_id}"
    if scheme == "id_only":
        return f"job-{job_id}"
    if scheme == "date_company":
        return f"{today_iso}-{slug}" if slug != str(job_id) else f"{today_iso}-job-{job_id}"
    if scheme == "date_company_id":
        return f"{today_iso}-{slug}-{job_id}" if slug != str(job_id) else f"{today_iso}-job-{job_id}"
    if scheme == "date_id":
        return f"{today_iso}-job-{job_id}"
    # unknown → safe default
    return f"{slug}-{job_id}" if slug != str(job_id) else f"job-{job_id}"
