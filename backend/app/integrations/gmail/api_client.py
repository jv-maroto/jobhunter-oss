"""Cliente Gmail via la API oficial + OAuth desktop (scope readonly/metadata).

Imports de google* perezosos: el modulo carga aunque no esten instaladas las
dependencias del extra `gmail`. Local-first: token en data/integrations/.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, parseaddr

from app.config import settings
from app.integrations.gmail import store
from app.integrations.gmail.base import EmailMessage, GmailClient

logger = logging.getLogger(__name__)

SCOPES_BY_NAME = {
    "readonly": ["https://www.googleapis.com/auth/gmail.readonly"],
    "metadata": ["https://www.googleapis.com/auth/gmail.metadata"],
}


def _scopes() -> list[str]:
    return SCOPES_BY_NAME.get(settings.gmail_scope, SCOPES_BY_NAME["readonly"])


def run_oauth_flow() -> dict:
    """Lanza el flujo OAuth desktop (abre el navegador del usuario) y guarda token.

    Requiere client_secret.json subido por el usuario. Devuelve {account}.
    Pensado para ejecutarse en la maquina local del usuario (local-first).
    """
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-not-found]

    secret = store.read_text(store.CLIENT_SECRET_FILE)
    if not secret:
        raise RuntimeError("Falta client_secret.json (subelo en Conectar Gmail)")

    flow = InstalledAppFlow.from_client_config(json.loads(secret), _scopes())
    creds = flow.run_local_server(port=0)
    store.write_secure(store.TOKEN_FILE, creds.to_json())

    account = ""
    try:
        account = GmailApiClient().account
    except Exception:  # noqa: BLE001
        pass
    return {"account": account}


class GmailApiClient(GmailClient):
    def __init__(self) -> None:
        self._service = None
        self.account = ""
        self._build()

    def _build(self) -> None:
        token = store.read_text(store.TOKEN_FILE)
        if not token:
            return
        try:
            from google.auth.transport.requests import Request  # type: ignore[import-not-found]
            from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
            from googleapiclient.discovery import build  # type: ignore[import-not-found]

            creds = Credentials.from_authorized_user_info(json.loads(token), _scopes())
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                store.write_secure(store.TOKEN_FILE, creds.to_json())
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            prof = self._service.users().getProfile(userId="me").execute()
            self.account = prof.get("emailAddress", "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gmail API no disponible: %s", exc)
            self._service = None

    def is_connected(self) -> bool:
        return self._service is not None

    def fetch_recent(self, query: str, max_results: int = 50) -> list[EmailMessage]:
        if self._service is None:
            return []
        out: list[EmailMessage] = []
        try:
            resp = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            for ref in resp.get("messages", []):
                msg = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=ref["id"], format="full")
                    .execute()
                )
                out.append(self._parse(msg))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gmail fetch fallo: %s", exc)
        return out

    @staticmethod
    def _parse(msg: dict) -> EmailMessage:
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        from_raw = headers.get("from", "")
        name, email_addr = parseaddr(from_raw)
        subject = headers.get("subject", "")

        received = None
        if headers.get("date"):
            try:
                received = parsedate_to_datetime(headers["date"])
            except Exception:  # noqa: BLE001
                received = None
        if received is None:
            ts = msg.get("internalDate")
            if ts:
                received = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)

        body = GmailApiClient._extract_body(payload)
        return EmailMessage(
            gmail_id=msg.get("id", ""),
            thread_id=msg.get("threadId"),
            from_email=email_addr,
            from_name=name or email_addr,
            subject=subject,
            snippet=(msg.get("snippet", "") or "")[:512],
            body=body[:4000],
            received_at=received,
        )

    @staticmethod
    def _extract_body(payload: dict) -> str:
        # text/plain preferente; recorre partes anidadas.
        def walk(part: dict) -> str:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")
            for sub in part.get("parts", []) or []:
                txt = walk(sub)
                if txt:
                    return txt
            return ""

        return walk(payload)
