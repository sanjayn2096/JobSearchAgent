"""Node 4: turn ranked results into something a human wants to read."""
from __future__ import annotations

import logging

from app.agents.state import JobSearchState
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

_SYSTEM = """You brief a job seeker on their search results.

Write 3-5 sentences of plain prose. Lead with the strongest match and say why.
Note any real pattern in the results (salary bands, arrangement, seniority skew).
If results are thin, say so plainly and suggest one concrete way to broaden.
No bullet points. No preamble. Do not invent details not present in the data."""


class SummarizeNode:
    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    async def __call__(self, state: JobSearchState) -> dict:
        scored = state.get("scored_jobs", [])
        if not scored:
            errs = state.get("errors", [])
            detail = f" Sources reported: {'; '.join(errs)}" if errs else ""
            return {"summary": f"No matching roles found.{detail}"}

        lines = []
        for s in scored[:10]:
            j = s.job
            sal = (
                f"{j.salary.currency} {j.salary.minimum or '?'}-{j.salary.maximum or '?'}"
                if j.salary.is_disclosed
                else "undisclosed"
            )
            lines.append(
                f"- {j.title} @ {j.company} | {j.location.display()} | {sal} | fit {s.score:.2f}"
            )

        try:
            summary = await self._llm.text(
                system=_SYSTEM,
                user=f"Search: {state['raw_query']}\n\nResults:\n" + "\n".join(lines),
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("Summary generation failed: %s", exc)
            top = scored[0]
            summary = (
                f"Found {len(scored)} matching roles. Best fit: {top.job.title} "
                f"at {top.job.company} (score {top.score:.2f})."
            )
        return {"summary": summary.strip()}
