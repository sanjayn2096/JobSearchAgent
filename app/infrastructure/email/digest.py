from __future__ import annotations

from datetime import date


def build_digest(run: dict, approve_url: str) -> tuple[str, str]:
    """Returns (subject, html_body) for the daily digest email."""
    today = run.get("date", date.today().isoformat())
    subject = f"Job Digest {today} — {len(run['jobs'])} matches"

    sections = []
    for i, job in enumerate(run["jobs"], 1):
        tweaks_html = _tweaks_section(job.get("resume_tweaks", []))
        contacts_html = _contacts_section(job.get("contacts", []))

        sections.append(f"""
<div style="border:1px solid #ddd;border-radius:6px;padding:16px;margin-bottom:20px;">
  <h3 style="margin:0 0 4px">{i}. {job['title']} — {job['company']}</h3>
  <p style="margin:0 0 8px;color:#555">{job['location']} &nbsp;|&nbsp; Fit score: <strong>{job['score']:.0%}</strong> &nbsp;|&nbsp;
     <a href="{job['url']}">View posting</a></p>

  <h4 style="margin:12px 0 6px">Resume tweaks</h4>
  {tweaks_html}

  <h4 style="margin:12px 0 6px">Cover letter</h4>
  <p style="white-space:pre-wrap;background:#f9f9f9;padding:10px;border-radius:4px">{job.get('cover_letter','—')}</p>

  {contacts_html}
</div>""")

    body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:700px;margin:auto;padding:24px">
<h2>Your Daily Job Digest — {today}</h2>
<p>Search: <em>{run.get('query','')}</em></p>
{''.join(sections)}
<div style="text-align:center;margin-top:32px">
  <a href="{approve_url}"
     style="background:#2563eb;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:16px">
    ✓ Approve &amp; prepare application package
  </a>
</div>
</body></html>"""

    return subject, body


def _tweaks_section(tweaks: list[dict]) -> str:
    if not tweaks:
        return "<p style='color:#888'>No tweaks suggested.</p>"
    rows = ""
    for t in tweaks:
        badge_color = {"add": "#16a34a", "reword": "#2563eb", "remove": "#dc2626", "surface": "#d97706"}.get(
            t["kind"], "#555"
        )
        rows += f"""
<tr>
  <td style="padding:6px 8px;vertical-align:top">
    <span style="background:{badge_color};color:#fff;border-radius:3px;padding:1px 6px;font-size:11px">{t['kind'].upper()}</span>
    <span style="color:#888;font-size:12px;margin-left:6px">{t['section']}</span>
  </td>
  <td style="padding:6px 8px;color:#555;font-size:13px">{t.get('original') or '—'}</td>
  <td style="padding:6px 8px;font-size:13px">{t['suggested']}</td>
  <td style="padding:6px 8px;color:#888;font-size:12px">{t['reason']}</td>
</tr>"""
    return f"""<table style="width:100%;border-collapse:collapse;font-size:13px">
  <tr style="background:#f3f4f6">
    <th style="padding:6px 8px;text-align:left">Type</th>
    <th style="padding:6px 8px;text-align:left">Original</th>
    <th style="padding:6px 8px;text-align:left">Suggested</th>
    <th style="padding:6px 8px;text-align:left">Reason</th>
  </tr>
  {rows}
</table>"""


def _contacts_section(contacts: list[dict]) -> str:
    if not contacts:
        return ""
    cards = ""
    for c in contacts:
        email_display = f'<a href="mailto:{c["email"]}">{c["email"]}</a>' if c.get("email") else "Email not found"
        cards += f"""
<div style="background:#f0f9ff;border-radius:4px;padding:10px;margin-bottom:10px">
  <strong>{c['name']}</strong> — {c['title']}<br>
  {email_display}
  <div style="margin-top:8px">
    <strong>Draft:</strong> {c.get('outreach_subject','')}<br>
    <pre style="white-space:pre-wrap;font-size:12px;background:#fff;padding:8px;border-radius:3px;margin:6px 0 0">{c.get('outreach_body','')}</pre>
  </div>
</div>"""
    return f"<h4 style='margin:12px 0 6px'>Contacts & outreach drafts</h4>{cards}"
