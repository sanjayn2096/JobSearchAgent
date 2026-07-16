"""Node 1: natural language -> SearchCriteria.

This is the one place we let the model interpret free text. Everything
downstream operates on the validated struct, so a hallucinated field becomes a
Pydantic error at the boundary rather than a mystery two nodes later.
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.agents.state import JobSearchState
from app.domain.entities.job import SeniorityLevel, WorkArrangement
from app.domain.entities.search_criteria import SearchCriteria
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

_SYSTEM = """You extract structured job-search parameters from a user's request.

Rules:
- Convert salary shorthand to integers: "150k" -> 150000, "1.2M" -> 1200000.
- Salary phrases like "150k+", "at least 150k", "minimum 150k" all set salary_floor.
- Infer seniority ONLY when stated or strongly implied by the title
  (e.g. "Staff Engineer" -> staff). Otherwise leave null.
- Split a compound location into city/region/country. "Seattle" -> city=Seattle,
  region=WA, country=USA.
- Never invent skills the user did not mention or clearly imply from the role.
- If the request is vague, prefer fewer fields over guessed ones."""


class _ParsedQuery(BaseModel):
    """LLM-facing schema. Intentionally not the domain object: this is a
    transport shape we validate, then map into SearchCriteria."""

    keywords: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    salary_floor: Optional[int] = None
    currency: str = "USD"
    seniority: Optional[SeniorityLevel] = None
    arrangement: Optional[WorkArrangement] = None
    required_skills: list[str] = Field(default_factory=list)

    @field_validator("salary_floor")
    @classmethod
    def _sane_salary(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1000:
            # Model wrote "150" meaning 150k. Recover rather than fail.
            return v * 1000
        return v


class ParseQueryNode:
    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    async def __call__(self, state: JobSearchState) -> dict:
        query = state["raw_query"]
        try:
            parsed = await self._llm.structured(
                schema=_ParsedQuery, system=_SYSTEM, user=query, temperature=0.0
            )
        except Exception as exc:
            logger.exception("Query parsing failed")
            return {"errors": [f"parse_query: {exc}"]}

        if not (parsed.keywords or parsed.titles):
            parsed.keywords = [query.strip()[:80]]  # fall back to raw text

        criteria = SearchCriteria(
            keywords=parsed.keywords,
            titles=parsed.titles,
            city=parsed.city,
            region=parsed.region,
            country=parsed.country,
            salary_floor=parsed.salary_floor,
            currency=parsed.currency,
            seniority=parsed.seniority,
            arrangement=parsed.arrangement,
            required_skills=parsed.required_skills,
        )
        logger.info("Parsed query into %s", criteria)
        return {"criteria": criteria, "attempt": state.get("attempt", 0) + 1}
