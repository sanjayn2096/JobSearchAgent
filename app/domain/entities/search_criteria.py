"""The structured form of a user's natural-language job request."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

from app.domain.entities.job import SeniorityLevel, WorkArrangement


@dataclass(frozen=True)
class SearchCriteria:
    """Parsed intent. This is what the LLM turns "Android Engineer, Seattle,
    150k+" into, and it is the only thing the rest of the system sees.

    Frozen so a criteria object can be safely shared with concurrent scrapers.
    New passes of the retry cycle produce new instances via ``refined_with``.
    """
    keywords: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    salary_floor: Optional[int] = None
    currency: str = "USD"
    seniority: Optional[SeniorityLevel] = None
    arrangement: Optional[WorkArrangement] = None
    required_skills: list[str] = field(default_factory=list)
    exclude_companies: tuple[str, ...] = field(default_factory=tuple)
    posted_within_days: Optional[int] = 30
    max_results: int = 25

    def to_query_string(self) -> str:
        """Flatten back to the keyword string a job board expects."""
        terms = self.titles or self.keywords
        seniority_word = (
            self.seniority.value
            if self.seniority and self.seniority is not SeniorityLevel.UNKNOWN
            else None
        )
        parts: list[str] = []
        if seniority_word:
            # Only prepend if not already present in any title/keyword
            already_present = any(seniority_word.lower() in t.lower() for t in terms)
            if not already_present:
                parts.append(seniority_word)
        parts.extend(terms)
        return " ".join(parts).strip()

    def refined_with(self, **changes: Any) -> "SearchCriteria":
        """Return a copy with the given fields overridden.

        Used by the broaden-and-retry cycle: the graph loosens one constraint
        at a time and this returns a fresh criteria object rather than mutating
        state that other tasks may still hold.
        """
        return replace(self, **changes)
