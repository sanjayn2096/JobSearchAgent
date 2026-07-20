from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infrastructure.config.settings import get_settings
from app.infrastructure.email.digest import build_digest
from app.infrastructure.email.smtp import send_html
from app.infrastructure.storage.run_store import load_profile, save_run

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


def start_scheduler(daily_use_case, profile_loader=load_profile) -> None:
    settings = get_settings()
    if not settings.daily_search_query:
        logger.info("DAILY_SEARCH_QUERY not set — daily scheduler disabled")
        return

    _scheduler.add_job(
        _run_daily,
        "cron",
        hour=settings.daily_run_hour,
        minute=0,
        kwargs={"daily_use_case": daily_use_case, "profile_loader": profile_loader},
    )
    _scheduler.start()
    logger.info("Daily scheduler started — fires at %02d:00", settings.daily_run_hour)


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown()


def get_next_run_time():
    jobs = _scheduler.get_jobs()
    return jobs[0].next_run_time if jobs else None


async def _run_daily(daily_use_case, profile_loader) -> None:
    settings = get_settings()
    profile_dict = profile_loader()
    if not profile_dict:
        logger.warning("No profile found — skipping daily run")
        return

    from app.domain.entities.candidate import CandidateProfile

    profile = CandidateProfile(**profile_dict)

    logger.info("Starting daily search: %s", settings.daily_search_query)
    try:
        run = await daily_use_case.execute(settings.daily_search_query, profile)
    except Exception:
        logger.exception("Daily search failed")
        return

    run_id = save_run(run)
    approve_url = f"{settings.base_url}/runs/{run_id}"
    subject, html = build_digest(run, approve_url)

    if settings.smtp_username and settings.notification_email:
        try:
            await send_html(
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                from_addr=settings.smtp_from or settings.smtp_username,
                to_addr=settings.notification_email,
                subject=subject,
                html=html,
            )
        except Exception:
            logger.exception("Failed to send digest email")
    else:
        logger.info("SMTP not configured — digest saved as run %s", run_id)
