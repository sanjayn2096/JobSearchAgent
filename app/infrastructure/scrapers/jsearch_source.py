"""JSearch (RapidAPI) adapter — aggregates LinkedIn, Indeed, Glassdoor, ZipRecruiter.

This is the legitimate route to LinkedIn-originated listings: JSearch has the
aggregation agreements, we consume a documented API, nobody's ToS gets broken.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.domain.entities.job import (
    Job,
    Location,
    SalaryRange,
    SeniorityLevel,
    WorkArrangement,
)
from app.domain.entities.search_criteria import SearchCriteria

logger = logging.getLogger(__name__)

_BASE_URL = "https://jsearch.p.rapidapi.com/search"

_SENIORITY_PATTERNS = [
    (re.compile(r"\b(principal|distinguished|fellow)\b", re.I), SeniorityLevel.PRINCIPAL),
    (re.compile(r"\b(staff|lead)\b", re.I), SeniorityLevel.STAFF),
    (re.compile(r"\b(senior|sr\.?|snr)\b", re.I), SeniorityLevel.SENIOR),
    (re.compile(r"\b(junior|jr\.?|entry.level|associate)\b", re.I), SeniorityLevel.JUNIOR),
    (re.compile(r"\b(intern|internship)\b", re.I), SeniorityLevel.INTERN),
]

_SKILL_VOCAB = [
    "Kotlin", "Java", "Swift", "Python", "Go", "Rust", "TypeScript", "JavaScript",
    "Jetpack Compose", "Android", "iOS", "Coroutines", "RxJava", "Dagger", "Hilt",
    "MVVM", "MVI", "Gradle", "GraphQL", "REST", "gRPC", "SQL", "Firebase",
    "CI/CD", "Espresso", "JUnit", "React", "Flutter",
]


class JSearchSource:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not api_key:
            raise ValueError("JSearchSource requires an API key")
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "jsearch"

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        params = {
            "query": criteria.to_query_string(),
            "page": "1",
            "num_pages": "1",
            "date_posted": "month",
        }
        if criteria.arrangement is WorkArrangement.REMOTE:
            params["remote_jobs_only"] = "true"

        headers = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        client = self._client or httpx.AsyncClient(timeout=20.0)
        try:
            response = await client.get(_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._owns_client:
                await client.aclose()

        raw_jobs = payload.get("data") or []
        jobs = []
        for item in raw_jobs:
            try:
                jobs.append(self._to_domain(item))
            except Exception as exc:
                logger.debug("Skipping malformed job: %s", exc)
        return jobs

    def _to_domain(self, item: dict[str, Any]) -> Job:
        title = item.get("job_title") or ""
        description = item.get("job_description") or ""

        return Job(
            source_id=item.get("job_id") or f"jsearch-{hash(title)}",
            title=title,
            company=item.get("employer_name") or "Unknown",
            location=Location(
                city=item.get("job_city"),
                region=item.get("job_state"),
                country=item.get("job_country"),
                arrangement=(
                    WorkArrangement.REMOTE
                    if item.get("job_is_remote")
                    else WorkArrangement.UNKNOWN
                ),
            ),
            url=item.get("job_apply_link") or "",
            description=description,
            salary=self._parse_salary(item),
            seniority=self._infer_seniority(title),
            posted_at=self._parse_date(item.get("job_posted_at_datetime_utc")),
            skills=self._extract_skills(f"{title} {description}"),
        )

    @staticmethod
    def _parse_salary(item: dict[str, Any]) -> SalaryRange:
        lo, hi = item.get("job_min_salary"), item.get("job_max_salary")
        period = (item.get("job_salary_period") or "YEAR").lower()

        # Normalize to annual so comparisons against a floor are meaningful.
        multiplier = {"hour": 2080, "day": 260, "week": 52, "month": 12, "year": 1}.get(
            period, 1
        )
        try:
            lo = int(lo * multiplier) if lo else None
            hi = int(hi * multiplier) if hi else None
            return SalaryRange(lo, hi, item.get("job_salary_currency") or "USD")
        except (TypeError, ValueError):
            return SalaryRange()

    @staticmethod
    def _infer_seniority(title: str) -> SeniorityLevel:
        for pattern, level in _SENIORITY_PATTERNS:
            if pattern.search(title):
                return level
        return SeniorityLevel.UNKNOWN

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        """Keyword extraction, not NLP. Cheap, deterministic, good enough —
        and it costs zero tokens. The LLM's judgment is spent on ranking, not
        on spotting the word 'Kotlin'."""
        found = []
        lowered = text.lower()
        for skill in _SKILL_VOCAB:
            if re.search(rf"\b{re.escape(skill.lower())}\b", lowered):
                found.append(skill)
        return found

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
