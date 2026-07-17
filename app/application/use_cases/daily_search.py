from __future__ import annotations

import dataclasses
import uuid

from app.domain.entities.candidate import CandidateProfile


class DailySearchUseCase:
    def __init__(self, graph) -> None:
        self._graph = graph

    async def execute(self, query: str, profile: CandidateProfile) -> dict:
        thread_id = str(uuid.uuid4())
        initial_state = {
            "raw_query": query,
            "profile": profile,
            "attempt": 0,
            "raw_jobs": [],
            "errors": [],
        }
        final = await self._graph.ainvoke(
            initial_state, config={"configurable": {"thread_id": thread_id}}
        )
        return _serialize(final, query)


def _serialize(state: dict, query: str) -> dict:
    scored = state.get("scored_jobs", [])[:10]
    cover_letters = state.get("cover_letters", {})
    suggestions_by_job = {s.job_id: s for s in state.get("resume_suggestions", [])}
    contacts_map = state.get("contacts", {})
    outreach_map = state.get("outreach_drafts", {})

    jobs = []
    for s in scored:
        j = s.job
        suggestion = suggestions_by_job.get(j.source_id)
        job_contacts = contacts_map.get(j.source_id, [])
        job_drafts = {d.contact.name: d for d in outreach_map.get(j.source_id, [])}

        contacts_out = []
        for contact in job_contacts:
            draft = job_drafts.get(contact.name)
            contacts_out.append({
                "name": contact.name,
                "title": contact.title,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
                "outreach_subject": draft.subject if draft else "",
                "outreach_body": draft.body if draft else "",
            })

        jobs.append({
            "id": j.source_id,
            "title": j.title,
            "company": j.company,
            "location": j.location.display(),
            "url": j.url,
            "score": s.score,
            "cover_letter": cover_letters.get(j.source_id, ""),
            "resume_tweaks": [dataclasses.asdict(t) for t in (suggestion.tweaks if suggestion else [])],
            "contacts": contacts_out,
        })

    return {
        "query": query,
        "summary": state.get("summary", ""),
        "jobs": jobs,
        "warnings": state.get("errors", []),
    }
