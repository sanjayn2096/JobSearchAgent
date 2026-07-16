"""Domain tests. No mocks, no network, no LLM — this is the payoff of keeping
the scoring logic pure. These run in milliseconds."""
from __future__ import annotations

import pytest

from app.domain.entities.job import (
    Job, Location, SalaryRange, ScoredJob, SeniorityLevel, WorkArrangement,
)
from app.domain.entities.search_criteria import SearchCriteria
from app.domain.services.matching import HardFilter, JobRanker, JobScorer


def make_job(**overrides) -> Job:
    defaults = dict(
        source_id="j1",
        title="Senior Android Engineer",
        company="Acme",
        location=Location("Seattle", "WA", "USA", WorkArrangement.HYBRID),
        url="https://example.com/j1",
        salary=SalaryRange(160000, 190000),
        seniority=SeniorityLevel.SENIOR,
        skills=["Kotlin", "Android", "Jetpack Compose"],
    )
    return Job(**{**defaults, **overrides})


class TestSalaryRange:
    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError, match="cannot exceed maximum"):
            SalaryRange(200000, 100000)

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="negative"):
            SalaryRange(-5, 100)

    def test_undisclosed_never_satisfies_a_floor(self):
        assert SalaryRange().satisfies(150000) is False

    def test_satisfies_uses_ceiling(self):
        # 140-160k should pass a 150k floor: the top of band clears it.
        assert SalaryRange(140000, 160000).satisfies(150000) is True

    def test_below_floor_fails(self):
        assert SalaryRange(90000, 120000).satisfies(150000) is False


class TestHardFilter:
    def test_keeps_undisclosed_salary(self):
        """Filtering out undisclosed salaries would discard most of the market."""
        job = make_job(salary=SalaryRange())
        criteria = SearchCriteria(titles=["Android Engineer"], salary_floor=150000)
        assert HardFilter.passes(job, criteria) is True

    def test_excludes_disclosed_below_floor(self):
        job = make_job(salary=SalaryRange(90000, 110000))
        criteria = SearchCriteria(titles=["Android Engineer"], salary_floor=150000)
        assert HardFilter.passes(job, criteria) is False

    def test_requires_all_required_skills(self):
        job = make_job(skills=["Kotlin"])
        criteria = SearchCriteria(
            titles=["Android Engineer"], required_skills=["Kotlin", "GraphQL"]
        )
        assert HardFilter.passes(job, criteria) is False


class TestJobScorer:
    def test_score_is_bounded(self):
        scorer = JobScorer()
        criteria = SearchCriteria(titles=["Senior Android Engineer"], salary_floor=150000)
        result = scorer.score(make_job(), criteria)
        assert 0.0 <= result.score <= 1.0

    def test_exact_title_beats_unrelated_title(self):
        scorer = JobScorer()
        criteria = SearchCriteria(titles=["Senior Android Engineer"])
        android = scorer.score(make_job(), criteria)
        ios = scorer.score(
            make_job(source_id="j2", title="Senior iOS Engineer", skills=["Swift"]),
            criteria,
        )
        assert android.score > ios.score

    def test_undisclosed_salary_is_penalized_not_zeroed(self):
        scorer = JobScorer()
        criteria = SearchCriteria(titles=["Senior Android Engineer"], salary_floor=150000)
        disclosed = scorer.score(make_job(), criteria)
        undisclosed = scorer.score(
            make_job(source_id="j2", salary=SalaryRange()), criteria
        )
        assert undisclosed.score < disclosed.score
        assert undisclosed.score > 0.0


class TestJobRanker:
    def test_dedup_collapses_same_role_same_company(self):
        a = make_job(source_id="a")
        b = make_job(source_id="b")  # same company + title, different board
        assert len(JobRanker.deduplicate([a, b])) == 1

    def test_dedup_prefers_record_with_salary(self):
        without = make_job(source_id="a", salary=SalaryRange())
        with_sal = make_job(source_id="b", salary=SalaryRange(160000, 190000))
        [survivor] = JobRanker.deduplicate([without, with_sal])
        assert survivor.salary.is_disclosed

    def test_rank_orders_desc_and_truncates(self):
        jobs = [
            ScoredJob(job=make_job(source_id=f"j{i}"), score=i / 10, rationale="")
            for i in range(10)
        ]
        top = JobRanker.rank(jobs, limit=3)
        assert len(top) == 3
        assert [t.score for t in top] == [0.9, 0.8, 0.7]


class TestScoredJob:
    def test_rejects_out_of_range_score(self):
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            ScoredJob(job=make_job(), score=1.5, rationale="")
