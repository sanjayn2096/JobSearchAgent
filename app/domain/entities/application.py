"""Application materials the agent drafts for a given job."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from app.domain.entities.job import Job


class ApplicationStatus(str, Enum):
    DRAFTED = "drafted"           # Agent produced materials
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"         # Human said yes
    DISCARDED = "discarded"


@dataclass
class ApplicationDraft:
    """Deliberately never carries a `SUBMITTED` state.

    This agent drafts; a human submits. Auto-submitting applications is against
    LinkedIn's ToS and is a bad idea besides — a human should always be the last
    step before their name goes on something.
    """
    job: Job
    cover_letter: str
    tailored_summary: str
    talking_points: list[str] = field(default_factory=list)
    gaps_to_address: list[str] = field(default_factory=list)
    status: ApplicationStatus = ApplicationStatus.DRAFTED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: UUID = field(default_factory=uuid4)

    def approve(self) -> None:
        if self.status is ApplicationStatus.DISCARDED:
            raise ValueError("Cannot approve a discarded draft")
        self.status = ApplicationStatus.APPROVED
