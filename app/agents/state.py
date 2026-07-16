"""Graph state. This is the agent's working memory between nodes.

Two design choices worth calling out:

- ``errors`` uses an additive reducer because errors can legitimately come
  from more than one place in a single graph run (parse failures, per-source
  failures, LLM failures).
- ``raw_jobs`` does NOT use an additive reducer. Fan-out across job sources
  happens inside ``SearchJobsNode`` via ``asyncio.gather`` — not across
  concurrent LangGraph nodes — so there is exactly one writer, and each retry
  pass must OVERWRITE the previous pass's jobs. Using ``operator.add`` here
  silently accumulates jobs across retries and masks the retry cycle's own
  reason for existing.
"""
from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from app.domain.entities.candidate import CandidateProfile
from app.domain.entities.job import Job, ScoredJob
from app.domain.entities.search_criteria import SearchCriteria


class JobSearchState(TypedDict, total=False):
    # --- inputs ---
    raw_query: str
    profile: Optional[CandidateProfile]

    # --- planning ---
    criteria: Optional[SearchCriteria]
    attempt: int

    # --- fan-out results (single writer, overwritten each retry pass) ---
    raw_jobs: list[Job]
    errors: Annotated[list[str], operator.add]

    # --- post-processing ---
    filtered_jobs: list[Job]
    scored_jobs: list[ScoredJob]

    # --- outputs ---
    summary: str
    cover_letters: dict[str, str]
