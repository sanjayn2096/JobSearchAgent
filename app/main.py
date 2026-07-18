"""FastAPI entrypoint.

    uvicorn app.main:app --reload
    open http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.infrastructure.config.settings import get_settings
from app.infrastructure.scheduler.daily_run import start_scheduler, stop_scheduler
from app.interfaces.api.dependencies import get_daily_use_case
from app.interfaces.api.routes import jobs, resume, approve, runs, analyze, admin
import mcp_server as _mcp_module


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    logging.getLogger(__name__).info(
        "Starting %s in %s mode", settings.app_name, settings.environment
    )
    start_scheduler(get_daily_use_case())
    yield
    stop_scheduler()
    logging.getLogger(__name__).info("Shutting down")


app = FastAPI(
    title="Job Application Agent",
    description=(
        "Agentic job search with daily digest, resume tailoring, contact discovery, "
        "and outreach drafting."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(resume.router)
app.include_router(approve.router)
app.include_router(runs.router)
app.include_router(analyze.router)
app.include_router(admin.router)

# Remote MCP connector — Claude.ai can add this as a connector at /mcp
app.mount("/mcp", _mcp_module.mcp.streamable_http_app())

# Serve React frontend — mount assets directory for hashed bundles, then
# catch-all to return index.html so client-side routing works.
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    _assets_dir = _static_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str) -> FileResponse:
        return FileResponse(str(_static_dir / "index.html"))
