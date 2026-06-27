"""Persistencia local del estado/credenciales de Gmail (data/integrations/).

Todo en disco del usuario, fuera de git. Ficheros:
- gmail_state.json: {account, mode, scope, connected_at, last_sync_at}
- gmail_token.json: token OAuth (modo api)
- client_secret.json: OAuth client del usuario (modo api)
- gmail_imap.json: {email, app_password} (modo imap)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _path(name: str):
    return settings.integrations_path / name


STATE_FILE = "gmail_state.json"
TOKEN_FILE = "gmail_token.json"
CLIENT_SECRET_FILE = "client_secret.json"
IMAP_FILE = "gmail_imap.json"


def load_state() -> dict[str, Any]:
    p = _path(STATE_FILE)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_state(state: dict[str, Any]) -> None:
    p = _path(STATE_FILE)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def update_state(**fields: Any) -> dict[str, Any]:
    state = load_state()
    state.update(fields)
    save_state(state)
    return state


def set_last_sync(when: datetime | None = None) -> None:
    update_state(last_sync_at=(when or datetime.utcnow()).isoformat())


def write_secure(name: str, content: str) -> None:
    """Escribe un fichero de credenciales con permisos restrictivos."""
    p = _path(name)
    p.write_text(content, encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except Exception:  # noqa: BLE001 (Windows ignora chmod)
        pass


def read_text(name: str) -> str | None:
    p = _path(name)
    return p.read_text(encoding="utf-8") if p.exists() else None


def disconnect() -> None:
    for name in (STATE_FILE, TOKEN_FILE, IMAP_FILE):
        p = _path(name)
        if p.exists():
            try:
                p.unlink()
            except Exception as exc:  # noqa: BLE001
                logger.warning("no se pudo borrar %s: %s", name, exc)
