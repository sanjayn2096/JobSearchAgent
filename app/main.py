"""FastAPI entrypoint.

    uvicorn app.main:app --reload
    open http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.config.settings import get_settings
from app.interfaces.api.routes import jobs


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
    yield
    logging.getLogger(__name__).info("Shutting down")


app = FastAPI(
    title="Job Application Agent",
    description=(
        "An agentic job search built with LangChain + LangGraph on a clean "
        "architecture core. Parses natural language, searches multiple boards "
        "concurrently, scores deterministically, and replans when results are thin."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)


@app.get("/", tags=["ops"])
async def root() -> dict:
    return {"service": "job-application-agent", "docs": "/docs"}
