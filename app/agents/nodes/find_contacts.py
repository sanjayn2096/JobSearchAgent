from __future__ import annotations

import asyncio
import logging

from app.agents.state import JobSearchState
from app.domain.ports.people_finder import PeopleFinder

logger = logging.getLogger(__name__)


class FindContactsNode:
    def __init__(self, people_finder: PeopleFinder, top_n: int = 5) -> None:
        self._finder = people_finder
        self._top_n = top_n

    async def __call__(self, state: JobSearchState) -> dict:
        scored = state.get("scored_jobs", [])
        if not scored:
            return {"contacts": {}}

        targets = scored[: self._top_n]
        results = await asyncio.gather(
            *(self._finder.find(s.job.company) for s in targets), return_exceptions=True
        )

        contacts: dict[str, list] = {}
        for s, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.warning("Contact lookup failed for %s: %s", s.job.company, result)
                contacts[s.job.source_id] = []
            else:
                contacts[s.job.source_id] = result
        return {"contacts": contacts}
