from __future__ import annotations

from typing import Optional, Protocol

from app.domain.entities.job import SalaryRange


class JobEnricher(Protocol):
    async def fetch_details(self, job_id: str) -> str: ...
    async def fetch_company_salary(self, title: str, company: str) -> Optional[SalaryRange]: ...
    async def fetch_salary_estimate(self, title: str, location: str) -> Optional[SalaryRange]: ...
