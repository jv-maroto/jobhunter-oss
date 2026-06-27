"""Factoria de cliente Gmail segun el modo guardado en el estado."""

from __future__ import annotations

from app.integrations.gmail import store
from app.integrations.gmail.base import GmailClient


def get_client() -> GmailClient | None:
    """Devuelve el cliente segun `mode` del estado, o None si no hay conexion."""
    state = store.load_state()
    mode = state.get("mode")
    if mode == "api":
        from app.integrations.gmail.api_client import GmailApiClient

        client = GmailApiClient()
        return client if client.is_connected() else None
    if mode == "imap":
        from app.integrations.gmail.imap_client import ImapGmailClient

        client = ImapGmailClient()
        # Tiene credenciales guardadas; la conexion real se valida al hacer fetch.
        return client if (client._email and client._password) else None
    return None
