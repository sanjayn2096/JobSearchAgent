from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


async def send_html(
    *,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    html: str,
) -> None:
    # smtp_host/port/username kept in signature for backwards compat,
    # but we send via Resend API (Railway blocks outbound SMTP).
    api_key = password  # reuse SMTP_PASSWORD field to store Resend API key
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_addr, "to": [to_addr], "subject": subject, "html": html},
        )
        resp.raise_for_status()
    logger.info("Email sent via Resend to %s: %s", to_addr, subject)
