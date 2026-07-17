from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.domain.entities.candidate import CandidateProfile
from app.domain.ports.llm import StructuredLLM

_SYSTEM = (
    "Extract structured information from a resume. Be precise — do not invent details "
    "not present in the text. For years_experience, infer from work history if not stated."
)


class _ResumeSchema(BaseModel):
    headline: str = Field(description="Current role or professional headline")
    summary: str = Field(description="2-3 sentence professional summary based on resume content")
    years_experience: Optional[int] = Field(None, description="Total years of professional experience")
    skills: list[str] = Field(default_factory=list, description="Technical and professional skills listed")
    past_roles: list[str] = Field(default_factory=list, description="Previous job titles")
    education: list[str] = Field(default_factory=list, description="Degrees and certifications")
    preferred_locations: list[str] = Field(default_factory=list, description="Locations mentioned as preferred")
    salary_expectation: Optional[int] = Field(None, description="Annual salary expectation in USD if stated")


async def parse_resume_text(text: str, llm: StructuredLLM) -> CandidateProfile:
    result = await llm.structured(
        schema=_ResumeSchema,
        system=_SYSTEM,
        user=f"RESUME:\n{text[:6000]}",
        temperature=0.0,
    )
    return CandidateProfile(
        headline=result.headline,
        summary=result.summary,
        years_experience=result.years_experience,
        skills=result.skills,
        past_roles=result.past_roles,
        education=result.education,
        preferred_locations=result.preferred_locations,
        salary_expectation=result.salary_expectation,
    )
