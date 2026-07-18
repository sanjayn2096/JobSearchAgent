"""Composition root. The one place where abstractions meet implementations."""
from __future__ import annotations

import logging
from functools import lru_cache

from app.agents.graphs.daily_search_graph import build_daily_search_graph
from app.agents.graphs.job_search_graph import build_job_search_graph
from app.application.use_cases.daily_search import DailySearchUseCase
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


def _build_enricher(settings: Settings):
    if settings.jsearch_api_key and not settings.use_mock_sources:
        from app.infrastructure.scrapers.jsearch_source import JSearchSource
        return JSearchSource(settings.jsearch_api_key)
    return None


def _build_people_finder(settings: Settings):
    if settings.apollo_api_key:
        from app.infrastructure.people.apollo_source import ApolloSource
        return ApolloSource(settings.apollo_api_key)
    logger.info("APOLLO_API_KEY not set — contact discovery disabled")
    return _NoOpPeopleFinder()


class _NoOpPeopleFinder:
    async def find(self, company: str) -> list:
        return []


def get_llm():
    return _build_llm(get_settings())


@lru_cache
def get_search_use_case() -> SearchJobsUseCase:
    settings = get_settings()
    graph = build_job_search_graph(llm=_build_llm(settings), sources=_build_sources(settings))
    return SearchJobsUseCase(graph)


@lru_cache
def get_daily_use_case() -> DailySearchUseCase:
    settings = get_settings()
    graph = build_daily_search_graph(
        llm=_build_llm(settings),
        sources=_build_sources(settings),
        people_finder=_build_people_finder(settings),
        enricher=_build_enricher(settings),
    )
    return DailySearchUseCase(graph)
