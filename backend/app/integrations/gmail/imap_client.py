"""Cliente Gmail via IMAP + app-password (fallback sin proyecto OAuth).

Solo stdlib (imaplib/email). Requiere verificacion en 2 pasos + contrasena de
aplicacion. Nota: las cuentas de Google Workspace no permiten app-passwords
desde mayo 2025 (usar entonces el modo API).
"""

from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from app.integrations.gmail import store
from app.integrations.gmail.base import EmailMessage, GmailClient
from app.integrations.gmail.query import ATS_DOMAINS

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"


def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value or ""


class ImapGmailClient(GmailClient):
    def __init__(self) -> None:
        self.account = ""
        self._email = ""
        self._password = ""
        raw = store.read_text(store.IMAP_FILE)
        if raw:
            import json

            data = json.loads(raw)
            self._email = data.get("email", "")
            self._password = data.get("app_password", "")
            self.account = self._email

    def is_connected(self) -> bool:
        return self.check_connection() is None

    def check_connection(self) -> str | None:
        """Try to log in and return None on success or a human message on failure.
        Distinguishes between wrong password, 2FA not enabled and app-password
        rejected — Gmail's IMAP errors are cryptic otherwise."""
        if not (self._email and self._password):
            return "Falta email o app-password."
        try:
            conn = imaplib.IMAP4_SSL(IMAP_HOST)
            conn.login(self._email, self._password)
            conn.logout()
            return None
        except imaplib.IMAP4.error as exc:
            raw = str(exc).lower()
            logger.warning("IMAP login rejected: %s", exc)
            # Gmail rejects with these signatures depending on account state.
            if "invalid credentials" in raw or "authentication failed" in raw:
                return (
                    "Google rechazó las credenciales. Causas típicas:\n"
                    "1. Estás usando la contraseña normal de Gmail. "
                    "Necesitas una App Password de 16 caracteres.\n"
                    "2. La cuenta no tiene la verificación en 2 pasos activada "
                    "(Google la exige antes de crear App Passwords).\n"
                    "3. Copiaste la App Password con espacios — pégala junta.\n"
                    "Genera una nueva en https://myaccount.google.com/apppasswords "
                    "(el nombre puede ser 'JobHunter')."
                )
            if "web login required" in raw:
                return (
                    "Google pide login por web primero. Ve a "
                    "https://accounts.google.com/DisplayUnlockCaptcha y luego "
                    "reintenta."
                )
            return f"IMAP login falló: {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("IMAP connection error: %s", exc)
            return f"No se pudo conectar a Gmail IMAP: {exc}"

    def fetch_recent(self, query: str, max_results: int = 50) -> list[EmailMessage]:
        # IMAP no usa la sintaxis de Gmail; filtramos por fecha + remitentes ATS.
        if not (self._email and self._password):
            return []
        out: list[EmailMessage] = []
        try:
            conn = imaplib.IMAP4_SSL(IMAP_HOST)
            conn.login(self._email, self._password)
            conn.select("INBOX", readonly=True)
            # Busqueda amplia reciente; el pre-filtro fino se hace en sync.py.
            typ, data = conn.search(None, "ALL")
            ids = data[0].split()[-max_results:] if data and data[0] else []
            for num in reversed(ids):
                typ, raw = conn.fetch(num, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = email.message_from_bytes(raw[0][1])
                out.append(self._parse(num.decode(), msg))
            conn.logout()
        except Exception as exc:  # noqa: BLE001
            logger.warning("IMAP fetch fallo: %s", exc)
        return out

    @staticmethod
    def _parse(uid: str, msg: email.message.Message) -> EmailMessage:
        name, addr = parseaddr(msg.get("From", ""))
        subject = _decode(msg.get("Subject", ""))
        received = None
        if msg.get("Date"):
            try:
                received = parsedate_to_datetime(msg["Date"])
            except Exception:  # noqa: BLE001
                received = None

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode("utf-8", "replace")
                        break
                    except Exception:  # noqa: BLE001
                        continue
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                body = ""

        return EmailMessage(
            gmail_id=f"imap-{uid}",
            thread_id=None,
            from_email=addr,
            from_name=_decode(name) or addr,
            subject=subject,
            snippet=body[:512],
            body=body[:4000],
            received_at=received,
        )


# Reexport por si sync quiere los dominios.
__all__ = ["ImapGmailClient", "ATS_DOMAINS"]
