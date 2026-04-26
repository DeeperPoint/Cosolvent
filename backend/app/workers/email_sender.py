"""Background task: send emails via Resend."""

from __future__ import annotations

import logging

import resend

from app.core.config import settings

logger = logging.getLogger("cosolvent.worker.email")


async def send_email_task(
    ctx: dict,
    to: str,
    subject: str,
    html: str,
) -> None:
    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not configured — skipping email to %s. "
            "Set RESEND_API_KEY in .env to enable email delivery.",
            to,
        )
        return

    if not settings.email_from:
        logger.warning(
            "EMAIL_FROM not set — skipping email to %s. Set EMAIL_FROM in .env "
            "to a sender address Resend has authorised (a verified domain, or "
            "``onboarding@resend.dev`` for sandbox use).",
            to,
        )
        return

    resend.api_key = settings.resend_api_key

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html,
        })
    except resend.exceptions.ResendError as exc:
        message = str(exc)
        # Resend's most common dev-time failure modes — log them as actionable
        # warnings instead of opaque tracebacks so the operator knows what to fix.
        if "verify a domain" in message or "only send testing emails" in message:
            logger.warning(
                "Resend rejected email to %s in sandbox mode (from=%s). %s "
                "To send to arbitrary recipients, verify a domain at "
                "resend.com/domains and set EMAIL_FROM to an address on it.",
                to,
                settings.email_from,
                message,
            )
        elif "not authorized to send emails from" in message:
            logger.warning(
                "Resend rejected EMAIL_FROM=%s — that domain isn't verified on "
                "this Resend account. Use onboarding@resend.dev for sandbox, "
                "or verify the domain at resend.com/domains.",
                settings.email_from,
            )
        else:
            logger.error("Resend API error sending to %s: %s", to, message)
        return
    except Exception:
        logger.error("Unexpected error sending email to %s", to, exc_info=True)
        return

    logger.info("Email sent to %s: %s", to, subject)
