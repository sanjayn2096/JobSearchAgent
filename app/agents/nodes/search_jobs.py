"""Node 2: fan out across every configured JobSource, concurrently.

One slow or broken board must never take down the search. Each source is
wrapped in its own timeout + exception boundary; failures land in state.errors
and the graph proceeds with whatever came back.
"""
from __future__ import annotations

import asyncio
import logging

from app.agents.state import JobSearchState
from app.domain.entities.job import Job
from app.domain.ports.job_source import JobSource

logger = logging.getLogger(__name__)


class SearchJobsNode:
    def __init__(self, sources: list[JobSource], per_source_timeout: float = 20.0) -> None:
        if not sources:
            raise ValueError("SearchJobsNode requires at least one JobSource")
        self._sources = sources
        self._timeout = per_source_timeout

    async def __call__(self, state: JobSearchState) -> dict:
        criteria = state.get("criteria")
        if criteria is None:
            return {"errors": ["search_jobs: no criteria — parse step failed"]}

        results = await asyncio.gather(
            *(self._safe_search(s, criteria) for s in self._sources),
            return_exceptions=False,
        )

        jobs: list[Job] = []
        errors: list[str] = []
        for source_name, source_jobs, error in results:
            if error:
                errors.append(f"{source_name}: {error}")
            else:
                logger.info("%s returned %d jobs", source_name, len(source_jobs))
                jobs.extend(source_jobs)

        if not jobs and not errors:
            errors.append("No jobs returned by any source")

        return {"raw_jobs": jobs, "errors": errors}

    async def _safe_search(self, source: JobSource, criteria):
        try:
            jobs = await asyncio.wait_for(source.search(criteria), timeout=self._timeout)
            return source.name, jobs, None
        except asyncio.TimeoutError:
            return source.name, [], f"timed out after {self._timeout}s"
        except Exception as exc:
            logger.warning("Source %s failed: %s", source.name, exc)
            return source.name, [], str(exc)
