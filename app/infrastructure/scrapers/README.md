# A note on LinkedIn

The original brief called this a "LinkedIn job application agent." This folder
does not scrape LinkedIn, and that is a deliberate engineering decision rather
than an oversight.

**Why not:**

1. **It violates their User Agreement.** Section 8.2 prohibits automated
   scraping, and LinkedIn enforces it — accounts get restricted, and they have
   litigated (*hiQ Labs v. LinkedIn* went to the Ninth Circuit twice).
2. **It doesn't work reliably.** Aggressive bot detection, rotating DOM classes,
   and auth walls mean a scraper breaks weekly. A portfolio project that is
   broken when a reviewer clones it is worse than no project.
3. **Auto-*applying* is the real problem.** Submitting applications on someone's
   behalf without per-application review is how people accidentally spam
   recruiters under their own name.

**What this does instead:** the `JobSource` port is provider-agnostic, and this
folder implements it against APIs that permit programmatic access — JSearch
(aggregates LinkedIn/Indeed/Glassdoor listings via RapidAPI, legitimately),
Adzuna (free tier, official API), and Greenhouse (public boards, no key).

**Why this is a better portfolio signal:** the interesting engineering here was
never "can you parse HTML." It's the ports/adapters boundary that makes the
source swappable, the concurrent fan-out with per-source failure isolation, and
the replan cycle. All of that is *more* visible with three real sources than
with one fragile scraper. Reviewers who have shipped agents will notice you knew
where the line was.

The agent drafts cover letters and ranks roles. A human presses submit.
