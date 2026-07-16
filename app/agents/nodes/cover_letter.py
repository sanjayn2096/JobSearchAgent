"""Node 5 (optional): draft tailored cover letters for the top matches.

Runs only when a CandidateProfile is present — writing a letter without knowing
the candidate produces generic filler, which is worse than nothing.
"""
from __future__ import annotations

import asyncio
import logging

from app.agents.state import JobSearchState
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

_SYSTEM = """You draft a short, specific cover letter opening (max 150 words).

Connect concrete candidate experience to concrete job requirements. Name the
company and the role. No flattery, no "I am writing to express my interest",
no invented experience. If the candidate genuinely lacks a stated requirement,
address it once, briefly, and move on."""


class CoverLetterNode:
    def __init__(self, llm: StructuredLLM, top_n: int = 3) -> None:
        self._llm = llm
        self._top_n = top_n

    async def __call__(self, state: JobSearchState) -> dict:
        profile = state.get("profile")
        scored = state.get("scored_jobs", [])
        if not profile or not scored:
            return {"cover_letters": {}}

        targets = scored[: self._top_n]
        drafts = await asyncio.gather(
            *(self._draft(s, profile) for s in targets), return_exceptions=True
        )

        letters: dict[str, str] = {}
        for s, draft in zip(targets, drafts):
            if isinstance(draft, Exception):
                logger.warning("Cover letter failed for %s: %s", s.job.source_id, draft)
                continue
            letters[s.job.source_id] = draft
        return {"cover_letters": letters}

    async def _draft(self, scored, profile) -> str:
        j = scored.job
        user = (
            f"CANDIDATE\n{profile.headline}\n"
            f"Experience: {profile.years_experience or 'unspecified'} years\n"
            f"Skills: {', '.join(profile.skills) or 'unspecified'}\n"
            f"About: {profile.summary}\n\n"
            f"ROLE\n{j.title} at {j.company} ({j.location.display()})\n"
            f"Required skills: {', '.join(j.skills) or 'unspecified'}\n"
            f"Description: {j.description[:1500]}\n\n"
            f"Matched: {', '.join(scored.matched_skills) or 'none identified'}\n"
            f"Gaps: {', '.join(scored.missing_skills) or 'none identified'}"
        )
        text = await self._llm.text(system=_SYSTEM, user=user, temperature=0.6)
        return text.strip()
