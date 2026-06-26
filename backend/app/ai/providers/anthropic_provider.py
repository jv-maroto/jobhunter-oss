"""Provider Anthropic (Claude) con prompt caching y tracking de coste real."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Precios USD por 1M de tokens. Fuente: anthropic.com/pricing (cached reads -90%).
# Aproximacion conservadora EUR/USD = 0.92.
USD_TO_EUR = 0.92

ANTHROPIC_PRICING_USD: dict[str, dict[str, float]] = {
    # claude-haiku-4-5
    "haiku-4-5": {"input": 1.0, "output": 5.0},
    # claude-sonnet (4.6 y 4.7)
    "sonnet-4-6": {"input": 3.0, "output": 15.0},
    "sonnet-4-7": {"input": 3.0, "output": 15.0},
    # claude-opus
    "opus-4-7": {"input": 15.0, "output": 75.0},
}

# Token threshold para activar cache_control (Anthropic exige >=1024 para sonnet/opus,
# >=2048 para haiku).
CACHE_MIN_TOKENS_HAIKU = 2048
CACHE_MIN_TOKENS_DEFAULT = 1024


def _pricing_for(model: str) -> dict[str, float]:
    """Busca tarifa por substring del nombre del modelo."""
    m = model.lower()
    for key, prices in ANTHROPIC_PRICING_USD.items():
        if key in m:
            return prices
    # Default conservador: tarifa Sonnet.
    return ANTHROPIC_PRICING_USD["sonnet-4-6"]


def _approx_tokens(text: str) -> int:
    """Estima tokens (1 token ~= 4 chars en ingles, 3.5 en castellano).

    Solo se usa para decidir si activar cache_control.
    """
    return max(1, len(text) // 4)


class AnthropicProvider(LLMProvider):
    """Provider sincrono envuelto en `asyncio.to_thread` para ofrecer interfaz async."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-6",
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self._client: Any | None = None

    def _ensure_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]

            self._client = Anthropic(api_key=self.api_key)
            return self._client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anthropic SDK no disponible: %s", exc)
            return None

    def is_available(self) -> bool:
        return bool(self.api_key) and self._ensure_client() is not None

    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
        cache_system: bool = True,
    ) -> LLMResponse:
        client = self._ensure_client()
        if client is None:
            raise LLMError("Anthropic client no inicializado (API key faltante).")

        target_model = model or self.default_model
        cache_min = (
            CACHE_MIN_TOKENS_HAIKU if "haiku" in target_model.lower() else CACHE_MIN_TOKENS_DEFAULT
        )

        # Bloque system con cache_control si supera el umbral.
        system_block: list[dict[str, Any]]
        if cache_system and system and _approx_tokens(system) >= cache_min:
            system_block = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = [{"type": "text", "text": system}] if system else []

        # Pista para JSON: si el caller lo pide, anadimos instruccion al final del user.
        user_text = user
        if json_mode and "json" not in user_text.lower()[-200:]:
            user_text = (
                user_text
                + "\n\nResponde UNICAMENTE con un JSON valido, sin markdown, sin texto extra."
            )

        def _call() -> Any:
            return client.messages.create(
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_block,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_text}],
                    }
                ],
            )

        try:
            msg = await asyncio.to_thread(_call)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Anthropic call failed: {exc}") from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()

        usage = getattr(msg, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        cache_creation = int(getattr(usage, "cache_creation_input_tokens", 0) or 0) if usage else 0
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0) if usage else 0

        prices = _pricing_for(target_model)
        # Input no cacheado se paga full. Cache write = 1.25x. Cache read = 0.10x.
        cost_usd = (
            (input_tokens / 1_000_000) * prices["input"]
            + (cache_creation / 1_000_000) * prices["input"] * 1.25
            + (cache_read / 1_000_000) * prices["input"] * 0.10
            + (output_tokens / 1_000_000) * prices["output"]
        )
        cost_eur = cost_usd * USD_TO_EUR

        return LLMResponse(
            content=text,
            model=target_model,
            provider=self.name,
            input_tokens=input_tokens + cache_creation,
            output_tokens=output_tokens,
            cached_input_tokens=cache_read,
            cost_eur=cost_eur,
            cached=cache_read > 0,
        )
