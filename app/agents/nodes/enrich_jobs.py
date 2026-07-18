from __future__ import annotations

import asyncio
import logging

from app.agents.state import JobSearchState
from app.domain.ports.job_enricher import JobEnricher

logger = logging.getLogger(__name__)


class EnrichJobsNode:
    """Fetches full job descriptions and fills in undisclosed salaries
    for the top N jobs before downstream nodes run.

    Runs in the daily graph only — keeps the interactive API fast."""

    def __init__(self, enricher: JobEnricher, top_n: int = 10) -> None:
        self._enricher = enricher
        self._top_n = top_n

    async def __call__(self, state: JobSearchState) -> dict:
        scored = state.get("scored_jobs", [])
        if not scored:
            return {}

        targets = scored[: self._top_n]
        await asyncio.gather(
            *(self._enrich(s) for s in targets), return_exceptions=True
        )
        return {"scored_jobs": targets + scored[self._top_n :]}

    async def _enrich(self, scored) -> None:
        job = scored.job

        description = await self._enricher.fetch_details(job.source_id)
        if description:
            job.description = description
            logger.debug("Enriched description for %s @ %s", job.title, job.company)

        if not job.salary.is_disclosed:
            salary = await self._enricher.fetch_company_salary(job.title, job.company)
            if salary is None:
                location = f"{job.location.city or ''} {job.location.region or ''}".strip()
                salary = await self._enricher.fetch_salary_estimate(job.title, location)
            if salary:
                job.salary = salary
                logger.debug("Filled salary for %s @ %s: %s", job.title, job.company, salary)
