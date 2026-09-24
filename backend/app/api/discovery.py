"""One-click discovery endpoints, registered before /jobs/{id}."""
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.discovery import discovery_status, reserve_discovery, run_discovery
from app.onboarding.detect import is_onboarded

router = APIRouter(prefix="/jobs", tags=["discovery"])


@router.post("/discover-now", status_code=202)
def discover_now(background_tasks: BackgroundTasks):
    if not is_onboarded():
        raise HTTPException(status_code=409, detail="Completa tu perfil antes de buscar ofertas")
    if not reserve_discovery():
        return {**discovery_status(), "status": "already_running"}
    background_tasks.add_task(run_discovery)
    return {**discovery_status(), "status": "started"}


@router.get("/discover-status")
def discover_status():
    return discovery_status()
