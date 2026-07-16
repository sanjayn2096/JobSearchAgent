# Job Application Agent

Tell it what kind of job you're looking for. It searches, filters, ranks, and writes you a summary — and if it doesn't find enough matches, it automatically tries again with slightly relaxed requirements.

No clicking through job boards. No copy-pasting. Just describe the role you want.

---

## What it does

You send a message like:

> *"Senior Android Engineer in Seattle, at least 150k"*

The agent:

1. **Understands your request** — figures out the job title, location, salary, seniority level, and any skills you mentioned
2. **Searches job boards** — queries multiple sources at the same time
3. **Filters and scores results** — removes anything that doesn't meet your requirements, then ranks what's left by how well it fits
4. **Retries if needed** — if it only finds 1–2 matches, it automatically relaxes the tightest constraint (usually salary) and searches again
5. **Writes a summary** — explains the top results in plain language
6. **Drafts cover letter openers** — if you provide your profile, it writes a short, tailored opening for the top 3 matches

---

## Try it in 60 seconds (no accounts, no API keys)

```bash
git clone <repo>
cd job-application-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
python demo.py
```

This runs two example searches against built-in fake job data so you can see the agent work — including the retry logic — before setting anything up.

---

## Run it as an API

**With your OpenRouter key:**

```bash
cp .env.example .env
# Edit .env and add: OPENROUTER_API_KEY=sk-or-...
uvicorn app.main:app --reload
```

**Search for jobs:**

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Senior Android Engineer, Seattle, 150k+"}'
```

Or open `http://localhost:8000/docs` in your browser for a visual interface where you can fill in a form and click Run.

### Which AI model to use

Set `LLM_MODEL` in your `.env` file. Any model from [openrouter.ai/models](https://openrouter.ai/models) works:

```
LLM_MODEL=openai/gpt-4o-mini          # fast and cheap (default)
LLM_MODEL=anthropic/claude-3.5-haiku  # better at nuanced writing
LLM_MODEL=google/gemini-flash-1.5     # another fast option
```

### Real job data (optional)

The agent comes with built-in sample jobs for testing. To search real listings, get a free key from [JSearch on RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) (200 searches/month free) and add it to `.env`:

```
JSEARCH_API_KEY=your-key
USE_MOCK_SOURCES=false
```

JSearch pulls from LinkedIn, Indeed, Glassdoor, and ZipRecruiter via their official API — no scraping.

---

## Use it with Claude

The agent includes an MCP server so Claude can call it directly as a tool — you just talk to Claude and it handles the search for you.

```bash
# 1. Start the agent server
uvicorn app.main:app --port 8000

# 2. Register it with Claude Code
claude mcp add job-search -- python /path/to/mcp_server.py
```

Once registered, you can say to Claude: *"Find me senior Android roles in Seattle paying over 150k"* and it will search, get results back, and discuss them with you.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how this connection works under the hood.

---

## What you get back

```json
{
  "summary": "Three strong matches found. The best fit is the Staff role at Emerald Health — it matches your skills and clears your salary target. Results skew senior with two hybrid options in central Seattle.",
  "results": [
    {
      "job": {
        "title": "Staff Android Engineer",
        "company": "Emerald Health",
        "location": "Bellevue, WA (Remote)",
        "salary": { "minimum": 210000, "maximum": 260000 }
      },
      "score": 0.94,
      "rationale": "Strongest signal: skill overlap. Weakest: seniority fit.",
      "matched_skills": ["Kotlin", "Jetpack Compose", "Android"],
      "missing_skills": [],
      "cover_letter": null
    }
  ],
  "total_found": 4,
  "warnings": []
}
```

Each result includes a fit score (0–1), an explanation of why it scored that way, and which skills matched or were missing.

---

## Run the tests

```bash
pytest tests/ -v
```

23 tests, all passing. No internet connection or API keys needed — the tests use built-in fake data and a fake AI model.

---

## Known limitations

This is a portfolio project, not a production service. A few things would need work before deploying it publicly:

| What's missing | What it would need |
|---|---|
| No login or authentication | Add API key or token checking |
| No rate limiting | Prevent abuse with request limits |
| State resets on restart | Use a database-backed state store instead of in-memory |
| Only works with one server process | Needs shared state store for horizontal scaling |
| CORS allows all origins | Lock down to specific domains |

---

## How it's built

Curious about the technical decisions — how the AI is used, why LangGraph, what tradeoffs were made? See [ARCHITECTURE.md](ARCHITECTURE.md).
