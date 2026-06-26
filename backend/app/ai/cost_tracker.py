"""Tracker de coste de llamadas LLM. Persistencia en SQLite via SQLAlchemy."""

from __future__ import annotations

import logging
from datetime import datetime

from app.ai.providers.base import LLMResponse
from app.db import SessionLocal
from app.models.api_call import ApiCall

logger = logging.getLogger(__name__)


class CostTracker:
    """Persiste cada LLMResponse en `api_calls`. Robusto a fallos de DB."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def track_call(self, response: LLMResponse, tier: str) -> None:
        if not self.enabled:
            return
        try:
            db = SessionLocal()
            try:
                row = ApiCall(
                    created_at=datetime.utcnow(),
                    provider=response.provider,
                    model=response.model,
                    tier=tier,
                    input_tokens=int(response.input_tokens or 0),
                    output_tokens=int(response.output_tokens or 0),
                    cached_input_tokens=int(response.cached_input_tokens or 0),
                    cost_eur=float(response.cost_eur or 0.0),
                    cached=bool(response.cached),
                )
                db.add(row)
                db.commit()
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("CostTracker.track_call fallo: %s", exc)


_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
