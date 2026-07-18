from __future__ import annotations

import dataclasses
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.agents.nodes.suggest_resume_tweaks import SuggestResumeTweaksNode
from app.domain.entities.candidate import CandidateProfile
from app.domain.entities.job import Job, Location, SalaryRange, SeniorityLevel, WorkArrangement
from app.domain.entities.job import ScoredJob
from app.infrastructure.storage.run_store import load_profile
from app.interfaces.api.dependencies import get_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analyze"])


class _JobIn(BaseModel):
    id: str
    title: str
    company: str
    location: str = ""
    skills: list[str] = []
    missing_skills: list[str] = []
    score: float = 0.0


class AnalyzeRequest(BaseModel):
    jobs: list[_JobIn]


@router.post("/analyze")
async def analyze_resume(request: AnalyzeRequest) -> dict:
    profile_dict = load_profile()
    if not profile_dict:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No resume uploaded yet")

    profile = CandidateProfile(**profile_dict)

    scored_jobs = [
        ScoredJob(
            job=Job(
                source_id=j.id,
                title=j.title,
                company=j.company,
                location=Location(arrangement=WorkArrangement.UNKNOWN),
                url="",
                description="",
                salary=SalaryRange(),
                seniority=SeniorityLevel.UNKNOWN,
                skills=j.skills,
            ),
            score=j.score,
            rationale="",
            matched_skills=[s for s in j.skills if s in profile.skills],
            missing_skills=j.missing_skills,
        )
        for j in request.jobs
    ]

    node = SuggestResumeTweaksNode(llm=get_llm(), top_n=len(scored_jobs))
    result = await node({"profile": profile, "scored_jobs": scored_jobs})

    return {
        s.job_id: [dataclasses.asdict(t) for t in s.tweaks]
        for s in result.get("resume_suggestions", [])
    }
