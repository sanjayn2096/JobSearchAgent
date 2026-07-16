"""Port: anything that can hand us job postings.

The domain does not know whether this is LinkedIn, Indeed, a CSV file, or a
fake. That is the entire point — see infrastructure/scrapers for the adapters.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.entities.job import Job
from app.domain.entities.search_criteria import SearchCriteria


class JobSource(Protocol):
    """Structural protocol. Any object exposing ``name`` and ``search`` qualifies."""

    @property
    def name(self) -> str:
        """Stable identifier, e.g. 'jsearch'. Used for provenance + logging."""
        ...

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        """Return postings matching criteria. Must not raise on empty results —
        return an empty list. May raise JobSourceError on transport failure."""
        ...


class JobSourceError(RuntimeError):
    """Transport-level failure. The orchestrator degrades gracefully on this
    rather than failing the whole run — one dead source shouldn't kill a search.
    """
