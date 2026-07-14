"""Deals persistence: the deal record plus the event-sourced story chain.

Four document collections back the Story Progression System:
  * ``deals``            — the deal record (parties, instrument, disclosure level, state).
  * ``story_versions``   — immutable composed versions (narrative + snapshot + hash).
  * ``version_responses``— acknowledge / annotate / correct records (source of truth).
  * ``consent_records``  — disclosure-advance / attribute / audience-expansion consents.

Story versions are never updated in place except for their *derived* lifecycle marker
(``state``) and supersession — the content (narrative/snapshot/hash) is immutable once
written. Milestone status is always recomputed from responses; the stored ``state`` is a
cache, not the source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.database import get_collection

_DEALS = "deals"
_VERSIONS = "story_versions"
_RESPONSES = "version_responses"
_CONSENTS = "consent_records"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── deals ────────────────────────────────────────────────────────────────────
async def create_deal(doc: dict) -> dict:
    now = _now()
    doc = {**doc, "created_at": now, "updated_at": now}
    result = await get_collection(_DEALS).insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_deal(deal_id: str) -> dict | None:
    return await get_collection(_DEALS).find_one({"_id": deal_id})


async def update_deal(deal_id: str, updates: dict) -> dict | None:
    updates = {**updates, "updated_at": _now()}
    return await get_collection(_DEALS).find_one_and_update(
        {"_id": deal_id}, {"$set": updates}, return_document=True
    )


async def list_deals_for_user(user_id: str) -> list[dict]:
    # Query the flat ``participants`` membership index (array-of-objects) — the DB proxy
    # special-cases ``participants.*`` to a JSONB array-containment match. ``parties`` holds
    # the rich party set (roles, join/exit seq); ``participants`` mirrors user ids for lookup.
    cursor = get_collection(_DEALS).find({"participants.user_id": user_id}).sort("updated_at", -1)
    return await cursor.to_list(length=200)


# ── story versions ─────────────────────────────────────────────────────────
async def create_version(doc: dict) -> dict:
    now = _now()
    doc = {**doc, "created_at": now}
    result = await get_collection(_VERSIONS).insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_version(version_id: str) -> dict | None:
    return await get_collection(_VERSIONS).find_one({"_id": version_id})


async def list_versions(deal_id: str) -> list[dict]:
    """All versions for a deal, ordered by sequence (sorted in-process — ``seq`` is a
    JSONB field, not a sortable column)."""
    cursor = get_collection(_VERSIONS).find({"deal_id": deal_id})
    docs = await cursor.to_list(length=1000)
    return sorted(docs, key=lambda d: d.get("seq", 0))


async def set_version_state(version_id: str, state: str, extra: dict | None = None) -> dict | None:
    updates = {"state": state, **(extra or {})}
    return await get_collection(_VERSIONS).find_one_and_update(
        {"_id": version_id}, {"$set": updates}, return_document=True
    )


# ── responses ────────────────────────────────────────────────────────────────
async def create_response(doc: dict) -> dict:
    now = _now()
    doc = {**doc, "created_at": now}
    result = await get_collection(_RESPONSES).insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def list_responses_for_deal(deal_id: str) -> list[dict]:
    cursor = get_collection(_RESPONSES).find({"deal_id": deal_id})
    return await cursor.to_list(length=5000)


async def list_responses_for_version(version_id: str) -> list[dict]:
    cursor = get_collection(_RESPONSES).find({"version_id": version_id})
    return await cursor.to_list(length=1000)


# ── consents ─────────────────────────────────────────────────────────────────
async def create_consent(doc: dict) -> dict:
    now = _now()
    doc = {**doc, "created_at": now}
    result = await get_collection(_CONSENTS).insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def list_consents_for_deal(deal_id: str) -> list[dict]:
    cursor = get_collection(_CONSENTS).find({"deal_id": deal_id})
    return await cursor.to_list(length=1000)
