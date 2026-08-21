"""Persistence for the pre-computed showcase cache.

One row per (kind, cache_key) — ``kind`` distinguishes what's cached ("persona",
"matches", "qa"); ``cache_key`` scopes it (a participant type, a profile id, ...).
Upserted in place so re-running precompute replaces stale entries rather than
accumulating duplicates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import get_collection

_CACHE = "showcase_cache"


async def upsert(kind: str, cache_key: str, payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    existing = await get_collection(_CACHE).find_one({"kind": kind, "cache_key": cache_key})
    doc = {"kind": kind, "cache_key": cache_key, "payload": payload, "updated_at": now}
    if existing:
        await get_collection(_CACHE).update_one({"_id": existing["_id"]}, {"$set": doc})
    else:
        doc["created_at"] = now
        await get_collection(_CACHE).insert_one(doc)


async def get(kind: str, cache_key: str) -> dict[str, Any] | None:
    doc = await get_collection(_CACHE).find_one({"kind": kind, "cache_key": cache_key})
    return doc.get("payload") if doc else None


async def list_by_kind_prefix(kind: str, cache_key_prefix: str, limit: int = 200) -> list[dict[str, Any]]:
    """All payloads for ``kind`` whose cache_key starts with ``cache_key_prefix``
    (e.g. every cached persona of one participant type: ``persona:{type}:``)."""
    docs = await get_collection(_CACHE).find({"kind": kind}).to_list(length=limit)
    return [d["payload"] for d in docs if str(d.get("cache_key", "")).startswith(cache_key_prefix)]


async def clear(kind: str) -> None:
    # No delete_many on the document-store proxy; this cache is small (bounded by
    # population size), so a per-row loop is fine.
    docs = await get_collection(_CACHE).find({"kind": kind}).to_list(length=10_000)
    for d in docs:
        await get_collection(_CACHE).delete_one({"_id": d["_id"]})
