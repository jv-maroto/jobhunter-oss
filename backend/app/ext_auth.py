"""Shared secret authentication for /ext/* endpoints.

Rationale: `/ext/profile` returns the candidate's CV master narrative, phone,
email and salary preferences. On a single-user machine there's no OS-level
process boundary — any malicious tab (or an unrelated Chrome extension) can
hit `http://localhost:8000/ext/profile` and exfiltrate the whole thing.
A shared secret between backend and the JobHunter extension raises the bar:
the caller has to have read `chrome.storage.local`, which requires being
either our extension or someone with local disk access (in which case they
already have the SQLite DB).

Behaviour:
- First boot generates `data/ext_token.txt` with a random 32-byte token.
- `/ext/token` returns it (only callable from a browser extension origin;
  bootstrap uses the CORS regex that already restricts to chrome-extension://).
- Every other `/ext/*` endpoint requires `X-Extension-Token: <token>`.
- If the token file has never existed (fresh clone), auth is off — no breaking
  changes for existing users. The token file appears the first time the ext
  calls `/ext/token`. From then on, missing/wrong header returns 401.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Header, HTTPException, status

from app.config import settings


def _token_file() -> Path:
    return settings.data_path / "ext_token.txt"


def get_or_create_token() -> str:
    """Read the token from disk, creating it on first call."""
    tf = _token_file()
    if tf.exists():
        return tf.read_text(encoding="utf-8").strip()
    tf.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    tf.write_text(token, encoding="utf-8")
    try:
        tf.chmod(0o600)
    except OSError:
        # Windows / non-POSIX FS: chmod may be a no-op — that's fine.
        pass
    return token


def _current_token() -> str | None:
    """Read the token without creating it. Returns None if never created —
    that opts the caller into 'auth off' mode (backwards-compat)."""
    tf = _token_file()
    if not tf.exists():
        return None
    return tf.read_text(encoding="utf-8").strip()


def require_ext_token(
    x_extension_token: str | None = Header(default=None, alias="X-Extension-Token"),
) -> None:
    """FastAPI dependency for /ext/* endpoints.

    Fails with 401 iff a token has already been provisioned AND the header
    is missing or wrong. Comparison is constant-time to avoid timing side
    channels (low value in a localhost setup but free to add).
    """
    expected = _current_token()
    if expected is None:
        # First-boot / legacy install: don't gate. `get_or_create_token`
        # will provision on the ext's next call to /ext/token.
        return
    if not x_extension_token or not secrets.compare_digest(x_extension_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing or invalid X-Extension-Token. Reload the JobHunter "
                "extension: it fetches the token from GET /ext/token on install."
            ),
        )
