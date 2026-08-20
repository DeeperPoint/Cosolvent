"""Persistence for synthetic population profiles.

Kept separate from the participant-facing profiles repository: synthetic profiles
are keyed by a stable ``external_id`` (so re-imports upsert in place) and own a
synthetic user, and every record is flagged ``is_synthetic`` for the clean-cutover
guarantees.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection


async def create_synthetic_user(
    external_id: str,
    participant_type: str,
    *,
    email: str | None = None,
    password_hash: str | None = None,
) -> dict[str, Any]:
    """``email``/``password_hash`` are optional: the plain C0 ingest path leaves both
    unset (an unaddressable ``@population.local`` user — enough to own a matchable
    profile, not enough to log in). A caller building *interactive* demo accounts
    (see ``scripts/seed_demo_users.py``) supplies both so the synthetic user can
    actually authenticate — without that, demo-account creation had no reason to go
    through this watermarked path at all, which is exactly how it ended up bypassing
    GAP-9 enforcement before."""
    now = datetime.now(timezone.utc)
    doc = {
        "email": email or f"synthetic+{external_id}@population.local",
        "participant_type": participant_type,
        "role": "user",
        "is_active": True,
        "has_onboarded": True,
        "is_synthetic": True,
        "external_id": external_id,
        "created_at": now,
    }
    if password_hash:
        doc["password_hash"] = password_hash
    result = await get_collection("users").insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def upsert_synthetic_profile(
    external_id: str,
    participant_type: str,
    fields: dict[str, Any],
    completeness: int,
    *,
    email: str | None = None,
    password_hash: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Insert a new synthetic profile (creating its owner user) or update the
    existing one with the same ``external_id``. Returns (profile, created).

    ``email``/``password_hash`` only take effect on creation — an existing synthetic
    user's login credentials aren't rotated by a field refresh.
    """
    profiles = get_collection("profiles")
    now = datetime.now(timezone.utc)

    existing = await profiles.find_one({"external_id": external_id})
    if existing:
        await profiles.update_one(
            {"external_id": external_id},
            {"$set": {
                "participant_type": participant_type,
                "fields": fields,
                "completeness": completeness,
                "updated_at": now,
            }},
        )
        existing.update({"participant_type": participant_type, "fields": fields, "completeness": completeness})
        return existing, False

    user = await create_synthetic_user(
        external_id, participant_type, email=email, password_hash=password_hash
    )
    doc = {
        "user_id": str(user["_id"]),
        "participant_type": participant_type,
        "status": "active",
        "fields": fields,
        "ai_profile": None,
        "ai_profile_draft": None,
        "ai_profile_status": "none",
        "ai_profile_updated_at": None,
        "completeness": completeness,
        "is_synthetic": True,
        "external_id": external_id,
        "created_at": now,
        "updated_at": now,
    }
    result = await profiles.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc, True


async def count_synthetic_profiles() -> int:
    return await get_collection("profiles").count_documents({"is_synthetic": True})
