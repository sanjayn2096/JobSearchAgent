from __future__ import annotations

import asyncio
import logging

from app.agents.state import JobSearchState
from app.domain.entities.outreach import EmailDraft
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

_SYSTEM = """Write a short cold outreach email for a job seeker. 3-4 sentences max.

Sentence 1: reference the specific role + candidate's strongest relevant credential.
Sentence 2: one concrete reason they're a fit (specific skill or achievement).
Sentence 3: a low-friction ask (15-min call or to forward the resume).

No flattery. No "I hope this email finds you well". No buzzwords."""


class DraftOutreachNode:
    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    async def __call__(self, state: JobSearchState) -> dict:
        profile = state.get("profile")
        scored = state.get("scored_jobs", [])
        contacts_map = state.get("contacts", {})
        if not profile or not scored or not contacts_map:
            return {"outreach_drafts": {}}

        tasks, keys = [], []
        for s in scored:
            for contact in contacts_map.get(s.job.source_id, []):
                tasks.append(self._draft(s, profile, contact))
                keys.append((s.job.source_id, contact.name))

        if not tasks:
            return {"outreach_drafts": {}}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        drafts: dict[str, list[EmailDraft]] = {}
        for (job_id, _), result in zip(keys, results):
            if isinstance(result, Exception):
                logger.warning("Outreach draft failed: %s", result)
            else:
                drafts.setdefault(job_id, []).append(result)
        return {"outreach_drafts": drafts}

    async def _draft(self, scored, profile, contact) -> EmailDraft:
        j = scored.job
        user = (
            f"CANDIDATE\n{profile.headline} | {profile.years_experience or '?'} years\n"
            f"Top skills: {', '.join(profile.skills[:8])}\n"
            f"Summary: {profile.summary}\n\n"
            f"RECIPIENT\n{contact.name}, {contact.title} at {j.company}\n\n"
            f"ROLE\n{j.title} at {j.company}\n"
            f"Matched skills: {', '.join(scored.matched_skills) or 'none'}"
        )
        body = await self._llm.text(system=_SYSTEM, user=user, temperature=0.5)
        return EmailDraft(
            contact=contact,
            job_id=j.source_id,
            subject=f"Re: {j.title} at {j.company}",
            body=body.strip(),
        )
