from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse

from app.infrastructure.config.settings import get_settings
from app.infrastructure.email.smtp import send_html
from app.infrastructure.storage.run_store import load_run

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["approve"])


def _packages_dir() -> Path:
    return Path(get_settings().data_dir) / "packages"


@router.post("/approve/{run_id}", response_class=HTMLResponse)
async def approve_run(run_id: str) -> HTMLResponse:
    """Approve today's job digest. Saves per-job application packages and emails them."""
    try:
        run = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run {run_id} not found")

    pkg_dir = _packages_dir() / run_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    job_summaries = []
    for job in run.get("jobs", []):
        safe_name = job["company"].replace(" ", "_").replace("/", "-")
        job_dir = pkg_dir / f"{safe_name}_{job['id'][:8]}"
        job_dir.mkdir(exist_ok=True)

        _write_package_files(job_dir, job)
        job_summaries.append(
            f"<li><a href='{job['url']}'>{job['title']} @ {job['company']}</a> "
            f"— package saved to <code>{job_dir}</code></li>"
        )

    settings = get_settings()
    if settings.smtp_username and settings.notification_email:
        subject, html = _build_approval_email(run, run_id)
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
            logger.exception("Failed to send approval email")

    return HTMLResponse(
        f"<html><body style='font-family:sans-serif;max-width:600px;margin:auto;padding:24px'>"
        f"<h2>Application packages ready</h2>"
        f"<ul>{''.join(job_summaries)}</ul>"
        f"<p>Each folder contains your tailored cover letter, resume tweaks, and contact drafts.</p>"
        f"</body></html>"
    )


def _write_package_files(job_dir: Path, job: dict) -> None:
    if job.get("cover_letter"):
        (job_dir / "cover_letter.txt").write_text(job["cover_letter"])

    tweaks = job.get("resume_tweaks", [])
    if tweaks:
        lines = [f"=== Resume Tweaks for {job['title']} @ {job['company']} ===\n"]
        for t in tweaks:
            lines.append(f"[{t['kind'].upper()}] {t['section']}")
            if t.get("original"):
                lines.append(f"  Original : {t['original']}")
            lines.append(f"  Suggested: {t['suggested']}")
            lines.append(f"  Why      : {t['reason']}\n")
        (job_dir / "resume_tweaks.txt").write_text("\n".join(lines))

    contacts = job.get("contacts", [])
    if contacts:
        lines = [f"=== Outreach Contacts for {job['title']} @ {job['company']} ===\n"]
        for c in contacts:
            lines.append(f"Name   : {c['name']}")
            lines.append(f"Title  : {c['title']}")
            lines.append(f"Email  : {c.get('email') or 'not found'}")
            lines.append(f"LinkedIn: {c.get('linkedin_url') or '—'}")
            if c.get("outreach_body"):
                lines.append(f"\nSubject: {c['outreach_subject']}")
                lines.append(c["outreach_body"])
            lines.append("")
        (job_dir / "outreach.txt").write_text("\n".join(lines))


def _build_approval_email(run: dict, run_id: str) -> tuple[str, str]:
    subject = f"Application packages ready — {run.get('date', run_id)}"
    items = "".join(
        f"<li><a href='{j['url']}'>{j['title']} @ {j['company']}</a></li>"
        for j in run.get("jobs", [])
    )
    html = (
        f"<html><body style='font-family:sans-serif'>"
        f"<h2>Your application packages are ready</h2>"
        f"<p>Packages saved to <code>data/packages/{run_id}/</code></p>"
        f"<ul>{items}</ul>"
        f"<p>Each folder has cover_letter.txt, resume_tweaks.txt, and outreach.txt.</p>"
        f"</body></html>"
    )
    return subject, html
