"""Provider OpenAI (Chat Completions). Import perezoso del SDK 'openai'."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

USD_TO_EUR = 0.92

# Precios USD por 1M de tokens (aprox, openai.com/pricing). Cached input ~50%.
OPENAI_PRICING_USD: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "o4-mini": {"input": 1.1, "output": 4.4},
    "o3-mini": {"input": 1.1, "output": 4.4},
}


def _pricing_for(model: str) -> dict[str, float]:
    m = model.lower()
    # Match mas largo primero para no confundir "gpt-4o" con "gpt-4o-mini".
    for key in sorted(OPENAI_PRICING_USD, key=len, reverse=True):
        if key in m:
            return OPENAI_PRICING_USD[key]
    return {"input": 0.0, "output": 0.0}


class OpenAIProvider(LLMProvider):
    """Provider OpenAI sincrono envuelto en `asyncio.to_thread`."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url
        self._client: Any | None = None

    def _ensure_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore[import-not-found]

            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
            return self._client
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI SDK no disponible: %s", exc)
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
            raise LLMError("OpenAI client no inicializado (API key faltante o SDK no instalado).")

        target_model = model or self.default_model

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        user_text = user
        if json_mode and "json" not in user_text.lower()[-200:]:
            user_text = user_text + "\n\nResponde UNICAMENTE con un JSON valido, sin markdown."
        messages.append({"role": "user", "content": user_text})

        base_kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            base_kwargs["response_format"] = {"type": "json_object"}

        def _call(use_completion_tokens: bool, drop_temp: bool) -> Any:
            kwargs = dict(base_kwargs)
            if use_completion_tokens:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = max_tokens
            if drop_temp:
                kwargs.pop("temperature", None)
            return client.chat.completions.create(**kwargs)

        try:
            resp = await asyncio.to_thread(_call, False, False)
        except Exception as exc:  # noqa: BLE001
            # Modelos de razonamiento (o-series / gpt-5) usan max_completion_tokens
            # y/o no aceptan temperature. Reintenta adaptando los kwargs.
            msg = str(exc).lower()
            needs_ct = "max_tokens" in msg or "max_completion_tokens" in msg
            drops_temp = "temperature" in msg
            if needs_ct or drops_temp:
                try:
                    resp = await asyncio.to_thread(_call, needs_ct, drops_temp)
                except Exception as exc2:  # noqa: BLE001
                    raise LLMError(f"OpenAI call failed: {exc2}") from exc2
            else:
                raise LLMError(f"OpenAI call failed: {exc}") from exc

        try:
            text = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI respuesta sin contenido: {exc}") from exc

        usage = getattr(resp, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        cached_input = 0
        details = getattr(usage, "prompt_tokens_details", None) if usage else None
        if details is not None:
            cached_input = int(getattr(details, "cached_tokens", 0) or 0)

        prices = _pricing_for(target_model)
        non_cached = max(0, input_tokens - cached_input)
        cost_usd = (
            (non_cached / 1_000_000) * prices["input"]
            + (cached_input / 1_000_000) * prices["input"] * 0.5
            + (output_tokens / 1_000_000) * prices["output"]
        )

        return LLMResponse(
            content=text,
            model=target_model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input,
            cost_eur=cost_usd * USD_TO_EUR,
            cached=cached_input > 0,
        )
