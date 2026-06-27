"""Keystore runtime de configuracion de IA (data/integrations/ai.json).

Persiste el modo de IA, el proveedor cloud preferido, el flag de scraping IA y
las claves API que el usuario introduce desde la UI. El router de IA PREFIERE
estos valores sobre los de .env/settings (asi el usuario puede meter claves sin
tocar el .env).

Forma del fichero:
{
  "ai_mode": "auto"|"cloud"|"local"|"off",
  "ai_cloud_provider": "anthropic"|"openai"|"gemini",
  "ai_scraping_enabled": bool,
  "keys": {"anthropic": "", "openai": "", "gemini": ""}
}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

AI_STORE_FILE = "ai.json"
PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "gemini")
VALID_MODES: tuple[str, ...] = ("auto", "cloud", "local", "off")


def _path():
    return settings.integrations_path / AI_STORE_FILE


def _defaults() -> dict[str, Any]:
    return {
        "ai_mode": settings.ai_mode,
        "ai_cloud_provider": settings.ai_cloud_provider,
        "ai_scraping_enabled": bool(settings.ai_scraping_enabled),
        "keys": {p: "" for p in PROVIDERS},
    }


def get_state() -> dict[str, Any]:
    """Estado completo: el fichero del keystore fusionado con los defaults de settings."""
    state = _defaults()
    p = _path()
    if p.exists():
        try:
            disk = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(disk, dict):
                for k in ("ai_mode", "ai_cloud_provider", "ai_scraping_enabled"):
                    if disk.get(k) is not None:
                        state[k] = disk[k]
                disk_keys = disk.get("keys") or {}
                if isinstance(disk_keys, dict):
                    for prov in PROVIDERS:
                        val = disk_keys.get(prov)
                        if val:
                            state["keys"][prov] = str(val)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai keystore ilegible, usando defaults: %s", exc)
    # Normaliza valores invalidos.
    if state.get("ai_mode") not in VALID_MODES:
        state["ai_mode"] = "auto"
    if state.get("ai_cloud_provider") not in PROVIDERS:
        state["ai_cloud_provider"] = "anthropic"
    state["ai_scraping_enabled"] = bool(state.get("ai_scraping_enabled"))
    return state


def _write(state: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except Exception:  # noqa: BLE001 (Windows ignora chmod)
        pass


def set_state(partial: dict[str, Any]) -> dict[str, Any]:
    """Fusiona `partial` con el estado actual y persiste. Devuelve el estado nuevo.

    `partial` admite: ai_mode, ai_cloud_provider, ai_scraping_enabled, keys{...}.
    Una clave con valor vacio ("") la BORRA del keystore (vuelve a settings/.env).
    """
    state = get_state()
    if partial.get("ai_mode") in VALID_MODES:
        state["ai_mode"] = partial["ai_mode"]
    if partial.get("ai_cloud_provider") in PROVIDERS:
        state["ai_cloud_provider"] = partial["ai_cloud_provider"]
    if partial.get("ai_scraping_enabled") is not None:
        state["ai_scraping_enabled"] = bool(partial["ai_scraping_enabled"])
    keys = partial.get("keys")
    if isinstance(keys, dict):
        for prov in PROVIDERS:
            if prov in keys:
                val = keys[prov]
                state["keys"][prov] = str(val).strip() if val else ""
    _write(state)
    return state


def get_key(provider: str) -> str:
    """Clave del keystore; si vacia, cae a settings.<provider>_api_key (.env)."""
    provider = (provider or "").lower()
    if provider not in PROVIDERS:
        return ""
    state = get_state()
    val = (state.get("keys") or {}).get(provider, "")
    if val:
        return str(val)
    return getattr(settings, f"{provider}_api_key", "") or ""


def has_key(provider: str) -> bool:
    return bool(get_key(provider))


def local_available() -> bool:
    """True si Ollama responde en settings.ollama_base_url (modo local)."""
    try:
        import httpx

        base = settings.ollama_base_url.rstrip("/")
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{base}/api/tags")
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def resolve_mode() -> str:
    """Resuelve el modo efectivo: 'cloud' | 'local' | 'off'.

    auto -> cloud si hay clave del ai_cloud_provider; si no, local si Ollama
    responde; si no, off.
    """
    state = get_state()
    mode = state.get("ai_mode", "auto")
    if mode in ("cloud", "local", "off"):
        return mode
    # auto
    if has_key(state.get("ai_cloud_provider", "anthropic")):
        return "cloud"
    if local_available():
        return "local"
    return "off"


def active_label() -> str:
    """Etiqueta del LLM activo: el provider cloud elegido, 'ollama' u 'off'."""
    mode = resolve_mode()
    if mode == "cloud":
        return get_state().get("ai_cloud_provider", "anthropic")
    if mode == "local":
        return "ollama"
    return "off"
