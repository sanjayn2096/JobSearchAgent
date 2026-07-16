"""Port: the reasoning engine.

Kept narrow on purpose. The domain needs two things from an LLM and nothing
else. Swapping OpenAI for a local model touches only ``infrastructure/llm/``.
"""
from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):
    """Structural protocol — any object with these two coroutines qualifies.

    We use a Protocol rather than an ABC so ``FakeLLM`` in tests and adapters
    like ``LangChainLLM`` don't need to inherit from a shared base.
    """

    async def structured(
        self, *, schema: type[T], system: str, user: str, temperature: float = 0.0
    ) -> T:
        """Generation constrained to a Pydantic schema. Adapters should use
        native structured-output / tool-calling rather than parsing JSON out
        of prose."""
        ...

    async def text(
        self, *, system: str, user: str, temperature: float = 0.7
    ) -> str:
        """Free-form prose generation."""
        ...


class LLMError(RuntimeError):
    """Base for LLM transport failures."""


class LLMStructuredOutputError(LLMError):
    """Model could not produce schema-valid output."""
