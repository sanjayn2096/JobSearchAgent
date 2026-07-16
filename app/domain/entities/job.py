"""Core domain entities. Pure Python — no framework imports allowed here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    UNKNOWN = "unknown"


class WorkArrangement(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Location:
    """Value object. A job's location includes its work arrangement — remote
    and onsite are structurally the same field to the matcher."""
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    arrangement: WorkArrangement = WorkArrangement.UNKNOWN

    def display(self) -> str:
        parts = [p for p in (self.city, self.region, self.country) if p]
        base = ", ".join(parts) or "Unknown location"
        if self.arrangement is WorkArrangement.REMOTE:
            return f"{base} (Remote)"
        if self.arrangement is WorkArrangement.HYBRID:
            return f"{base} (Hybrid)"
        return base


@dataclass(frozen=True)
class SalaryRange:
    """Value object. Frozen because a salary range has no identity of its own."""
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    currency: str = "USD"
    period: str = "yearly"

    def __post_init__(self) -> None:
        if self.minimum is not None and self.minimum < 0:
            raise ValueError("SalaryRange minimum cannot be negative")
        if self.maximum is not None and self.maximum < 0:
            raise ValueError("SalaryRange maximum cannot be negative")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("SalaryRange minimum cannot exceed maximum")

    @property
    def is_disclosed(self) -> bool:
        return self.minimum is not None or self.maximum is not None

    def satisfies(self, floor: int) -> bool:
        """Does this range clear the requested floor?

        Undisclosed ranges do NOT satisfy a floor — filtering-in a job whose
        pay we cannot verify against the user's minimum is a false positive.
        HardFilter keeps them separately (undisclosed passes because we don't
        exclude them) and JobScorer penalizes them.
        """
        if not self.is_disclosed:
            return False
        ceiling = self.maximum if self.maximum is not None else self.minimum
        return ceiling is not None and ceiling >= floor

    def __str__(self) -> str:
        if self.minimum and self.maximum:
            return f"{self.currency} {self.minimum:,}-{self.maximum:,}/{self.period}"
        if self.minimum:
            return f"{self.currency} {self.minimum:,}+/{self.period}"
        if self.maximum:
            return f"{self.currency} up to {self.maximum:,}/{self.period}"
        return "Not disclosed"


@dataclass
class Job:
    """A job posting. Entity — identity survives field changes."""
    source_id: str
    title: str
    company: str
    location: Location
    url: str
    description: str = ""
    salary: SalaryRange = field(default_factory=SalaryRange)
    seniority: SeniorityLevel = SeniorityLevel.UNKNOWN
    posted_at: Optional[datetime] = None
    skills: list[str] = field(default_factory=list)
    source: str = "unknown"
    id: UUID = field(default_factory=uuid4)

    @property
    def fingerprint(self) -> str:
        """Dedup key. The same role gets cross-posted across boards with
        different URLs and IDs, so neither is a reliable identity check."""
        city = (self.location.city or "").lower().strip()
        return f"{self.company.lower().strip()}::{self.title.lower().strip()}::{city}"


@dataclass
class ScoredJob:
    """A Job plus the agent's assessment of it."""
    job: Job
    score: float                      # 0.0 - 1.0
    rationale: str
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score {self.score} outside [0,1]")

    @property
    def is_strong_match(self) -> bool:
        return self.score >= 0.7
