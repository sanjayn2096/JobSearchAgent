"""The LangGraph state machine.

    parse_query
         |
    search_jobs  <-------------+
         |                     |
    filter_and_score           | (broaden & retry, max 2 attempts)
         |                     |
    [enough results?] --no-----+
         | yes
    summarize
         |
    [profile present?] --yes--> cover_letter
         | no                        |
        END <-----------------------+

Why a graph and not a chain: the replan edge is a genuine cycle. A user asking
for "Staff Android Engineer, Seattle, 250k+" may get two results on the first
pass; the agent should notice, relax the tightest constraint, and try again —
without re-parsing the query or asking the user. That control flow is awkward
in a linear chain and trivial as a conditional edge.
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.cover_letter import CoverLetterNode
from app.agents.nodes.filter_and_score import FilterAndScoreNode
from app.agents.nodes.parse_query import ParseQueryNode
from app.agents.nodes.search_jobs import SearchJobsNode
from app.agents.nodes.summarize import SummarizeNode
from app.agents.state import JobSearchState
from app.domain.ports.job_source import JobSource
from app.domain.ports.llm import StructuredLLM

logger = logging.getLogger(__name__)

MIN_ACCEPTABLE_RESULTS = 3
MAX_ATTEMPTS = 2


async def _broaden_criteria(state: JobSearchState) -> dict:
    """Relax the single most restrictive constraint and retry.

    Order matters: we drop salary floor before location, because a user who
    named a city usually means it, while a salary floor is often aspirational.
    """
    criteria = state["criteria"]

    if criteria.salary_floor is not None:
        relaxed = int(criteria.salary_floor * 0.85)
        logger.info("Broadening: salary floor %s -> %s", criteria.salary_floor, relaxed)
        new = criteria.refined_with(salary_floor=relaxed)
    elif criteria.required_skills:
        logger.info("Broadening: dropping required_skills")
        new = criteria.refined_with(required_skills=[])
    elif criteria.seniority is not None:
        logger.info("Broadening: dropping seniority filter")
        new = criteria.refined_with(seniority=None)
    else:
        logger.info("Broadening: widening to region")
        new = criteria.refined_with(city=None)

    # raw_jobs is a plain overwrite field (see state.py). SearchJobsNode is
    # its only writer, so the next pass through the cycle replaces the list
    # rather than appending to it — attempt N scores only attempt N's jobs.
    return {"criteria": new, "attempt": state.get("attempt", 0) + 1}


def _should_retry(state: JobSearchState) -> Literal["broaden", "summarize"]:
    scored = state.get("scored_jobs", [])
    attempt = state.get("attempt", 0)
    if len(scored) < MIN_ACCEPTABLE_RESULTS and attempt < MAX_ATTEMPTS:
        logger.info("Only %d results on attempt %d — broadening", len(scored), attempt)
        return "broaden"
    return "summarize"


def _needs_cover_letters(state: JobSearchState) -> Literal["cover_letter", "__end__"]:
    if state.get("profile") and state.get("scored_jobs"):
        return "cover_letter"
    return END


def build_job_search_graph(
    llm: StructuredLLM,
    sources: list[JobSource],
    *,
    checkpointer=None,
    enable_cover_letters: bool = True,
):
    """Composition root for the agent. Every dependency is injected — the graph
    knows about ports, never about OpenAI or a specific job board."""
    graph = StateGraph(JobSearchState)

    graph.add_node("parse_query", ParseQueryNode(llm))
    graph.add_node("search_jobs", SearchJobsNode(sources))
    graph.add_node("filter_and_score", FilterAndScoreNode())
    graph.add_node("broaden", _broaden_criteria)
    graph.add_node("summarize", SummarizeNode(llm))

    graph.add_edge(START, "parse_query")
    graph.add_edge("parse_query", "search_jobs")
    graph.add_edge("search_jobs", "filter_and_score")

    graph.add_conditional_edges(
        "filter_and_score",
        _should_retry,
        {"broaden": "broaden", "summarize": "summarize"},
    )
    graph.add_edge("broaden", "search_jobs")  # the cycle

    if enable_cover_letters:
        graph.add_node("cover_letter", CoverLetterNode(llm))
        graph.add_conditional_edges(
            "summarize", _needs_cover_letters, {"cover_letter": "cover_letter", END: END}
        )
        graph.add_edge("cover_letter", END)
    else:
        graph.add_edge("summarize", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
