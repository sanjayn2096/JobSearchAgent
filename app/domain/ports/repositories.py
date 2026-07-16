"""Ports: persistence.

Note these are *collection-like* interfaces, not DAOs. The use cases talk about
saving jobs, not about rows and transactions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import ApplicationDraft, CandidateProfile, Job


class JobRepositoryPort(ABC):
    @abstractmethod
    async def upsert_many(self, jobs: list[Job]) -> list[Job]:
        """Insert-or-update by fingerprint. Returns the persisted set."""

    @abstractmethod
    async def get(self, job_id: UUID) -> Job | None: ...

    @abstractmethod
    async def list_seen_fingerprints(self) -> set[str]:
        """Used to suppress jobs the user has already been shown."""


class ApplicationRepositoryPort(ABC):
    @abstractmethod
    async def save(self, draft: ApplicationDraft) -> ApplicationDraft: ...

    @abstractmethod
    async def get(self, draft_id: UUID) -> ApplicationDraft | None: ...

    @abstractmethod
    async def list_all(self) -> list[ApplicationDraft]: ...


class CandidateRepositoryPort(ABC):
    @abstractmethod
    async def get_active(self) -> CandidateProfile | None: ...

    @abstractmethod
    async def save(self, profile: CandidateProfile) -> CandidateProfile: ...
