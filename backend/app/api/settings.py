"""Settings endpoints: read/write cv_master.json + future user preferences.

In the self-hosted, single-user model each instance lives on the user's
machine, so we don't need auth here — the dashboard runs only on localhost.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.profile_store import read_profile, write_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/cv_master")
def get_cv_master() -> dict[str, Any]:
    """Returns the raw cv_master.json contents."""
    try:
        return read_profile()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"cv_master inválido: {exc}") from exc


@router.put("/cv_master")
def put_cv_master(payload: dict[str, Any]) -> dict[str, Any]:
    """Overwrites cv_master.json with the provided JSON. Backs up the previous version."""
    try:
        write_profile(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = settings.cv_master_file
    return {"ok": True, "path": str(path), "size": path.stat().st_size}


class FeatureFlags(BaseModel):
    """Toggles for the public/self-hosted version.

    By default everything is on for the maintainer. A community user who
    cloned the repo can flip these off in their .env to hide features they
    don't care about (post generation, comment generation, etc.).
    """
    enable_post_generation: bool = True
    enable_image_generation: bool = True
    enable_comment_suggestions: bool = True
    enable_trending_news: bool = True


@router.get("/features", response_model=FeatureFlags)
def get_features() -> FeatureFlags:
    """Returns the feature flags read from environment (or defaults)."""
    return FeatureFlags(
        enable_post_generation=getattr(settings, "enable_post_generation", True),
        enable_image_generation=getattr(settings, "enable_image_generation", True),
        enable_comment_suggestions=getattr(settings, "enable_comment_suggestions", True),
        enable_trending_news=getattr(settings, "enable_trending_news", True),
    )
