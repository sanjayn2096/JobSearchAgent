from __future__ import annotations

from fastapi import APIRouter

from app.infrastructure.scheduler.daily_run import _run_daily
from app.interfaces.api.dependencies import get_daily_use_case
from app.infrastructure.storage.run_store import load_profile

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/trigger-daily")
async def trigger_daily_run() -> dict:
    """Manually trigger the daily run for testing."""
    profile = load_profile()
    if not profile:
        return {"status": "error", "reason": "No resume uploaded"}

    await _run_daily(
        daily_use_case=get_daily_use_case(),
        profile_loader=load_profile,
    )
    return {"status": "ok", "message": "Daily run completed — check logs"}
