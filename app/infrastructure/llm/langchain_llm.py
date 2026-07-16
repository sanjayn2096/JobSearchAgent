"""LangChain-backed implementation of the StructuredLLM port.

This is the ONLY file in the codebase that imports langchain_openai. If you
switch providers, you edit here and nowhere else — that's the whole payoff of
the port/adapter split.
"""
from __future__ import annotations

import logging
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LangChainLLM:
    """Adapter. Satisfies StructuredLLM structurally — no inheritance needed."""

    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self._model_name = model
        self._client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )  # retries handled by tenacity below for uniform backoff

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def structured(
        self, *, schema: type[T], system: str, user: str, temperature: float = 0.0
    ) -> T:
        client = self._client.bind(temperature=temperature).with_structured_output(schema)
        result = await client.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return result  # already validated against `schema` by LangChain

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def text(self, *, system: str, user: str, temperature: float = 0.7) -> str:
        client = self._client.bind(temperature=temperature)
        result = await client.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return result.content


class FakeLLM:
    """Deterministic test double. Lives here (not in tests/) so integration
    tests and local demos can run with zero API keys."""

    def __init__(self, structured_response=None, text_response: str = "Fake summary.") -> None:
        self._structured = structured_response
        self._text = text_response
        self.calls: list[dict] = []

    async def structured(self, *, schema, system, user, temperature=0.0):
        self.calls.append({"type": "structured", "user": user})
        if self._structured is not None:
            return self._structured
        return schema()

    async def text(self, *, system, user, temperature=0.7) -> str:
        self.calls.append({"type": "text", "user": user})
        return self._text
