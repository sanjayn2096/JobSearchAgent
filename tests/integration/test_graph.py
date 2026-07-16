"""Graph tests using FakeLLM + MockJobSource. No API keys, no network.

Verifies the wiring and the control flow — that the cycle terminates, that a
dead source doesn't kill the run, that state flows between nodes.
"""
from __future__ import annotations

import pytest

from app.agents.graphs.job_search_graph import build_job_search_graph
from app.agents.nodes.parse_query import _ParsedQuery
from app.domain.entities.job import SeniorityLevel
from app.infrastructure.llm.langchain_llm import FakeLLM
from app.infrastructure.scrapers.mock_source import MockJobSource


def make_llm(**overrides) -> FakeLLM:
    fields = {
        "titles": ["Android Engineer"],
        "city": "Seattle",
        "region": "WA",
        "salary_floor": 150000,
        "seniority": SeniorityLevel.SENIOR,
    }
    fields.update(overrides)
    parsed = _ParsedQuery(**fields)
    return FakeLLM(structured_response=parsed, text_response="Three strong matches.")


async def run(graph, query="Android Engineer, Seattle, 150k+", profile=None):
    return await graph.ainvoke(
        {"raw_query": query, "profile": profile, "attempt": 0, "raw_jobs": [], "errors": []},
        config={"configurable": {"thread_id": "test"}},
    )


@pytest.mark.asyncio
async def test_happy_path_returns_ranked_results():
    graph = build_job_search_graph(make_llm(), [MockJobSource()])
    state = await run(graph)

    assert state["criteria"].city == "Seattle"
    assert state["scored_jobs"]
    scores = [s.score for s in state["scored_jobs"]]
    assert scores == sorted(scores, reverse=True), "results must be ranked"
    assert state["summary"]


@pytest.mark.asyncio
async def test_dead_source_does_not_kill_the_run():
    """The whole point of per-source isolation."""
    graph = build_job_search_graph(
        make_llm(), [MockJobSource(fail=True), MockJobSource()]
    )
    state = await run(graph)

    assert state["scored_jobs"], "healthy source should still produce results"
    assert any("outage" in e for e in state["errors"]), "failure should be reported"


@pytest.mark.asyncio
async def test_all_sources_dead_degrades_gracefully():
    graph = build_job_search_graph(make_llm(), [MockJobSource(fail=True)])
    state = await run(graph)

    assert state["scored_jobs"] == []
    assert state["summary"]  # still explains itself rather than crashing


@pytest.mark.asyncio
async def test_impossible_salary_triggers_broaden_cycle():
    """Nothing in the fixtures pays 400k. The agent should relax and retry
    rather than returning nothing — and must terminate."""
    graph = build_job_search_graph(make_llm(salary_floor=400000), [MockJobSource()])
    state = await run(graph, "Android Engineer, Seattle, 400k+")

    assert state["attempt"] > 1, "should have retried at least once"
    assert state["attempt"] <= 3, "cycle must be bounded — no infinite replan"
    assert state["criteria"].salary_floor < 400000, "floor should have been relaxed"


@pytest.mark.asyncio
async def test_dedup_across_sources():
    """Two sources returning identical fixtures must not double-count."""
    graph = build_job_search_graph(make_llm(), [MockJobSource(), MockJobSource()])
    state = await run(graph)

    ids = [s.job.source_id for s in state["scored_jobs"]]
    assert len(ids) == len(set(ids)), "duplicates leaked into results"


@pytest.mark.asyncio
async def test_no_profile_skips_cover_letters():
    graph = build_job_search_graph(make_llm(), [MockJobSource()])
    state = await run(graph, profile=None)
    assert state.get("cover_letters", {}) == {}


@pytest.mark.asyncio
async def test_profile_triggers_cover_letters():
    from app.domain.entities.candidate import CandidateProfile

    graph = build_job_search_graph(make_llm(), [MockJobSource()])
    state = await run(
        graph,
        profile=CandidateProfile(
            headline="Android engineer, 7 years", skills=["Kotlin", "Android"]
        ),
    )
    assert state["cover_letters"], "profile present — letters should be drafted"


@pytest.mark.asyncio
async def test_retry_scores_only_attempt2_jobs():
    """Regression: raw_jobs must be overwritten on retry, not accumulated.

    We wire a source that returns one batch of jobs with source_id 'a-*' on the
    first call and a different batch 'b-*' on the second. If the reducer were
    additive, scored_jobs would contain ids from both passes. After the fix,
    only the second-pass ids survive.
    """
    from app.domain.entities.job import Job, Location, SalaryRange, SeniorityLevel, WorkArrangement
    from app.domain.entities.search_criteria import SearchCriteria

    call_count = 0

    class TwoPassSource:
        @property
        def name(self) -> str:
            return "two-pass"

        async def search(self, criteria: SearchCriteria) -> list[Job]:
            nonlocal call_count
            call_count += 1
            prefix = "a" if call_count == 1 else "b"
            return [
                Job(
                    source_id=f"{prefix}-{i}",
                    title="Android Engineer",
                    company=f"Corp{i}",
                    location=Location("Seattle", "WA", "USA", WorkArrangement.HYBRID),
                    url=f"https://example.com/{prefix}-{i}",
                    salary=SalaryRange(260000, 300000) if call_count == 2 else SalaryRange(50000, 80000),
                    seniority=SeniorityLevel.SENIOR,
                    skills=["Kotlin", "Android"],
                )
                for i in range(4)
            ]

    # Salary floor that first pass fails (50-80k < 150k) but second passes (260-300k).
    llm = make_llm(salary_floor=150000)
    graph = build_job_search_graph(llm, [TwoPassSource()])
    state = await run(graph)

    assert state["attempt"] > 1, "should have retried"
    scored_ids = {s.job.source_id for s in state["scored_jobs"]}
    # No 'a-*' ids should survive — they belong to the failed first attempt.
    assert not any(sid.startswith("a-") for sid in scored_ids), (
        f"attempt-1 jobs leaked into results: {scored_ids}"
    )
