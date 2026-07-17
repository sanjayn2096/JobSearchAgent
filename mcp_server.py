"""MCP server that exposes the job search agent as a Claude tool.

Run alongside the FastAPI server:
    uvicorn app.main:app --port 8000 &
    python mcp_server.py

Then add to Claude Code:
    claude mcp add job-search -- python /path/to/mcp_server.py

Or add to ~/.claude/claude_desktop_config.json for Claude Desktop:
    {
      "mcpServers": {
        "job-search": {
          "command": "python",
          "args": ["/path/to/mcp_server.py"],
          "env": { "API_BASE": "http://localhost:8000" }
        }
      }
    }
"""
from __future__ import annotations

import json
import os

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

server = Server("job-search-agent")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_jobs",
            description=(
                "Search for jobs using a natural-language query. "
                "Parses intent, fans out across job boards, scores and ranks results, "
                "and broadens the search automatically if too few results are found."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language job search. E.g. 'Senior Android Engineer, Seattle, 150k+'",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10)",
                        "default": 10,
                    },
                    "include_cover_letters": {
                        "type": "boolean",
                        "description": "Draft cover letters for top 3 matches (requires a stored resume)",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="upload_resume",
            description=(
                "Parse and store a resume from a local file path (PDF or DOCX). "
                "The stored profile is used for daily job matching, resume tweaks, "
                "and outreach drafts. Call this once before running daily searches."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the PDF or DOCX resume file",
                    },
                },
                "required": ["file_path"],
            },
        ),
        types.Tool(
            name="approve_daily_run",
            description=(
                "Approve a daily job digest by its run ID. "
                "Generates per-job application packages (cover letter, resume tweaks, "
                "outreach drafts) and emails them. The run ID is included in the digest email."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Run ID from the daily digest email",
                    },
                },
                "required": ["run_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_jobs":
        return await _search_jobs(arguments)
    if name == "upload_resume":
        return await _upload_resume(arguments)
    if name == "approve_daily_run":
        return await _approve_daily_run(arguments)
    raise ValueError(f"Unknown tool: {name}")


async def _search_jobs(arguments: dict) -> list[types.TextContent]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/api/v1/search",
            json={
                "query": arguments["query"],
                "max_results": arguments.get("max_results", 10),
                "include_cover_letters": arguments.get("include_cover_letters", False),
            },
        )
        response.raise_for_status()
        data = response.json()

    lines = [f"**Summary:** {data['summary']}", ""]
    for i, r in enumerate(data["results"], 1):
        j = r["job"]
        sal = (
            f"{j['salary']['minimum']:,}–{j['salary']['maximum']:,} {j['salary']['currency']}"
            if j["salary"]["disclosed"]
            else "salary undisclosed"
        )
        lines.append(f"{i}. **{j['title']}** at {j['company']}")
        lines.append(f"   {j['location']} · {sal} · fit score {r['score']:.2f}")
        lines.append(f"   {r['rationale']}")
        if r.get("cover_letter"):
            lines.append(f"   *Cover letter:* {r['cover_letter']}")
        lines.append("")
    if data.get("warnings"):
        lines.append(f"_Warnings: {'; '.join(data['warnings'])}_")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _upload_resume(arguments: dict) -> list[types.TextContent]:
    file_path = arguments["file_path"]
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    filename = file_path.split("/")[-1]

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/api/v1/resume",
            files={"file": (filename, file_bytes)},
        )
        response.raise_for_status()
        data = response.json()

    return [types.TextContent(
        type="text",
        text=f"Resume uploaded. Headline: {data['headline']} | Skills found: {data['skills_found']}",
    )]


async def _approve_daily_run(arguments: dict) -> list[types.TextContent]:
    run_id = arguments["run_id"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{API_BASE}/api/v1/approve/{run_id}")
        response.raise_for_status()

    return [types.TextContent(
        type="text",
        text=f"Approved run {run_id}. Application packages saved to data/packages/{run_id}/",
    )]


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
