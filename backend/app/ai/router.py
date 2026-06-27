"""Router LLM con fallback automatico entre providers por tier."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.providers.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# Tiers soportados.
KNOWN_TIERS = {"scoring", "generation", "messaging"}

# Slot de provider a usar por (provider cloud, tier). El router escoge el modelo
# barato para scoring/messaging y el potente para generation.
_CLOUD_SLOTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "scoring": "anthropic-haiku",
        "generation": "anthropic-sonnet",
        "messaging": "anthropic-haiku",
    },
    "openai": {
        "scoring": "openai-mini",
        "generation": "openai-gpt",
        "messaging": "openai-mini",
    },
    "gemini": {
        "scoring": "gemini-flash",
        "generation": "gemini-pro",
        "messaging": "gemini-flash",
    },
}
_CLOUD_ORDER: tuple[str, ...] = ("anthropic", "openai", "gemini")


def build_tier_map(mode: str, cloud_provider: str) -> dict[str, list[str]]:
    """Construye el tier_map segun el modo efectivo del keystore.

    - off   -> sin providers (IA desactivada).
    - local -> solo Ollama.
    - cloud -> el provider cloud elegido PRIMERO, luego los otros cloud como
      fallback, y Ollama como ultimo recurso.
    """
    tiers = ("scoring", "generation", "messaging")
    if mode == "off":
        return {t: [] for t in tiers}
    if mode == "local":
        return {t: ["ollama-qwen"] for t in tiers}
    # cloud
    if cloud_provider not in _CLOUD_SLOTS:
        cloud_provider = "anthropic"
    ordered = [cloud_provider] + [p for p in _CLOUD_ORDER if p != cloud_provider]
    out: dict[str, list[str]] = {}
    for t in tiers:
        out[t] = [_CLOUD_SLOTS[p][t] for p in ordered] + ["ollama-qwen"]
    return out


class LLMRouter:
    """Selecciona provider+modelo segun tier con fallback automatico.

    `providers`: dict {provider_key -> LLMProvider}
        donde provider_key es uno de los items del tier (p.ej. "anthropic-haiku").
    `tier_map`: dict {tier -> [provider_key, ...]} en orden de prioridad.
    `model_overrides`: dict {provider_key -> model_name} para forzar modelo concreto
        por slot de provider.
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        tier_map: dict[str, list[str]],
        model_overrides: dict[str, str] | None = None,
        cost_tracker: Any | None = None,
    ) -> None:
        self.providers = providers
        self.tier_map = tier_map
        self.model_overrides = model_overrides or {}
        self.cost_tracker = cost_tracker

    def _resolve_slot(self, slot_key: str) -> tuple[LLMProvider | None, str | None]:
        """Devuelve (provider, model_override) para un slot tipo `anthropic-haiku`."""
        provider = self.providers.get(slot_key)
        model = self.model_overrides.get(slot_key)
        return provider, model

    def available_providers(self, tier: str) -> list[str]:
        slots = self.tier_map.get(tier, [])
        return [s for s in slots if (p := self.providers.get(s)) is not None and p.is_available()]

    async def complete_for(
        self,
        tier: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
        cache_system: bool = True,
    ) -> LLMResponse:
        """Itera providers del tier con fallback. Loguea cual termino usandose.

        Si todos fallan, lanza RuntimeError.
        """
        slots = self.tier_map.get(tier)
        if not slots:
            raise LLMError(f"Tier desconocido o sin providers configurados: {tier!r}")

        last_error: Exception | None = None
        for slot in slots:
            provider, model_override = self._resolve_slot(slot)
            if provider is None:
                logger.debug("LLM[%s] slot %s: provider no registrado, skip", tier, slot)
                continue
            if not provider.is_available():
                logger.info("LLM[%s] slot %s: %s no disponible, skip", tier, slot, provider.name)
                continue

            target_model = model_override or getattr(provider, "default_model", None)
            logger.info("LLM[%s] using %s/%s", tier, provider.name, target_model)
            try:
                response = await provider.complete(
                    system=system,
                    user=user,
                    model=model_override,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                    cache_system=cache_system,
                )
                if self.cost_tracker is not None:
                    try:
                        self.cost_tracker.track_call(response, tier)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("cost_tracker.track_call fallo: %s", exc)
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "LLM[%s] %s/%s fallo: %s -> probando siguiente provider",
                    tier,
                    provider.name,
                    target_model,
                    exc,
                )
                continue

        raise RuntimeError(
            f"All LLM providers exhausted for tier {tier!r}. Ultimo error: {last_error!r}"
        )


# ---- Singleton + factory desde settings ----

_router_instance: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Devuelve el router global, inicializandolo si hace falta."""
    global _router_instance
    if _router_instance is None:
        _router_instance = build_default_router()
    return _router_instance


def set_router(router: LLMRouter) -> None:
    """Asigna manualmente el router global (util para tests/lifespan)."""
    global _router_instance
    _router_instance = router


def build_default_router(cost_tracker: Any | None = None) -> LLMRouter:
    """Construye el router por defecto.

    Las CLAVES se leen del keystore (data/integrations/ai.json) con fallback a
    `settings`/.env. Los tiers se construyen segun el modo efectivo del keystore
    (`resolve_mode()`): cloud -> el provider elegido primero; local -> Ollama;
    off -> sin providers. Mantiene los mismos slot-keys que antes mas los nuevos
    `openai-mini` / `openai-gpt`.
    """
    from app.ai import keystore
    from app.ai.providers.anthropic_provider import AnthropicProvider
    from app.ai.providers.gemini_provider import GeminiProvider
    from app.ai.providers.ollama_provider import OllamaProvider
    from app.ai.providers.openai_provider import OpenAIProvider
    from app.config import settings

    anth_key = keystore.get_key("anthropic")
    openai_key = keystore.get_key("openai")
    gemini_key = keystore.get_key("gemini")

    # Un slot por (provider, modelo) usable.
    anth_haiku = AnthropicProvider(
        api_key=anth_key,
        default_model=settings.anthropic_scoring_model,
    )
    anth_sonnet = AnthropicProvider(
        api_key=anth_key,
        default_model=settings.anthropic_generation_model,
    )
    openai_mini = OpenAIProvider(
        api_key=openai_key,
        default_model=settings.openai_scoring_model,
    )
    openai_gpt = OpenAIProvider(
        api_key=openai_key,
        default_model=settings.openai_generation_model,
    )
    gem_flash = GeminiProvider(
        api_key=gemini_key,
        default_model=settings.gemini_scoring_model,
    )
    gem_pro = GeminiProvider(
        api_key=gemini_key,
        default_model=settings.gemini_generation_model,
    )
    ollama = OllamaProvider(
        base_url=settings.ollama_base_url,
        default_model=settings.ollama_model,
    )

    providers: dict[str, LLMProvider] = {
        "anthropic-haiku": anth_haiku,
        "anthropic-sonnet": anth_sonnet,
        "openai-mini": openai_mini,
        "openai-gpt": openai_gpt,
        "gemini-flash": gem_flash,
        "gemini-pro": gem_pro,
        "ollama-qwen": ollama,
        # Aliases comunes:
        "ollama-llama": OllamaProvider(
            base_url=settings.ollama_base_url, default_model="llama3.2:3b"
        ),
    }

    state = keystore.get_state()
    tier_map = build_tier_map(keystore.resolve_mode(), state.get("ai_cloud_provider", "anthropic"))

    return LLMRouter(providers=providers, tier_map=tier_map, cost_tracker=cost_tracker)


def ai_available() -> bool:
    """True si hay al menos un provider LLM disponible en algun tier."""
    try:
        r = get_router()
    except Exception:  # noqa: BLE001
        return False
    for tier in ("scoring", "generation", "messaging"):
        try:
            if r.available_providers(tier):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False
