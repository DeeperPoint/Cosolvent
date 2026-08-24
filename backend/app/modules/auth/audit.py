"""Authentication audit trail.

Records who authenticated, how, and from where. Two reasons this exists rather
than relying on request logs:

  - **Incident response.** When a credential leaks, the first question is "what
    did it touch, and since when". Request logs answer that badly: they don't
    distinguish a cookie session from an API key, and they rotate.
  - **Sponsor security review.** A server-to-server integration is normally
    gated on being able to show an audit trail for credential issuance and use.

Writes are best-effort: an audit failure must never block or fail the
authentication it is describing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from app.core.database import get_collection

logger = logging.getLogger("cosolvent.auth.audit")

# Event names are a closed vocabulary so they stay queryable.
LOGIN_SUCCEEDED = "login.succeeded"
LOGIN_FAILED = "login.failed"
LOGIN_THROTTLED = "login.throttled"
LOGOUT = "logout"
API_KEY_CREATED = "api_key.created"
API_KEY_REVOKED = "api_key.revoked"
API_KEY_AUTH_FAILED = "api_key.auth_failed"


def request_context(request: Request | None) -> dict[str, Any]:
    """Extract the forensic fields worth keeping from a request."""
    if request is None:
        return {}
    return {
        "ip": client_ip(request),
        # Truncated: a user agent is a weak fingerprint, not a payload to store whole.
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "origin": request.headers.get("origin"),
    }


def client_ip(request: Request | None) -> str | None:
    """Best-effort client IP.

    `X-Forwarded-For` is only meaningful behind a proxy that sets it and strips
    any client-supplied value; treat it as a hint for rate limiting and audit,
    never as an authorization input.
    """
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def record(
    event: str,
    *,
    user_id: str | None = None,
    email: str | None = None,
    request: Request | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append an auth event. Never raises."""
    doc = {
        "event": event,
        "user_id": str(user_id) if user_id else None,
        "email": email,
        "created_at": datetime.now(timezone.utc),
        **request_context(request),
    }
    if detail:
        doc["detail"] = detail

    try:
        await get_collection("auth_audit").insert_one(doc)
    except Exception:  # noqa: BLE001 - auditing must not break authentication
        logger.warning("Failed to record auth audit event %s", event, exc_info=True)
