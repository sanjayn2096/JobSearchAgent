from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.infrastructure.config.settings import get_settings
from app.infrastructure.scheduler.daily_run import get_next_run_time
from app.infrastructure.storage.run_store import list_runs, load_profile, load_run

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.get("/runs")
async def get_runs() -> list[dict]:
    return list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    try:
        return load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run {run_id} not found")


@router.get("/status")
async def get_status() -> dict:
    next_run = get_next_run_time()
    return {
        "next_run_utc": next_run.isoformat() if next_run else None,
        "has_resume": load_profile() is not None,
        "daily_query": get_settings().daily_search_query,
    }
