from __future__ import annotations

from typing import Protocol

from app.domain.entities.outreach import Contact


class PeopleFinder(Protocol):
    async def find(self, company: str) -> list[Contact]: ...
