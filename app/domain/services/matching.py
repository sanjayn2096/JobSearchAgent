"""Pure matching logic. No I/O, no LLM, no framework — fully unit-testable.

Deliberate design note: the LLM does *semantic* work (parsing prose, judging
fit); this module does *deterministic* work (filtering, weighting, ranking).
Keeping them apart means a model change can't silently alter your ranking, and
ranking bugs are reproducible without a network call.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.candidate import CandidateProfile
from app.domain.entities.job import Job, ScoredJob, SeniorityLevel, WorkArrangement
from app.domain.entities.search_criteria import SearchCriteria


@dataclass(frozen=True)
class ScoringWeights:
    """Tunable without touching logic. Sums are normalized, so these are ratios."""

    skill_overlap: float = 0.40
    title_affinity: float = 0.25
    salary_fit: float = 0.20
    seniority_fit: float = 0.15

    def total(self) -> float:
        return self.skill_overlap + self.title_affinity + self.salary_fit + self.seniority_fit


_SENIORITY_ORDER = {
    SeniorityLevel.INTERN: 0,
    SeniorityLevel.JUNIOR: 1,
    SeniorityLevel.MID: 2,
    SeniorityLevel.SENIOR: 3,
    SeniorityLevel.STAFF: 4,
    SeniorityLevel.PRINCIPAL: 5,
}


def _normalize(token: str) -> str:
    return token.lower().strip().replace("-", " ").replace(".", "")


class HardFilter:
    """Non-negotiable constraints. Applied before scoring so we never spend
    LLM tokens ranking jobs the user already ruled out."""

    @staticmethod
    def passes(job: Job, criteria: SearchCriteria) -> bool:
        if criteria.salary_floor is not None:
            # Undisclosed salary is kept: filtering it out would discard most
            # of the market. Scoring penalizes it instead.
            if job.salary.is_disclosed and not job.salary.satisfies(criteria.salary_floor):
                return False

        if criteria.arrangement is not None:
            arr = job.location.arrangement
            if arr is not WorkArrangement.UNKNOWN and arr is not criteria.arrangement:
                return False

        if criteria.required_skills:
            job_skills = {_normalize(s) for s in job.skills}
            required = {_normalize(s) for s in criteria.required_skills}
            if not required.issubset(job_skills):
                return False

        if criteria.exclude_companies:
            excluded = {c.lower().strip() for c in criteria.exclude_companies}
            if job.company.lower().strip() in excluded:
                return False

        return True


class JobScorer:
    """Assigns [0,1] fit scores. Every sub-score is independently testable."""

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self._w = weights or ScoringWeights()

    def score(
        self, job: Job, criteria: SearchCriteria, profile: CandidateProfile | None = None
    ) -> ScoredJob:
        skill_score, matched, missing = self._skill_overlap(job, criteria, profile)
        title_score = self._title_affinity(job, criteria)
        salary_score = self._salary_fit(job, criteria)
        seniority_score = self._seniority_fit(job, criteria)

        raw = (
            skill_score * self._w.skill_overlap
            + title_score * self._w.title_affinity
            + salary_score * self._w.salary_fit
            + seniority_score * self._w.seniority_fit
        )
        final = round(min(1.0, raw / self._w.total()), 4)

        return ScoredJob(
            job=job,
            score=final,
            rationale=self._explain(skill_score, title_score, salary_score, seniority_score),
            matched_skills=matched,
            missing_skills=missing,
        )

    def _skill_overlap(
        self, job: Job, criteria: SearchCriteria, profile: CandidateProfile | None
    ) -> tuple[float, list[str], list[str]]:
        wanted = {_normalize(s) for s in criteria.required_skills}
        candidate_skills = {_normalize(s) for s in profile.skills} if profile else set()
        wanted |= candidate_skills

        if not wanted:
            return 0.5, [], []  # neutral when we have nothing to compare

        job_skills = {_normalize(s) for s in job.skills}
        if not job_skills:
            return 0.5, [], []

        matched = sorted(wanted & job_skills)
        # missing_skills = job requirements the candidate hasn't demonstrated,
        # measured against the candidate's own skills when we have a profile
        # (falling back to the required-skills list when we don't). Consumed by
        # the cover-letter node as "gaps to address".
        reference = candidate_skills if candidate_skills else wanted
        missing = sorted(job_skills - reference)
        return len(matched) / len(wanted), matched, missing

    def _title_affinity(self, job: Job, criteria: SearchCriteria) -> float:
        targets = [_normalize(t) for t in (criteria.titles or criteria.keywords)]
        title = _normalize(job.title)
        if not targets:
            return 0.0
        if any(t == title for t in targets):
            return 1.0
        if any(t in title or title in t for t in targets):
            return 0.75
        target_words = {w for t in targets for w in t.split()}
        title_words = set(title.split())
        if not target_words:
            return 0.0
        return len(target_words & title_words) / len(target_words)

    def _salary_fit(self, job: Job, criteria: SearchCriteria) -> float:
        if criteria.salary_floor is None:
            return 0.5
        if not job.salary.is_disclosed:
            return 0.35  # penalized, not excluded
        ceiling = job.salary.maximum or job.salary.minimum
        if ceiling is None:
            return 0.35
        ratio = ceiling / criteria.salary_floor
        return min(1.0, ratio / 1.3)  # 130% of floor tops out the score

    def _seniority_fit(self, job: Job, criteria: SearchCriteria) -> float:
        if criteria.seniority is None or job.seniority is SeniorityLevel.UNKNOWN:
            return 0.5
        want = _SENIORITY_ORDER.get(criteria.seniority)
        have = _SENIORITY_ORDER.get(job.seniority)
        if want is None or have is None:
            return 0.5
        return max(0.0, 1.0 - abs(want - have) * 0.3)

    @staticmethod
    def _explain(skill: float, title: float, salary: float, seniority: float) -> str:
        signals = {
            "skill overlap": skill,
            "title match": title,
            "salary fit": salary,
            "seniority fit": seniority,
        }
        best = max(signals, key=signals.get)
        worst = min(signals, key=signals.get)
        return f"Strongest signal: {best} ({signals[best]:.2f}). Weakest: {worst} ({signals[worst]:.2f})."


class JobRanker:
    """Dedup + rank. Separate from scoring so ordering strategy can change
    independently of fit calculation."""

    @staticmethod
    def deduplicate(jobs: list[Job]) -> list[Job]:
        seen: dict[str, Job] = {}
        for job in jobs:
            existing = seen.get(job.fingerprint)
            if existing is None or (
                not existing.salary.is_disclosed and job.salary.is_disclosed
            ):
                seen[job.fingerprint] = job  # prefer the richer record
        return list(seen.values())

    @staticmethod
    def rank(scored: list[ScoredJob], limit: int) -> list[ScoredJob]:
        return sorted(scored, key=lambda s: s.score, reverse=True)[:limit]
