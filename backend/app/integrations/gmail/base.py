"""Contrato comun de los clientes de Gmail (API oficial o IMAP)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmailMessage:
    gmail_id: str
    thread_id: str | None
    from_email: str
    from_name: str
    subject: str
    snippet: str  # <=512 chars, lo unico que se persiste del contenido
    body: str  # truncado, SOLO en memoria para clasificar; nunca se guarda
    received_at: datetime | None


class GmailClient(ABC):
    """Cliente de lectura de correo. Implementaciones: Gmail API y IMAP."""

    account: str = ""

    @abstractmethod
    def is_connected(self) -> bool:
        """True si hay credenciales validas y se puede leer."""

    @abstractmethod
    def fetch_recent(self, query: str, max_results: int = 50) -> list[EmailMessage]:
        """Devuelve correos recientes que cumplen `query` (sintaxis estilo Gmail)."""
