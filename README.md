# Job Application Agent

An agentic job search built with **LangGraph** + **FastAPI** on a clean hexagonal architecture core.

Parses a natural-language query, fans out across job boards concurrently, scores candidates
deterministically, and **replans automatically** when results are thin — all without re-asking
the user.

---

## What it does

```
"Staff Android Engineer, Seattle, 250k+"
        │
        ▼
  parse_query          LLM extracts structured SearchCriteria
        │
        ▼
  search_jobs ◄────────────────────────────────────────┐
        │   (concurrent fan-out, per-source timeout)   │
        ▼                                              │
  filter_and_score     hard filter → score → rank      │
        │                                              │
   [enough?] ──── no ──► broaden ──────────────────────┘
        │                (relax salary, then location)
        ▼ yes
    summarize           LLM writes a prose brief
        │
   [profile?] ──── yes ──► cover_letter   (top 3 matches)
        │
       END
```

The **retry cycle** is the key LangGraph feature: if the first pass returns fewer than 3 results,
the agent relaxes the tightest constraint and searches again — bounded at 2 attempts. This is
the control flow that justifies using a graph over a plain chain.

---

## Architecture

```
app/
├── domain/               Pure Python — no framework imports
│   ├── entities/         Job, SalaryRange, Location, SearchCriteria, CandidateProfile
│   ├── ports/            StructuredLLM, JobSource (Protocols, not ABCs)
│   └── services/
│       └── matching.py   HardFilter · JobScorer · JobRanker  ← deterministic, zero LLM
│
├── agents/
│   ├── graphs/           build_job_search_graph  (composition root)
│   ├── nodes/            parse_query · search_jobs · filter_and_score · summarize · cover_letter
│   └── state.py          JobSearchState TypedDict
│
├── application/          Use cases + DTOs (API contract, separate from domain)
├── infrastructure/       LangChainLLM · JSearchSource · MockJobSource · Settings
└── interfaces/api/       FastAPI router + dependency wiring
```

### Key design decisions

**LLM / deterministic split** — The LLM does two things: parse prose into a struct, and write
human-readable text. Everything else (filtering, scoring, ranking, dedup) is pure Python with no
network calls. This means:
- Ranking bugs reproduce instantly without an API key
- A model swap cannot silently change your scores
- Unit tests run in milliseconds

**Port / adapter pattern** — `StructuredLLM` and `JobSource` are structural Protocols. The graph
knows nothing about OpenAI or JSearch. Swapping providers is a one-line change in
`infrastructure/`. `MockJobSource` and `FakeLLM` live in `infrastructure/` (not `tests/`) so
demos and integration tests share the same test doubles.

**Composition root** — `build_job_search_graph` takes ports in, returns a compiled graph.
Every dependency is injected; nothing is imported at graph-construction time except ports.

**Reducer correctness** — `raw_jobs` is a plain overwrite field (not `operator.add`) so each
retry pass scores only its own jobs. `errors` is additive because multiple nodes write to it.
Both choices are documented in `state.py`.

---

## Quickstart (no API keys)

```bash
git clone <repo>
cd job-application-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .

python demo.py
```

You'll see both scenarios run — including the broaden-and-retry cycle on scenario 2 — with zero
network calls. The demo uses `MockJobSource` + `FakeLLM`.

---

## Running with real LLM (OpenRouter)

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENROUTER_API_KEY=sk-or-...
USE_MOCK_SOURCES=true      # real LLM, fake jobs — good for testing the parsing/summary
```

```bash
uvicorn app.main:app --reload
```

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Senior Android Engineer, Seattle, 150k+"}'
```

Interactive docs at `http://localhost:8000/docs`.

### Choosing a model

`LLM_MODEL` in `.env` accepts any model slug from [openrouter.ai/models](https://openrouter.ai/models):

```
LLM_MODEL=openai/gpt-4o-mini          # default — fast, cheap
LLM_MODEL=anthropic/claude-3.5-haiku  # stronger reasoning, slightly slower
LLM_MODEL=google/gemini-flash-1.5     # fast alternative
```

### Adding real job data (optional)

Get a free [JSearch key on RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
(200 req/month free). Add to `.env`:

```
JSEARCH_API_KEY=your-key
USE_MOCK_SOURCES=false
```

JSearch aggregates LinkedIn, Indeed, Glassdoor, and ZipRecruiter through their API —
no scraping, no ToS violations.

---

## Running tests

```bash
pytest tests/ -v
```

```
tests/unit/test_matching.py          15 tests   — pure domain, no network, <50ms
tests/integration/test_graph.py       8 tests   — full graph with FakeLLM + MockJobSource
```

Notable integration tests:
- `test_impossible_salary_triggers_broaden_cycle` — verifies the retry cycle fires and terminates
- `test_retry_scores_only_attempt2_jobs` — regression for the reducer isolation bug
- `test_dead_source_does_not_kill_the_run` — verifies per-source fault tolerance

---

## Adding a new job source

1. Create `app/infrastructure/scrapers/my_source.py` implementing two methods:
   ```python
   @property
   def name(self) -> str: ...
   async def search(self, criteria: SearchCriteria) -> list[Job]: ...
   ```
2. Wire it in `app/interfaces/api/dependencies.py` under `_build_sources`.
3. Done — the graph, state, and scoring are untouched.

---

## API reference

### `POST /api/v1/search`

```json
{
  "query": "Senior Android Engineer, Seattle, 150k+",
  "max_results": 25,
  "include_cover_letters": false,
  "profile": {
    "headline": "Android engineer, 7 years",
    "years_experience": 7,
    "skills": ["Kotlin", "Jetpack Compose", "Android"]
  }
}
```

Response:
```json
{
  "query": "...",
  "summary": "Three strong matches found...",
  "results": [
    {
      "job": { "title": "...", "company": "...", "location": "...", "salary": {...} },
      "score": 0.94,
      "rationale": "Strongest signal: skill overlap (1.00). Weakest: salary fit (0.80).",
      "matched_skills": ["Kotlin", "Android"],
      "missing_skills": [],
      "cover_letter": null
    }
  ],
  "total_found": 4,
  "warnings": []
}
```

### `GET /api/v1/health`

```json
{ "status": "ok" }
```

---

## What's intentionally out of scope

This project is a **portfolio demonstration**, not a production service. The following are
known gaps that would need addressing before a real deployment:

| Gap | What's needed |
|-----|---------------|
| No authentication | Add Bearer token or API key header middleware |
| No rate limiting | Add `slowapi` or an API gateway in front |
| In-memory checkpointer | Replace `MemorySaver` with `langgraph-checkpoint-postgres` for multi-worker / persistent state |
| No persistence layer | `repositories.py` ports are defined but not implemented — add SQLite/Postgres adapters |
| CORS open (`*`) | Restrict to known origins in production |
| Single-process only | `lru_cache` on the graph is fine for one process; use a shared graph store for horizontal scale |

---

## Project structure at a glance

```
├── app/
│   ├── domain/                   Zero framework dependencies
│   │   ├── entities/             job.py · candidate.py · search_criteria.py
│   │   ├── ports/                llm.py · job_source.py
│   │   └── services/matching.py  Pure scoring — no LLM, no I/O
│   ├── agents/
│   │   ├── graphs/               job_search_graph.py
│   │   ├── nodes/                parse_query · search_jobs · filter_and_score · summarize · cover_letter
│   │   └── state.py
│   ├── application/              use_cases/ · dto/schemas.py
│   ├── infrastructure/           langchain_llm · jsearch_source · mock_source · settings
│   └── interfaces/api/           FastAPI router · dependency injection
├── tests/
│   ├── unit/                     test_matching.py
│   └── integration/              test_graph.py
├── demo.py                       Zero-config runnable demo
├── requirements.txt
└── .env.example
```
