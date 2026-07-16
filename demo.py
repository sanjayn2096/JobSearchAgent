"""Zero-config demo. No API keys, no network:

    python demo.py

Runs the full graph against mock data with a fake LLM so you can watch the
control flow — including the broaden-and-retry cycle — before wiring anything up.
"""
from __future__ import annotations

import asyncio
import logging

from app.agents.graphs.job_search_graph import build_job_search_graph
from app.agents.nodes.parse_query import _ParsedQuery
from app.domain.entities.job import SeniorityLevel
from app.domain.entities.candidate import CandidateProfile
from app.infrastructure.llm.langchain_llm import FakeLLM
from app.infrastructure.scrapers.mock_source import MockJobSource

logging.basicConfig(level=logging.INFO, format="  %(levelname)-7s %(name)-40s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n  {text}\n{'=' * 78}")


async def scenario(title: str, salary_floor: int, query: str) -> None:
    banner(title)
    llm = FakeLLM(
        structured_response=_ParsedQuery(
            titles=["Android Engineer"],
            city="Seattle",
            region="WA",
            salary_floor=salary_floor,
            seniority=SeniorityLevel.SENIOR,
        ),
        text_response="(LLM summary would appear here — running with FakeLLM.)",
    )
    graph = build_job_search_graph(llm, [MockJobSource()])

    state = await graph.ainvoke(
        {
            "raw_query": query,
            "profile": CandidateProfile(
                headline="Android engineer, 7 years",
                years_experience=7,
                skills=["Kotlin", "Android", "Jetpack Compose"],
            ),
            "attempt": 0,
            "raw_jobs": [],
            "errors": [],
        },
        config={"configurable": {"thread_id": title}},
    )

    print(f"\n  Query        : {query}")
    print(f"  Attempts     : {state['attempt']}")
    print(f"  Final floor  : {state['criteria'].salary_floor:,} USD")
    print(f"  Matches      : {len(state['scored_jobs'])}\n")
    for i, s in enumerate(state["scored_jobs"], 1):
        j = s.job
        sal = (
            f"{j.salary.minimum:,}-{j.salary.maximum:,}"
            if j.salary.is_disclosed
            else "undisclosed"
        )
        print(f"  {i}. [{s.score:.2f}] {j.title} @ {j.company}")
        print(f"         {j.location.display()} | {sal} | {s.rationale}")


async def main() -> None:
    await scenario(
        "SCENARIO 1 — normal search, results found on first pass",
        150_000,
        "Android Engineer, Seattle, Salary 150kUSD+",
    )
    await scenario(
        "SCENARIO 2 — unrealistic floor, agent broadens and retries",
        400_000,
        "Android Engineer, Seattle, Salary 400kUSD+",
    )
    banner("Done. Note attempt=2 in scenario 2: the agent replanned on its own.")


if __name__ == "__main__":
    asyncio.run(main())
