"""Provider Google Gemini (google-genai SDK nueva)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Gemini 2.5 Flash es gratis hasta cierta cuota del free tier; coste 0 por defecto.
GEMINI_PRICING_USD: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.0, "output": 0.0},
    "gemini-2.5-pro": {"input": 0.0, "output": 0.0},
}

USD_TO_EUR = 0.92


def _pricing_for(model: str) -> dict[str, float]:
    m = model.lower()
    for key, prices in GEMINI_PRICING_USD.items():
        if key in m:
            return prices
    return {"input": 0.0, "output": 0.0}


class GeminiProvider(LLMProvider):
    """Provider Gemini async via google-genai (https://github.com/googleapis/python-genai)."""

    name = "gemini"

    def __init__(self, api_key: str, default_model: str = "gemini-2.5-pro") -> None:
        self.api_key = api_key
        self.default_model = default_model
        self._client: Any | None = None
        self._sdk_kind: str = "none"

    def _ensure_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        # Preferimos el SDK nuevo (google-genai).
        try:
            from google import genai  # type: ignore[import-not-found]

            self._client = genai.Client(api_key=self.api_key)
            self._sdk_kind = "genai"
            return self._client
        except Exception as exc:  # noqa: BLE001
            logger.debug("google-genai no disponible: %s", exc)
        # Fallback al SDK legacy si esta instalado.
        try:
            import google.generativeai as legacy  # type: ignore[import-not-found]

            legacy.configure(api_key=self.api_key)
            self._client = legacy
            self._sdk_kind = "legacy"
            return self._client
        except Exception as exc:  # noqa: BLE001
            logger.debug("google-generativeai legacy no disponible: %s", exc)
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
            raise LLMError("Gemini client no inicializado (API key faltante o SDK no instalado).")

        target_model = model or self.default_model

        try:
            if self._sdk_kind == "genai":
                text, input_tokens, output_tokens = await self._complete_genai(
                    client, target_model, system, user, max_tokens, temperature, json_mode
                )
            else:
                text, input_tokens, output_tokens = await self._complete_legacy(
                    client, target_model, system, user, max_tokens, temperature, json_mode
                )
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini call failed: {exc}") from exc

        prices = _pricing_for(target_model)
        cost_usd = (input_tokens / 1_000_000) * prices["input"] + (
            output_tokens / 1_000_000
        ) * prices["output"]

        return LLMResponse(
            content=text.strip(),
            model=target_model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost_usd * USD_TO_EUR,
            cached=False,
        )

    async def _complete_genai(
        self,
        client: Any,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        from google.genai import types  # type: ignore[import-not-found]

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            config_kwargs["system_instruction"] = system
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        config = types.GenerateContentConfig(**config_kwargs)

        def _call() -> Any:
            return client.models.generate_content(
                model=model,
                contents=user,
                config=config,
            )

        resp = await asyncio.to_thread(_call)
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        return text, input_tokens, output_tokens

    async def _complete_legacy(
        self,
        client: Any,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        # google.generativeai legacy
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        def _call() -> Any:
            gm = client.GenerativeModel(model_name=model, system_instruction=system or None)
            return gm.generate_content(user, generation_config=generation_config)

        resp = await asyncio.to_thread(_call)
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        return text, input_tokens, output_tokens
