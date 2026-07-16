"""In-memory JobSource. Lets the whole graph run with no network and no keys.

This exists so `make demo` works on a fresh clone. A reviewer should see the
agent think within 60 seconds of cloning, not hunt for API keys.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.domain.entities.job import (
    Job,
    Location,
    SalaryRange,
    SeniorityLevel,
    WorkArrangement,
)
from app.domain.entities.search_criteria import SearchCriteria

_NOW = datetime.now(timezone.utc)

_FIXTURES = [
    Job(
        source_id="mock-001",
        title="Senior Android Engineer",
        company="Rainier Mobile",
        location=Location("Seattle", "WA", "USA", WorkArrangement.HYBRID),
        url="https://example.com/jobs/mock-001",
        description="Build and ship our flagship Android app. Kotlin, Compose, "
        "coroutines. You'll own the offline sync layer end to end.",
        salary=SalaryRange(165000, 195000, "USD"),
        seniority=SeniorityLevel.SENIOR,
        posted_at=_NOW - timedelta(days=2),
        skills=["Kotlin", "Jetpack Compose", "Coroutines", "Android", "MVVM"],
    ),
    Job(
        source_id="mock-002",
        title="Android Engineer",
        company="Puget Systems",
        location=Location("Seattle", "WA", "USA", WorkArrangement.ONSITE),
        url="https://example.com/jobs/mock-002",
        description="Java and Kotlin Android development for logistics tooling.",
        salary=SalaryRange(130000, 150000, "USD"),
        seniority=SeniorityLevel.MID,
        posted_at=_NOW - timedelta(days=9),
        skills=["Java", "Kotlin", "Android", "REST"],
    ),
    Job(
        source_id="mock-003",
        title="Staff Android Engineer",
        company="Emerald Health",
        location=Location("Bellevue", "WA", "USA", WorkArrangement.REMOTE),
        url="https://example.com/jobs/mock-003",
        description="Lead Android architecture across three product teams. "
        "Compose migration, modularization, build performance.",
        salary=SalaryRange(210000, 260000, "USD"),
        seniority=SeniorityLevel.STAFF,
        posted_at=_NOW - timedelta(days=1),
        skills=["Kotlin", "Jetpack Compose", "Gradle", "Android", "Architecture"],
    ),
    Job(
        source_id="mock-004",
        title="Mobile Engineer, Android",
        company="Northgate Retail",
        location=Location("Seattle", "WA", "USA", WorkArrangement.HYBRID),
        url="https://example.com/jobs/mock-004",
        description="Android engineer for our in-store companion app.",
        salary=SalaryRange(),  # undisclosed — exercises the penalty path
        seniority=SeniorityLevel.MID,
        posted_at=_NOW - timedelta(days=5),
        skills=["Kotlin", "Android", "GraphQL"],
    ),
    Job(
        source_id="mock-005",
        title="Senior iOS Engineer",
        company="Rainier Mobile",
        location=Location("Seattle", "WA", "USA", WorkArrangement.HYBRID),
        url="https://example.com/jobs/mock-005",
        description="Swift and SwiftUI. Counterpart to our Android role.",
        salary=SalaryRange(165000, 195000, "USD"),
        seniority=SeniorityLevel.SENIOR,
        posted_at=_NOW - timedelta(days=2),
        skills=["Swift", "SwiftUI", "iOS"],  # low title affinity — should rank last
    ),
]


class MockJobSource:
    """Satisfies the JobSource protocol."""

    def __init__(self, latency: float = 0.1, fail: bool = False) -> None:
        self._latency = latency
        self._fail = fail  # lets tests exercise the failure-isolation path

    @property
    def name(self) -> str:
        return "mock"

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        await asyncio.sleep(self._latency)
        if self._fail:
            raise RuntimeError("simulated source outage")
        return list(_FIXTURES)
