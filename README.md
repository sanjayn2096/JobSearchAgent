# Job Application Agent

Upload your resume. The agent searches for jobs every day, suggests how to tailor your resume for the best matches, finds recruiters and hiring managers at those companies, and drafts outreach emails — all delivered to your inbox. Approve in one click to generate your application package.

---

## What it does

Every morning the agent:

1. **Searches job boards** — queries multiple sources concurrently for your target role
2. **Filters and ranks** — removes anything that doesn't meet your requirements, scores the rest
3. **Retries if needed** — if results are thin, relaxes the tightest constraint and searches again
4. **Suggests resume tweaks** — for each top job, tells you exactly which lines to reword, add, or surface to improve fit
5. **Finds contacts** — looks up a recruiter and a hiring manager at each company via Apollo.io
6. **Drafts outreach emails** — short, specific cold emails for each contact
7. **Emails you a digest** — one email with everything: jobs, resume diffs, contacts, and drafted outreach
8. **Generates application packages on approval** — click one link and it saves a per-job folder with your cover letter, tailored resume notes, and outreach drafts ready to send

---

## Quick start (no API keys needed)

```bash
git clone <repo>
cd job-application-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
python demo.py
```

This runs two example searches against built-in fake data so you can see the agent work — including the retry logic — before setting anything up.

---

## Run it as an API

```bash
cp .env.example .env
# Fill in at minimum: OPENROUTER_API_KEY
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API browser.

### Upload your resume

```bash
curl -X POST http://localhost:8000/api/v1/resume \
  -F "file=@/path/to/your_resume.pdf"
```

Returns the parsed headline and skill count. The profile is stored and used for every daily run.

### Search interactively

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Senior Android Engineer, Seattle, 150k+"}'
```

### Approve a daily run

```bash
curl -X POST http://localhost:8000/api/v1/approve/{run_id}
```

`run_id` is included in the digest email. On approval, per-job packages are saved to `data/packages/{run_id}/`.

---

## Daily digest setup

Set these in `.env` to enable the daily scheduler:

```
# What to search for
DAILY_SEARCH_QUERY=Senior Software Engineer, Remote

# Email delivery
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-app-password   # Gmail App Password, not your main password
NOTIFICATION_EMAIL=you@gmail.com

# People search (app.apollo.io)
APOLLO_API_KEY=your-key

# Job data (rapidapi.com — 200 free searches/month)
JSEARCH_API_KEY=your-key

# Public URL for the approve link in the email
BASE_URL=https://your-app.up.railway.app
```

The scheduler fires at 8am daily. Change the hour with `DAILY_RUN_HOUR=9`.

---

## Use it with Claude

The agent ships with an MCP server so Claude can call it as a tool directly.

```bash
# 1. Start the agent
uvicorn app.main:app --port 8000

# 2. Register with Claude Code
claude mcp add job-search -- python /path/to/mcp_server.py
```

Claude then has three tools: `upload_resume`, `search_jobs`, and `approve_daily_run`. You can say *"Upload my resume at ~/resume.pdf then find senior backend roles in Austin"* and Claude handles it end-to-end.

---

## Deploy to Railway

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Then in the Railway dashboard:
- **Volumes** → Add volume, mount at `/app/data` — this persists your profile, run history, and packages across deploys
- **Variables** → Add all keys from `.env.example`
- **Settings → Domains** → Generate a public URL, set it as `BASE_URL`

---

## Which AI model to use

Set `LLM_MODEL` in `.env`. Any model on [openrouter.ai/models](https://openrouter.ai/models) works:

```
LLM_MODEL=openai/gpt-4o-mini          # fast and cheap (default)
LLM_MODEL=anthropic/claude-3.5-haiku  # better writing quality
LLM_MODEL=google/gemini-flash-1.5     # another fast option
```

---

## Run the tests

```bash
pytest tests/ -v
```

No internet or API keys needed — tests use built-in fake data and a fake LLM.

---

## Known limitations

| What's missing | What it would need |
|---|---|
| No authentication | API key or token checking on all routes |
| No rate limiting | Request limits to prevent abuse |
| JSON file storage | A database for multi-user or horizontal scaling |
| CORS allows all origins | Lock down to specific domains in production |

---

## How it's built

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical breakdown — how AI is used, how LangGraph works, and the tradeoffs behind the key decisions.
