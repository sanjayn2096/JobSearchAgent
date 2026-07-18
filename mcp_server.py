"""MCP server — exposes the job search agent as Claude tools.

## Claude Code (local, points at Railway):
    claude mcp add job-agent \
      -e API_BASE=https://pure-emotion-production-f0d8.up.railway.app \
      -- python /path/to/mcp_server.py

## Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "job-agent": {
          "command": "python",
          "args": ["/path/to/mcp_server.py"],
          "env": { "API_BASE": "https://pure-emotion-production-f0d8.up.railway.app" }
        }
      }
    }

## Claude.ai connector (remote — served by FastAPI at /mcp):
    URL: https://pure-emotion-production-f0d8.up.railway.app/mcp
"""
from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

mcp = FastMCP("job-agent")


@mcp.tool()
async def search_jobs(
    query: str,
    max_results: int = 10,
    include_cover_letters: bool = False,
) -> str:
    """Search for jobs using a natural-language query. Scores and ranks results, broadens automatically if too few results."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{API_BASE}/api/v1/search",
            json={"query": query, "max_results": max_results, "include_cover_letters": include_cover_letters},
        )
        r.raise_for_status()
        data = r.json()

    lines = [f"**{data['total_found']} jobs found** — {data['summary']}", ""]
    for i, item in enumerate(data["results"], 1):
        j = item["job"]
        sal = (
            f"${j['salary']['minimum']:,}–${j['salary']['maximum']:,} {j['salary']['currency']}"
            if j["salary"]["disclosed"] else "salary undisclosed"
        )
        posted = f" · posted {j['posted_at'][:10]}" if j.get("posted_at") else ""
        lines += [
            f"{i}. **{j['title']}** at {j['company']}",
            f"   {j['location']} · {sal}{posted} · score {item['score']:.2f}",
            f"   {item['rationale']}",
        ]
        if item.get("cover_letter"):
            lines.append(f"   *Cover letter:* {item['cover_letter'][:300]}…")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def upload_resume(file_path: str) -> str:
    """Parse and store a resume from a local PDF or DOCX file. Call once before daily searches."""
    with open(file_path, "rb") as f:
        data = f.read()
    filename = file_path.split("/")[-1]
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{API_BASE}/api/v1/resume", files={"file": (filename, data)})
        r.raise_for_status()
        result = r.json()
    return f"Resume stored. Headline: {result['headline']} | Skills: {result['skills_found']}"


@mcp.tool()
async def get_status() -> str:
    """Get system status: next scheduled run time (PDT), whether a resume is uploaded, and the daily search query."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{API_BASE}/api/v1/status")
        r.raise_for_status()
        s = r.json()
    resume = "uploaded" if s["has_resume"] else "NOT uploaded"
    next_run = s["next_run_utc"] or "scheduler not running"
    return f"Resume: {resume}\nNext run (UTC): {next_run}\nDaily query: {s['daily_query']}"


@mcp.tool()
async def list_runs() -> str:
    """List all past daily job search runs with dates and job counts."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{API_BASE}/api/v1/runs")
        r.raise_for_status()
        runs = r.json()
    if not runs:
        return "No runs yet."
    lines = []
    for run in runs:
        lines.append(f"- {run['date']} | {run['job_count']} jobs | top: {run['top_job'] or '—'} | id: {run['run_id']}")
    return "\n".join(lines)


@mcp.tool()
async def get_run(run_id: str) -> str:
    """Get the full detail of a daily run: jobs with scores, resume tweaks, contacts and outreach drafts."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{API_BASE}/api/v1/runs/{run_id}")
        r.raise_for_status()
        run = r.json()
    lines = [f"**Run {run['date']}** — query: {run['query']}", ""]
    for job in run.get("jobs", []):
        lines.append(f"### {job['title']} @ {job['company']} (score {job['score']:.2f})")
        lines.append(f"   {job['location']} — {job['url']}")
        for t in job.get("resume_tweaks", []):
            lines.append(f"   [{t['kind'].upper()}] {t['section']}: {t['suggested']}")
        for c in job.get("contacts", []):
            lines.append(f"   Contact: {c['name']} ({c['title']}) {c.get('email','')}")
            if c.get("outreach_body"):
                lines.append(f"   Draft: {c['outreach_body'][:200]}…")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def approve_daily_run(run_id: str) -> str:
    """Approve a daily run to generate cover letters, resume tweaks, and outreach packages, then email them."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{API_BASE}/api/v1/approve/{run_id}")
        r.raise_for_status()
    return f"Approved run {run_id}. Application packages saved and email sent."


@mcp.tool()
async def trigger_daily_run() -> str:
    """Manually trigger the daily job search right now (for testing or on-demand runs)."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{API_BASE}/api/v1/admin/trigger-daily")
        r.raise_for_status()
        result = r.json()
    return result.get("message", str(result))


if __name__ == "__main__":
    mcp.run()
