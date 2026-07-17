from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel, Field

from app.agents.state import JobSearchState
from app.domain.entities.resume_suggestion import ResumeSuggestion, ResumeTweak, TweakKind
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

_SYSTEM = """Suggest targeted resume tweaks to improve fit for a specific job.

Rules:
- Maximum 3 tweaks per job.
- For REWORD/REMOVE: quote exact original text. For ADD: original is empty.
- Reason must be one sentence tied to the job's requirements.
- Do not invent experience the candidate does not have."""


class _Tweak(BaseModel):
    kind: str = Field(description="add, reword, remove, or surface")
    section: str = Field(description="summary, experience, or skills")
    original: str = Field(description="Exact text to replace (empty for add)")
    suggested: str = Field(description="Exact replacement or new text")
    reason: str = Field(description="One sentence: why this improves fit")


class _TweakList(BaseModel):
    tweaks: list[_Tweak] = Field(default_factory=list)


class SuggestResumeTweaksNode:
    def __init__(self, llm: StructuredLLM, top_n: int = 5) -> None:
        self._llm = llm
        self._top_n = top_n

    async def __call__(self, state: JobSearchState) -> dict:
        profile = state.get("profile")
        scored = state.get("scored_jobs", [])
        if not profile or not scored:
            return {"resume_suggestions": []}

        targets = scored[: self._top_n]
        results = await asyncio.gather(
            *(self._suggest(s, profile) for s in targets), return_exceptions=True
        )

        suggestions = []
        for s, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.warning("Resume tweak failed for %s: %s", s.job.source_id, result)
            else:
                suggestions.append(result)
        return {"resume_suggestions": suggestions}

    async def _suggest(self, scored, profile) -> ResumeSuggestion:
        j = scored.job
        user = (
            f"RESUME\nHeadline: {profile.headline}\n"
            f"Summary: {profile.summary}\n"
            f"Skills: {', '.join(profile.skills)}\n"
            f"Past roles: {', '.join(profile.past_roles)}\n\n"
            f"TARGET JOB\n{j.title} at {j.company}\n"
            f"Required: {', '.join(j.skills)}\n"
            f"Description: {j.description[:2000]}\n"
            f"Gaps: {', '.join(scored.missing_skills) or 'none'}"
        )
        result = await self._llm.structured(
            schema=_TweakList, system=_SYSTEM, user=user, temperature=0.2
        )
        valid_kinds = {k.value for k in TweakKind}
        tweaks = [
            ResumeTweak(
                kind=TweakKind(t.kind) if t.kind in valid_kinds else TweakKind.REWORD,
                section=t.section,
                original=t.original,
                suggested=t.suggested,
                reason=t.reason,
            )
            for t in result.tweaks
        ]
        return ResumeSuggestion(
            job_id=j.source_id,
            job_title=j.title,
            company=j.company,
            tweaks=tweaks,
        )
