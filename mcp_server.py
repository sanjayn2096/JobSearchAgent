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
                "and broadens the search automatically if too few results are found. "
                "Returns a summary and ranked list of matches with fit scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural-language job search query. "
                            "Examples: 'Senior Android Engineer, Seattle, 150k+', "
                            "'Remote Python backend, fintech, staff level'"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10)",
                        "default": 10,
                    },
                    "include_cover_letters": {
                        "type": "boolean",
                        "description": "Draft cover letters for the top 3 matches (requires a profile)",
                        "default": False,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "search_jobs":
        raise ValueError(f"Unknown tool: {name}")

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

    # Format into readable text Claude can reason over
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
