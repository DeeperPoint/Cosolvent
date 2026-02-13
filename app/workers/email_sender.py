"""Background task: send emails via Resend."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("cosolvent.worker.email")


async def send_email_task(
    ctx: dict,
    to: str,
    subject: str,
    html: str,
) -> None:
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured, skipping email to %s", to)
        return

    import resend
    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info("Email sent to %s: %s", to, subject)
    except Exception:
        logger.error("Failed to send email to %s", to, exc_info=True)
