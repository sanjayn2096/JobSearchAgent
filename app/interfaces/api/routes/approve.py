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


@router.get("/approve/{run_id}", response_class=HTMLResponse)
@router.post("/approve/{run_id}", response_class=HTMLResponse)
async def approve_run(run_id: str) -> HTMLResponse:
    """Approve today's job digest. Saves per-job application packages and emails them."""
    try:
        run = load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run {run_id} not found")

    pkg_dir = _packages_dir() / run_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    for job in run.get("jobs", []):
        safe_name = job["company"].replace(" ", "_").replace("/", "-")
        job_dir = pkg_dir / f"{safe_name}_{job['id'][:8]}"
        job_dir.mkdir(exist_ok=True)
        _write_package_files(job_dir, job)

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

    job_cards = []
    for job in run.get("jobs", []):
        tweaks_rows = "".join(
            f"<tr><td style='padding:4px 8px;color:#555'>{t['section']}</td>"
            f"<td style='padding:4px 8px'><strong>{t['kind']}</strong> — {t['suggested']}</td></tr>"
            for t in job.get("resume_tweaks", [])
        )
        tweaks_html = (
            f"<table style='width:100%;border-collapse:collapse;font-size:13px;margin-top:8px'>"
            f"{tweaks_rows}</table>"
            if tweaks_rows else "<p style='color:#888;font-size:13px'>No tweaks.</p>"
        )
        contacts_html = "".join(
            f"<div style='background:#f0f9ff;border-radius:4px;padding:8px;margin-bottom:8px;font-size:13px'>"
            f"<strong>{c['name']}</strong> — {c['title']}<br>"
            f"{'<a href=\"mailto:' + c['email'] + '\">' + c['email'] + '</a>' if c.get('email') else 'Email not found'}"
            f"</div>"
            for c in job.get("contacts", [])
        )
        job_cards.append(
            f"<div style='border:1px solid #ddd;border-radius:6px;padding:16px;margin-bottom:20px'>"
            f"<h3 style='margin:0 0 4px'>{job['title']} — {job['company']}</h3>"
            f"<p style='margin:0 0 8px;color:#555'>{job['location']}</p>"
            f"<a href='{job['url']}' target='_blank' "
            f"   style='display:inline-block;background:#2563eb;color:#fff;padding:8px 20px;"
            f"          border-radius:5px;text-decoration:none;font-size:14px;margin-bottom:12px'>"
            f"Apply Now →</a>"
            f"<h4 style='margin:12px 0 4px'>Resume tweaks</h4>{tweaks_html}"
            f"<h4 style='margin:12px 0 4px'>Cover letter</h4>"
            f"<p style='white-space:pre-wrap;background:#f9f9f9;padding:10px;border-radius:4px;font-size:13px'>{job.get('cover_letter','—')}</p>"
            + (f"<h4 style='margin:12px 0 4px'>Contacts</h4>{contacts_html}" if contacts_html else "")
            + "</div>"
        )

    return HTMLResponse(
        f"<!DOCTYPE html><html><body style='font-family:sans-serif;max-width:700px;margin:auto;padding:24px'>"
        f"<h2 style='color:#16a34a'>Application packages ready ✓</h2>"
        f"<p style='color:#555'>{len(run.get('jobs',[]))} jobs · {run.get('query','')}</p>"
        f"{''.join(job_cards)}"
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
