"""The user's own profile — the other half of every match decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CandidateProfile:
    headline: str = ""
    summary: str = ""
    years_experience: Optional[int] = None
    skills: list[str] = field(default_factory=list)
    past_roles: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    salary_expectation: Optional[int] = None

    def skill_overlap(self, required: list[str]) -> tuple[list[str], list[str]]:
        """Cheap deterministic pre-filter before spending LLM tokens."""
        mine = {s.lower().strip() for s in self.skills}
        theirs = [r.lower().strip() for r in required]
        matched = [r for r in theirs if r in mine]
        missing = [r for r in theirs if r not in mine]
        return matched, missing
