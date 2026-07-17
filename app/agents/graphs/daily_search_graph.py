"""Daily search graph — extends the interactive graph with resume tweaks,
contact discovery, and outreach drafting. Always assumes a profile is present."""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.graphs.job_search_graph import (
    MAX_ATTEMPTS,
    MIN_ACCEPTABLE_RESULTS,
    _broaden_criteria,
)
from app.agents.nodes.cover_letter import CoverLetterNode
from app.agents.nodes.draft_outreach import DraftOutreachNode
from app.agents.nodes.filter_and_score import FilterAndScoreNode
from app.agents.nodes.find_contacts import FindContactsNode
from app.agents.nodes.parse_query import ParseQueryNode
from app.agents.nodes.search_jobs import SearchJobsNode
from app.agents.nodes.suggest_resume_tweaks import SuggestResumeTweaksNode
from app.agents.nodes.summarize import SummarizeNode
from app.agents.state import JobSearchState
from app.domain.ports.job_source import JobSource
from app.domain.ports.llm import StructuredLLM
from app.domain.ports.people_finder import PeopleFinder

logger = logging.getLogger(__name__)


def _should_retry(state: JobSearchState) -> Literal["broaden", "summarize"]:
    scored = state.get("scored_jobs", [])
    attempt = state.get("attempt", 0)
    if len(scored) < MIN_ACCEPTABLE_RESULTS and attempt < MAX_ATTEMPTS:
        return "broaden"
    return "summarize"


def build_daily_search_graph(
    llm: StructuredLLM,
    sources: list[JobSource],
    people_finder: PeopleFinder,
):
    graph = StateGraph(JobSearchState)

    graph.add_node("parse_query", ParseQueryNode(llm))
    graph.add_node("search_jobs", SearchJobsNode(sources))
    graph.add_node("filter_and_score", FilterAndScoreNode())
    graph.add_node("broaden", _broaden_criteria)
    graph.add_node("summarize", SummarizeNode(llm))
    graph.add_node("cover_letter", CoverLetterNode(llm))
    graph.add_node("suggest_tweaks", SuggestResumeTweaksNode(llm))
    graph.add_node("find_contacts", FindContactsNode(people_finder))
    graph.add_node("draft_outreach", DraftOutreachNode(llm))

    graph.add_edge(START, "parse_query")
    graph.add_edge("parse_query", "search_jobs")
    graph.add_edge("search_jobs", "filter_and_score")
    graph.add_conditional_edges(
        "filter_and_score",
        _should_retry,
        {"broaden": "broaden", "summarize": "summarize"},
    )
    graph.add_edge("broaden", "search_jobs")
    graph.add_edge("summarize", "cover_letter")
    graph.add_edge("cover_letter", "suggest_tweaks")
    graph.add_edge("suggest_tweaks", "find_contacts")
    graph.add_edge("find_contacts", "draft_outreach")
    graph.add_edge("draft_outreach", END)

    return graph.compile(checkpointer=MemorySaver())
