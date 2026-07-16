"""Use case: orchestrates the agent and maps domain -> DTO.

The API layer calls this. It never touches the graph directly, so the same use
case backs the REST endpoint, a CLI, or a queue worker without duplication.
"""
from __future__ import annotations

import logging
import uuid

from app.application.dto.schemas import JobSearchRequest, JobSearchResponse, ScoredJobDTO
from app.domain.entities.candidate import CandidateProfile

logger = logging.getLogger(__name__)


class SearchJobsUseCase:
    def __init__(self, graph) -> None:
        self._graph = graph

    async def execute(self, request: JobSearchRequest) -> JobSearchResponse:
        profile = None
        if request.profile:
            profile = CandidateProfile(
                headline=request.profile.headline,
                years_experience=request.profile.years_experience,
                skills=request.profile.skills,
                summary=request.profile.summary,
            )

        thread_id = str(uuid.uuid4())
        initial_state = {
            "raw_query": request.query,
            "profile": profile if request.include_cover_letters else None,
            "attempt": 0,
            "raw_jobs": [],
            "errors": [],
        }

        final = await self._graph.ainvoke(
            initial_state, config={"configurable": {"thread_id": thread_id}}
        )

        letters = final.get("cover_letters", {})
        scored = final.get("scored_jobs", [])[: request.max_results]

        return JobSearchResponse(
            query=request.query,
            summary=final.get("summary", ""),
            results=[
                ScoredJobDTO.from_domain(s, letters.get(s.job.source_id)) for s in scored
            ],
            total_found=len(final.get("filtered_jobs", [])),
            warnings=final.get("errors", []),
        )
