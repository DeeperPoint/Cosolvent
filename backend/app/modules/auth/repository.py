from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


from app.core.database import get_collection
from app.core.config import settings
from app.core.security import generate_session_token


async def find_user_by_email(email: str) -> dict | None:
    return await get_collection("users").find_one({"email": email})


async def find_user_by_id(user_id: str) -> dict | None:
    return await get_collection("users").find_one({"_id": user_id})


async def create_user(
    email: str,
    password_hash: str | None,
    participant_type: str | None,
    role: str = "user",
    bootstrap_marker: str | None = None,
) -> dict[str, Any]:
    doc = {
        "email": email,
        "participant_type": participant_type,
        "role": role,
        "is_active": True,
        "has_onboarded": False,
        "created_at": datetime.now(timezone.utc),
    }
    if password_hash is not None:
        doc["password_hash"] = password_hash
    if bootstrap_marker is not None:
        doc["bootstrap_marker"] = bootstrap_marker
    result = await get_collection("users").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def create_session(user_id: str) -> str:
    token = generate_session_token()
    await get_collection("sessions").insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    })
    return token


async def delete_session(token: str) -> None:
    await get_collection("sessions").delete_one({"token": token})


async def count_admins() -> int:
    return await get_collection("users").count_documents({"role": "admin"})


# ── WebSocket auth tickets ────────────────────────────────────────────────
#
# HttpOnly session cookies aren't reliably attached to cross-port WebSocket
# upgrades from the browser, so authenticated callers exchange their cookie
# for a short-lived, single-use ticket they can pass in the WS auth message.

WS_TICKET_TTL_SECONDS = 60


async def create_ws_ticket(user_id: str) -> tuple[str, int]:
    token = generate_session_token()
    now = datetime.now(timezone.utc)
    await get_collection("ws_tickets").insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=WS_TICKET_TTL_SECONDS),
        "used_at": None,
    })
    return token, WS_TICKET_TTL_SECONDS


async def consume_ws_ticket(token: str) -> str | None:
    """Return the user_id for a valid, unused ticket and mark it spent.

    Returns ``None`` if the ticket is unknown, already spent, or expired.
    """
    if not token:
        return None
    coll = get_collection("ws_tickets")
    doc = await coll.find_one({"token": token})
    if not doc:
        return None
    if doc.get("used_at") is not None:
        return None
    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        return None
    await coll.update_one(
        {"token": token, "used_at": None},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )
    return str(doc["user_id"])
