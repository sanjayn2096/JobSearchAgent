"""Composition root. The one place where abstractions meet implementations.

Everything above this file depends on ports. This file is the only thing that
knows JSearchSource and LangChainLLM exist. Swapping either is a one-line edit
here — that property is the entire justification for the layering.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.agents.graphs.job_search_graph import build_job_search_graph
from app.application.use_cases.search_jobs import SearchJobsUseCase
from app.domain.ports.job_source import JobSource
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.llm.langchain_llm import FakeLLM, LangChainLLM
from app.infrastructure.scrapers.mock_source import MockJobSource

logger = logging.getLogger(__name__)


def _build_llm(settings: Settings):
    if settings.use_fake_llm or not settings.openrouter_api_key:
        logger.warning("Using FakeLLM — no OPENROUTER_API_KEY configured")
        return FakeLLM()
    return LangChainLLM(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=settings.llm_timeout_seconds,
    )


def _build_sources(settings: Settings) -> list[JobSource]:
    """Sources are configured, not hardcoded. A missing key means that source
    is skipped — the app still starts and still works, just with less coverage.
    Degrading is better than refusing to boot."""
    if settings.use_mock_sources:
        return [MockJobSource()]

    sources: list[JobSource] = []

    if settings.jsearch_api_key:
        from app.infrastructure.scrapers.jsearch_source import JSearchSource

        sources.append(JSearchSource(settings.jsearch_api_key))
    else:
        logger.info("JSEARCH_API_KEY not set — skipping JSearch source")

    if not sources:
        logger.warning("No live sources configured — falling back to mock data")
        sources.append(MockJobSource())

    return sources


@lru_cache
def get_search_use_case() -> SearchJobsUseCase:
    """Cached: building the graph compiles a state machine and is not free.
    The graph is stateless across invocations — per-request state lives in the
    checkpointer, keyed by thread_id."""
    settings = get_settings()
    graph = build_job_search_graph(
        llm=_build_llm(settings), sources=_build_sources(settings)
    )
    return SearchJobsUseCase(graph)
