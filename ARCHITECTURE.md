# Architecture

Technical deep-dive into how the job application agent is built, how AI is used, how LangGraph is used, and the tradeoffs behind the key decisions.

---

## Folder structure

```
app/
├── domain/               Pure Python — no framework imports
│   ├── entities/         Job, SalaryRange, Location, SearchCriteria, CandidateProfile
│   ├── ports/            StructuredLLM, JobSource  (interfaces, not implementations)
│   └── services/
│       └── matching.py   HardFilter · JobScorer · JobRanker  ← no AI, just math
│
├── agents/
│   ├── graphs/           build_job_search_graph  (wires everything together)
│   ├── nodes/            parse_query · search_jobs · filter_and_score · summarize · cover_letter
│   └── state.py          JobSearchState — shared memory across the whole graph
│
├── application/          Use cases + API response shapes
├── infrastructure/       The real implementations: LangChain LLM, JSearch scraper, fake versions for testing
└── interfaces/api/       FastAPI routes and dependency wiring
```

The core principle: the `domain/` layer knows nothing about AI, web frameworks, or databases. It's plain Python classes and functions. This means the business logic — what makes a job a good match, how to score it — can be read, understood, and tested without running any servers or calling any APIs.

---

## How AI is used

The AI model is called in exactly **3 places**. Everything else is ordinary Python code.

### 1. Understanding the search request (`parse_query`)

The user types something like `"Staff Android Engineer, Seattle, 250k+"`. The AI converts this into a structured object with named fields: job title, city, salary minimum, seniority level, required skills.

Why AI here? Because natural language is messy. "250k+" means 250,000. "Sr." means Senior. "Remote only" means arrangement=remote. Teaching a rules engine to handle every variation of human phrasing is a losing battle — the AI handles this well.

The AI is given strict instructions: don't invent skills the user didn't mention, don't guess seniority unless it's clearly stated, normalize salary shorthand to full numbers. The output is validated against a strict schema before anything else runs, so a hallucinated field causes an error at the boundary rather than silently corrupting results downstream.

### 2. Writing the summary (`summarize`)

After jobs are scored and ranked, the AI writes 3–5 sentences explaining what was found: which role scored highest and why, any patterns across the results (e.g. "most roles are hybrid"), and a suggestion if results were thin.

The AI is told: use only the data you're given, no bullet points, no invented statistics, no generic filler. If the AI fails (network error, etc.), the node falls back to a pre-written template using the computed numbers.

### 3. Writing cover letter openers (`cover_letter`, optional)

When the user provides their profile (skills, experience, headline), the AI writes a short opening paragraph — under 150 words — for each of the top 3 matched jobs. The prompt passes in the candidate's actual skills and the job's actual requirements, including which skills matched and which were gaps.

The AI is told not to invent experience, not to flatter, and to address any gaps briefly and honestly rather than ignoring them.

### What the AI does NOT do

| Task | What handles it instead |
|------|------------------------|
| Filter out jobs below salary floor | `HardFilter` — a simple if/else check |
| Filter by work arrangement (remote, hybrid, onsite) | `HardFilter` — direct comparison |
| Filter by required skills | `HardFilter` — set intersection |
| Score how well a job fits | `JobScorer` — a weighted formula across 4 signals |
| Rank results | Sort by score, descending |
| Remove duplicate listings | Fingerprint match: same company + title + city = same job |
| Decide whether to retry | `len(scored) < 3 and attempts < 2` |
| Decide how to broaden the search | Fixed priority order: salary → skills → seniority → city |

This boundary is intentional. If the AI scored jobs, changing models could silently change which jobs appear at the top — and you'd have no way to write a unit test that caught it. With deterministic scoring, ranking bugs reproduce instantly with no network call, and you can write tests that assert exact scores.

---

## How LangGraph is used

### What LangGraph is

LangGraph is a library for building AI workflows as a **state machine** — a graph where nodes do work and edges decide what happens next. The agent's state (the current search criteria, the jobs found so far, errors, results) is passed between nodes and updated at each step.

### Why LangGraph instead of a plain loop

The core behaviour of this agent is: search → score → if not enough results, relax a constraint and search again. That's a cycle. A linear chain can't express it. A plain Python loop can, but you lose two things:

**Visibility.** LangGraph checkpoints state after every node. If something goes wrong, you can see exactly which node failed and what state it had. With a loop, you'd see one big function call in your logs. Tools like LangSmith show the full step-by-step trace, which is invaluable when debugging why the agent retried or didn't retry.

**Clarity.** The decision logic — "should we retry or summarise?" — lives as a named function (`_should_retry`) attached to a named edge in the graph. When you look at the compiled graph topology, you can see the cycle. In a loop, that same logic is buried inside a function body.

### The graph in plain English

```
Start
  │
  ▼
parse_query        AI reads the user's message and extracts structured search intent
  │
  ▼
search_jobs        Queries all configured job sources at the same time (concurrent)
  │
  ▼
filter_and_score   Removes jobs that don't meet hard requirements, scores the rest
  │
  ├── not enough results? ──► broaden ──► back to search_jobs  (max 2 retries)
  │
  ▼
summarize          AI writes a plain-language summary of what was found
  │
  ├── profile provided? ──► cover_letter  (AI drafts openers for top 3)
  │
  ▼
End
```

### LangGraph features used

| Feature | How it's used here |
|---------|-------------------|
| `StateGraph` | Defines the graph structure and what state flows between nodes |
| `TypedDict` state | `JobSearchState` — typed fields so every node knows what to expect |
| Conditional edges | Two decision points: retry-or-summarise, cover-letter-or-end |
| Graph cycle | The `broaden → search_jobs` edge is a real loop back |
| `MemorySaver` | Saves state after each node so runs can be inspected |
| `thread_id` | Each API request gets its own isolated state — concurrent users don't interfere |
| Async nodes | All nodes are async; job sources are queried in parallel using `asyncio.gather` |
| Annotated reducer | Errors from multiple nodes are collected additively rather than overwriting each other |

### Connecting to Claude via MCP

The agent also ships with `mcp_server.py` — a lightweight adapter that exposes the `search_jobs` API as an MCP tool Claude can call directly.

```
Claude ──tool call──► mcp_server.py ──HTTP──► FastAPI ──► LangGraph graph
       ◄──result─────               ◄─────────         ◄──────────────────
```

The MCP server contains no logic — it just translates Claude's tool call into an HTTP request and formats the response back into readable text. All the actual work happens in the FastAPI service.

**Why MCP and not a Claude skill file?**

Claude Code skill files are prompt instructions — they tell Claude how to behave. MCP tools are callable functions that return real data. For a use case where Claude needs actual search results back, MCP is the right integration path.

---

## Technical tradeoffs

### 1. AI scoring vs rule-based scoring

**What we considered:** Let the AI score each job — it would understand that "Kotlin developer" and "Android engineer" are related, even if the keywords don't overlap exactly.

**What we chose:** A weighted scoring formula across four signals (skill overlap, title match, salary fit, seniority fit).

**Why:** AI scoring is non-deterministic, costs a token call per job, can't be unit tested, and can silently change behaviour when you swap models. The formula is transparent, reproducible, and fast. Semantic understanding is concentrated in `parse_query` — once the user's intent is structured, scoring is a math problem.

---

### 2. Retrying with relaxed criteria — what order?

When results are too thin, the agent relaxes one constraint at a time in this order: salary → required skills → seniority → city.

**Why salary first?** A salary floor is often aspirational — someone asking for 250k would probably take 220k for the right role. A named city is usually genuinely meant — they want to work there. Relaxing location when salary is the real constraint wastes the user's time with irrelevant results.

This is a product judgment baked into the code (`_broaden_criteria`), not a config option. It's the kind of decision that should be made once and documented, not left open-ended.

---

### 3. Where raw job results are stored between retry attempts

**The problem:** LangGraph supports additive reducers on state fields — multiple nodes can write to the same list and the results get merged. We initially used this for `raw_jobs`. But this meant retry attempt 2 was scoring the combined jobs from attempt 1 AND attempt 2, not just the fresh batch. The retry cycle exists to get a *new* set of results under relaxed criteria — accumulating old ones defeats the purpose.

**What we chose:** Plain overwrite. Each retry pass replaces the previous jobs completely. The concurrent fan-out across multiple job sources (LinkedIn, Indeed, etc.) happens *inside* a single node using `asyncio.gather`, not across multiple LangGraph nodes, so there's only one writer per pass and overwrite is safe.

This was the most subtle bug in the original design. There's a regression test (`test_retry_scores_only_attempt2_jobs`) that would catch it if it came back.

---

### 4. Job sources: API vs scraping

**What we considered:** Scraping LinkedIn directly.

**What we chose:** JSearch, a RapidAPI service that aggregates LinkedIn, Indeed, Glassdoor, and ZipRecruiter via their official data agreements.

**Why:** Scraping LinkedIn violates their Terms of Service, gets IP-blocked, and breaks whenever they change their HTML. JSearch has a free tier (200 requests/month) and returns structured JSON. For any project that demos publicly, ToS compliance isn't optional.

---

### 5. Where the fake AI and fake job source live

**The problem:** The demo script (`demo.py`) needs to run with no API keys, so it needs access to `FakeLLM` and `MockJobSource`. If those lived in the `tests/` folder, `demo.py` would have to import from the test package — a backwards dependency.

**What we chose:** `FakeLLM` and `MockJobSource` live in `infrastructure/`, alongside the real implementations. The demo and the integration tests both import from the same place.

**The tradeoff:** A small philosophical blur — "fake" implementations sitting next to production code. We consider this acceptable because they're explicitly named `Fake` and `Mock`, and the alternative (importing from `tests/`) is a worse architecture violation.

---

### 6. Interfaces defined as Protocols, not abstract base classes

**What we considered:** Python's `ABC` (abstract base class) — subclass it, implement the required methods, get a clear error at class definition time if you miss one.

**What we chose:** `Protocol` — structural typing. Any class with the right method signatures qualifies, with no inheritance required.

**Why:** `FakeLLM` in tests doesn't need to inherit from a shared base. This keeps test doubles simple and avoids coupling the test infrastructure to the domain. The tradeoff is that a missing method is a runtime error rather than a definition-time error — acceptable given the test coverage.
