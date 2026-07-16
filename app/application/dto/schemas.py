"""API-facing DTOs. Separate from domain entities on purpose.

Domain entities are free to change shape as the model of the problem improves.
DTOs are a published contract with clients. Coupling them means every internal
refactor is a breaking API change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.entities.job import ScoredJob


class CandidateProfileDTO(BaseModel):
    headline: str = ""
    years_experience: Optional[int] = Field(None, ge=0, le=60)
    skills: list[str] = Field(default_factory=list)
    summary: str = ""


class JobSearchRequest(BaseModel):
    query: str = Field(
        ..., min_length=3, max_length=500,
        json_schema_extra={"example": "Android Engineer, Seattle, Salary 150kUSD+"},
    )
    profile: Optional[CandidateProfileDTO] = None
    max_results: int = Field(25, ge=1, le=100)
    include_cover_letters: bool = False


class SalaryDTO(BaseModel):
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    currency: str = "USD"
    disclosed: bool = False


class JobDTO(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    salary: SalaryDTO
    seniority: str
    posted_at: Optional[datetime] = None
    skills: list[str] = Field(default_factory=list)


class ScoredJobDTO(BaseModel):
    job: JobDTO
    score: float
    rationale: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    cover_letter: Optional[str] = None

    @classmethod
    def from_domain(cls, s: ScoredJob, cover_letter: str | None = None) -> "ScoredJobDTO":
        j = s.job
        return cls(
            job=JobDTO(
                id=j.source_id,
                title=j.title,
                company=j.company,
                location=j.location.display(),
                url=j.url,
                salary=SalaryDTO(
                    minimum=j.salary.minimum,
                    maximum=j.salary.maximum,
                    currency=j.salary.currency,
                    disclosed=j.salary.is_disclosed,
                ),
                seniority=j.seniority.value,
                posted_at=j.posted_at,
                skills=j.skills,
            ),
            score=s.score,
            rationale=s.rationale,
            matched_skills=s.matched_skills,
            missing_skills=s.missing_skills,
            cover_letter=cover_letter,
        )


class JobSearchResponse(BaseModel):
    query: str
    summary: str
    results: list[ScoredJobDTO]
    total_found: int
    warnings: list[str] = Field(default_factory=list)
