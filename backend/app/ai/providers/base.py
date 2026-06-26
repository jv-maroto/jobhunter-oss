"""Interfaz base para todos los providers LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Respuesta normalizada de cualquier provider LLM."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cost_eur: float = 0.0
    cached: bool = False
    raw: dict = Field(default_factory=dict, exclude=True)


class LLMError(RuntimeError):
    """Error generico de un provider o del router."""


class LLMProvider(ABC):
    """Interfaz abstracta que todo provider debe implementar."""

    name: str = "abstract"

    @abstractmethod
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
        """Devuelve un LLMResponse a partir de system + user prompts."""

    @abstractmethod
    def is_available(self) -> bool:
        """Indica si el provider puede usarse (credenciales, conectividad)."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name!r}>"
