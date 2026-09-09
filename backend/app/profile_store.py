from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.onboarding.schema import CvMaster

logger = logging.getLogger(__name__)

def read_profile() -> dict[str, Any]:
    path = settings.cv_master_file
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Profile must be a JSON object")
    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as file:
            temporary = file.name
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def write_profile(cv: dict[str, Any]) -> Path | None:
    # Validate without serializing the model: defaults must not create claims
    # about salary, permission to work, or skills the user never supplied.
    CvMaster.model_validate(cv)
    json.dumps(cv, allow_nan=False)
    path = settings.cv_master_file
    backup = None
    if path.exists():
        read_profile()
        backups = path.parent / "cv_master_backups"
        backups.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup = backups / f"cv_master_{stamp}.json"
        shutil.copy2(path, backup)
    atomic_write_json(path, cv)
    for module_name, attribute in (("app.services", "load_cv_master"),
                                   ("app.ai.profile_context", "_cv")):
        cached = getattr(sys.modules.get(module_name), attribute, None)
        if cached is not None:
            cached.cache_clear()
    try:
        from sqlalchemy import inspect

        from app.db import SessionLocal, engine
        from app.services import refresh_job_metadata

        if inspect(engine).has_table("jobs"):
            with SessionLocal() as db:
                refresh_job_metadata(db, cv)
    except Exception:
        logger.exception("Profile saved, but pending job metadata could not be refreshed")
    return backup
