"""Node 3: deterministic dedup -> hard filter -> score -> rank.

Zero LLM calls. This node is pure delegation to domain services, which is the
point: the expensive, non-deterministic part of the pipeline is already done.
"""
from __future__ import annotations

import logging

from app.agents.state import JobSearchState
from app.domain.services.matching import HardFilter, JobRanker, JobScorer

logger = logging.getLogger(__name__)


class FilterAndScoreNode:
    def __init__(self, scorer: JobScorer | None = None) -> None:
        self._scorer = scorer or JobScorer()

    async def __call__(self, state: JobSearchState) -> dict:
        criteria = state.get("criteria")
        raw = state.get("raw_jobs", [])
        if criteria is None or not raw:
            return {"filtered_jobs": [], "scored_jobs": []}

        deduped = JobRanker.deduplicate(raw)
        logger.info("Deduplicated %d -> %d jobs", len(raw), len(deduped))

        surviving = [j for j in deduped if HardFilter.passes(j, criteria)]
        logger.info("Hard filter kept %d/%d", len(surviving), len(deduped))

        profile = state.get("profile")
        scored = [self._scorer.score(j, criteria, profile) for j in surviving]
        ranked = JobRanker.rank(scored, criteria.max_results)

        return {"filtered_jobs": surviving, "scored_jobs": ranked}
