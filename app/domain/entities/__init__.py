from app.domain.entities.application import ApplicationDraft, ApplicationStatus
from app.domain.entities.candidate import CandidateProfile
from app.domain.entities.job import (
    Job,
    Location,
    SalaryRange,
    ScoredJob,
    SeniorityLevel,
    WorkArrangement,
)
from app.domain.entities.search_criteria import SearchCriteria

__all__ = [
    "ApplicationDraft",
    "ApplicationStatus",
    "CandidateProfile",
    "Job",
    "Location",
    "SalaryRange",
    "ScoredJob",
    "SearchCriteria",
    "SeniorityLevel",
    "WorkArrangement",
]
