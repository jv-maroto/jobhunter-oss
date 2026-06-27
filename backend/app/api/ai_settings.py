"""Endpoints de configuracion de IA (/settings/ai). Local-first, sin auth.

Lee/escribe el keystore (data/integrations/ai.json) y reconstruye el router
global tras cada cambio. NUNCA devuelve las claves en claro (solo `has_key`).

Contrato:
- GET  /settings/ai       -> estado publico (modo, provider, scraping, has_key, ...)
- PUT  /settings/ai       -> persiste cambios parciales y reconstruye el router
- POST /settings/ai/test  -> llamada minima al LLM activo: {ok, provider, error?}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.ai import keystore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])


def _public_state() -> dict[str, Any]:
    """Shape comun de GET y PUT. Nunca incluye claves en claro."""
    state = keystore.get_state()
    return {
        "ai_mode": state["ai_mode"],
        "ai_cloud_provider": state["ai_cloud_provider"],
        "ai_scraping_enabled": state["ai_scraping_enabled"],
        "has_key": {p: keystore.has_key(p) for p in keystore.PROVIDERS},
        "local_available": keystore.local_available(),
        "active": keystore.active_label(),
    }


@router.get("")
def get_ai_settings() -> dict[str, Any]:
    return _public_state()


class AiKeys(BaseModel):
    anthropic: str | None = None
    openai: str | None = None
    gemini: str | None = None


class AiSettingsUpdate(BaseModel):
    ai_mode: str | None = None
    ai_cloud_provider: str | None = None
    ai_scraping_enabled: bool | None = None
    keys: AiKeys | None = None


def _rebuild_router() -> None:
    try:
        from app.ai.cost_tracker import get_cost_tracker
        from app.ai.router import build_default_router, set_router

        set_router(build_default_router(cost_tracker=get_cost_tracker()))
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo reconstruir el router IA tras guardar: %s", exc)


@router.put("")
def put_ai_settings(body: AiSettingsUpdate) -> dict[str, Any]:
    partial: dict[str, Any] = {}
    if body.ai_mode is not None:
        partial["ai_mode"] = body.ai_mode
    if body.ai_cloud_provider is not None:
        partial["ai_cloud_provider"] = body.ai_cloud_provider
    if body.ai_scraping_enabled is not None:
        partial["ai_scraping_enabled"] = body.ai_scraping_enabled
    if body.keys is not None:
        keys: dict[str, Any] = {}
        for prov in keystore.PROVIDERS:
            val = getattr(body.keys, prov, None)
            if val is not None:
                keys[prov] = val
        if keys:
            partial["keys"] = keys

    keystore.set_state(partial)
    _rebuild_router()
    return _public_state()


@router.post("/test")
def test_ai() -> dict[str, Any]:
    """Llamada minima al LLM activo. Reporta el provider que realmente respondio."""
    label = keystore.active_label()
    if label == "off":
        return {
            "ok": False,
            "provider": "off",
            "error": "IA desactivada (modo off o sin claves configuradas).",
        }
    try:
        from app.ai.client import run_sync
        from app.ai.router import get_router

        resp = run_sync(
            get_router().complete_for(
                tier="scoring",
                system="You are a healthcheck. Reply with the single word: ok.",
                user="Reply with: ok",
                max_tokens=16,
                temperature=0.0,
                cache_system=False,
            )
        )
        ok = bool(resp.content and resp.content.strip())
        return {
            "ok": ok,
            "provider": resp.provider or label,
            "error": None if ok else "Respuesta vacia del modelo.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "provider": label, "error": str(exc)[:300]}
