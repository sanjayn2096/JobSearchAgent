# Architecture

Technical deep-dive into how the job application agent is built, how AI is used, how LangGraph is used, and the tradeoffs behind key decisions.

---

## Folder structure

```
app/
├── domain/               Pure Python — no framework imports
│   ├── entities/         Job, SalaryRange, Location, SearchCriteria,
│   │                     CandidateProfile, ResumeSuggestion, Contact, EmailDraft
│   ├── ports/            StructuredLLM, JobSource, PeopleFinder  (interfaces)
│   └── services/
│       └── matching.py   HardFilter · JobScorer · JobRanker  ← no AI, just math
│
├── agents/
│   ├── graphs/           job_search_graph  (interactive API)
│   │                     daily_search_graph  (scheduler — extends interactive)
│   ├── nodes/            parse_query · search_jobs · filter_and_score · summarize ·
│   │                     cover_letter · suggest_resume_tweaks · find_contacts ·
│   │                     draft_outreach · parse_resume
│   └── state.py          JobSearchState — shared memory across the whole graph
│
├── application/          Use cases + API response shapes
│   └── use_cases/        search_jobs  (interactive)  ·  daily_search  (scheduler)
│
├── infrastructure/       Real implementations
│   ├── llm/              LangChainLLM, FakeLLM
│   ├── scrapers/         JSearchSource, MockJobSource
│   ├── people/           ApolloSource  (recruiter/hiring manager lookup)
│   ├── resume/           PDF + DOCX text extraction
│   ├── email/            SMTP sender, HTML digest builder
│   ├── storage/          JSON run store (profile, daily runs, packages)
│   ├── scheduler/        APScheduler daily trigger
│   └── config/           Settings (pydantic-settings, reads .env)
│
└── interfaces/api/       FastAPI routes and dependency wiring
    └── routes/           jobs · resume · approve
```

The core principle: `domain/` knows nothing about AI, web frameworks, or databases. Business logic — what makes a job a good match, how to score it — can be read and tested without running any servers.

---

## Two graphs

### Interactive graph (`build_job_search_graph`)

Used by `POST /api/v1/search`. Fast path — no contact lookup or outreach drafting.

```
parse_query → search_jobs → filter_and_score
                                 |
                    not enough? → broaden → search_jobs (max 2 retries)
                                 |
                             summarize
                                 |
                    profile? → cover_letter → END
                         no → END
```

### Daily graph (`build_daily_search_graph`)

Used by the scheduler. Always assumes a profile is present. Adds three nodes after `cover_letter`.

```
... (same as interactive up to cover_letter) ...
    cover_letter
         |
    suggest_tweaks      AI diffs resume against each top job
         |
    find_contacts       Apollo.io: 1 recruiter + 1 hiring manager per company
         |
    draft_outreach      AI writes a 3-4 sentence cold email per contact
         |
        END
```

Both graphs share `JobSearchState`. The daily graph is a separate compiled graph — the interactive graph is not slowed down by contact lookup.

---

## How AI is used

AI is called in exactly **5 places**. Everything else is ordinary Python.

### 1. Understanding the search request (`parse_query`)

`"Staff Android Engineer, Seattle, 250k+"` → structured object with named fields. AI handles messy natural language; a rules engine can't. Output is validated against a strict schema before anything else runs.

### 2. Writing the summary (`summarize`)

3–5 sentences of plain prose: strongest match and why, any patterns in results, suggestion if thin. Falls back to a template if the LLM call fails.

### 3. Writing cover letter openers (`cover_letter`)

Short opening paragraph (under 150 words) for each of the top 3 jobs. Uses only actual candidate skills and actual job requirements — no invented experience.

### 4. Suggesting resume tweaks (`suggest_resume_tweaks`)

For each top job, AI returns up to 3 structured tweaks: kind (`add`, `reword`, `remove`, `surface`), section, original text, suggested replacement, and one-sentence reason. Max 3 tweaks per job keeps it actionable.

### 5. Drafting outreach emails (`draft_outreach`)

3–4 sentence cold email per contact. Sentence 1: role + strongest credential. Sentence 2: one concrete reason they're a fit. Sentence 3: low-friction ask. Prompt explicitly forbids flattery and buzzwords.

### What AI does NOT do

| Task | What handles it |
|------|-----------------|
| Filter jobs below salary floor | `HardFilter` — a simple if/else |
| Filter by work arrangement | `HardFilter` — direct comparison |
| Score how well a job fits | `JobScorer` — weighted formula, 4 signals |
| Rank results | Sort by score, descending |
| Dedup listings | Fingerprint: company + title + city |
| Decide whether to retry | `len(scored) < 3 and attempt < 2` |
| Parse resume text to profile | `parse_resume_text` — AI, but called at upload time, not in the graph |
| Find contacts | Apollo.io API — not AI |

---

## Resume parsing

Resume upload is a one-shot operation, not part of the search graph. The flow:

```
POST /api/v1/resume
    → extract_text()       pdfplumber (PDF) or python-docx (DOCX)
    → parse_resume_text()  AI extracts structured CandidateProfile
    → save_profile()       written to data/profile.json
```

The stored profile is loaded by the scheduler at run time. The interactive API still accepts inline profile fields in the request body — resume upload is additive, not required.

---

## People search (Apollo.io)

`ApolloSource.find(company)` makes two sequential API calls:
1. Search for recruiter titles (`Recruiter`, `Technical Recruiter`, `Talent Acquisition`)
2. Search for hiring manager titles (`Engineering Manager`, `VP of Engineering`, etc.)

Returns at most 1 contact per group (2 total per company). Falls back silently with an empty list if Apollo is unconfigured or the API call fails — the rest of the graph still completes.

`_NoOpPeopleFinder` in `dependencies.py` is used when `APOLLO_API_KEY` is not set, so the daily graph works without Apollo configured.

---

## State persistence

Daily runs are serialized to JSON and saved to `data/runs/{date}_{run_id}.json`. The `data/` path is configurable via `DATA_DIR` environment variable — in production (Railway), set it to the mounted volume path so runs survive redeploys.

```
data/
├── profile.json              stored candidate profile
├── runs/
│   └── 2026-07-17_{id}.json  one file per daily run
└── packages/
    └── {run_id}/
        └── {company}_{id}/
            ├── cover_letter.txt
            ├── resume_tweaks.txt
            └── outreach.txt
```

This is intentionally simple. For multi-user use, swap `run_store.py` for a database-backed implementation behind the same interface.

---

## Daily scheduler

APScheduler's `AsyncIOScheduler` runs inside the FastAPI process, started in the lifespan hook. It fires `_run_daily()` at the configured hour (default 8am).

The scheduler is disabled if `DAILY_SEARCH_QUERY` is not set — the app starts and the interactive API works normally.

---

## Email digest and approval

The digest is a single HTML email generated by `build_digest()`. For each top job it includes: fit score, resume tweak table (kind / original / suggested / reason), cover letter, and per-contact outreach drafts with drafted subject and body.

The approve link in the email points to `POST /api/v1/approve/{run_id}`. On approval:
1. Loads the run from disk
2. Writes per-job text files to `data/packages/{run_id}/`
3. Sends a follow-up email with package paths and job URLs

There is no auto-submission of job applications. That decision is intentional — see the `ApplicationDraft` entity and its `SUBMITTED` state comment.

---

## MCP integration

`mcp_server.py` is a thin stdio adapter. It exposes three tools to Claude:

```
Claude ──tool call──► mcp_server.py ──HTTP──► FastAPI ──► LangGraph graph
       ◄──result─────               ◄─────────         ◄──────────────────
```

- `upload_resume(file_path)` — reads a local file, POSTs to `/api/v1/resume`
- `search_jobs(query)` — POSTs to `/api/v1/search`, formats results as readable text
- `approve_daily_run(run_id)` — POSTs to `/api/v1/approve/{run_id}`

The MCP server contains no logic. All work happens in FastAPI.

---

## Technical tradeoffs

### 1. AI scoring vs rule-based scoring

Chose a deterministic weighted formula (4 signals: skill overlap, title match, salary fit, seniority fit). AI scoring is non-deterministic, costs a token call per job, and can't be unit tested. Semantic understanding is concentrated in `parse_query`.

### 2. Two graphs instead of one configurable graph

`build_job_search_graph` and `build_daily_search_graph` are separate compiled graphs. The alternative — a single graph with conditional edges for each new node — would run Apollo lookups on every interactive search call, making the API significantly slower. Two graphs, one fast, one thorough.

### 3. Retry order: salary → skills → seniority → city

A salary floor is often aspirational. A named city is usually genuinely meant. Relaxing location when salary is the real constraint wastes the user's time. This is a product judgment baked into `_broaden_criteria`, not a config option.

### 4. `raw_jobs` overwrites on retry

LangGraph supports additive reducers, but `raw_jobs` uses plain overwrite. Each retry pass replaces the previous batch — accumulating old results across retries would defeat the purpose of the retry cycle. There is a regression test for this (`test_retry_scores_only_attempt2_jobs`).

### 5. JSON file storage over a database

Single-user, single-process. JSON files are readable, debuggable, and need zero infrastructure. The `run_store.py` interface is narrow enough that swapping to Postgres or DynamoDB is a contained change.

### 6. Protocols, not ABCs

`StructuredLLM`, `JobSource`, and `PeopleFinder` are all `Protocol` classes. Test doubles don't need to inherit from a shared base — any class with the right method signatures qualifies. The tradeoff: a missing method is a runtime error rather than a definition-time error.
