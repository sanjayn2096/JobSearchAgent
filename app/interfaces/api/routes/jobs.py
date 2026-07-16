from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto.schemas import JobSearchRequest, JobSearchResponse
from app.application.use_cases.search_jobs import SearchJobsUseCase
from app.interfaces.api.dependencies import get_search_use_case

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post(
    "/search",
    response_model=JobSearchResponse,
    summary="Run an agentic job search from a natural-language query",
)
async def search_jobs(
    request: JobSearchRequest,
    use_case: SearchJobsUseCase = Depends(get_search_use_case),
) -> JobSearchResponse:
    """Parses the query, fans out across job sources, filters, scores, ranks,
    and (optionally) drafts cover letters. Broadens and retries automatically
    if the first pass returns too few results."""
    try:
        return await use_case.execute(request)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        logger.exception("Job search failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Search failed. See server logs."
        ) from exc


@router.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}
