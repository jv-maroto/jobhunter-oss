"""Provider Ollama local via HTTP API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Provider Ollama. Llama a /api/generate. Coste 0 EUR."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen2.5:7b",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama no responde en %s: %s", self.base_url, exc)
            return False

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
        target_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "system": system or "",
            "prompt": user,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Ollama call failed: {exc}") from exc

        text = (data.get("response") or "").strip()
        input_tokens = int(data.get("prompt_eval_count") or 0)
        output_tokens = int(data.get("eval_count") or 0)

        return LLMResponse(
            content=text,
            model=target_model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=0.0,
            cached=False,
        )
