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
    (e.g. every cached persona of one participant type: ``persona:{type}:``).

    The prefix filter runs before the limit, not after. Applying the limit to the
    unfiltered read meant a type whose rows sat past the first `limit` documents
    came back empty: with thirty producers cached ahead of twenty buyers, a
    thirty-row read returned only producers, and Mode 1 showed no buyers at all.
    The cache is bounded by population size, so reading it whole is cheap.
    """
    docs = await get_collection(_CACHE).find({"kind": kind}).to_list(length=None)
    matching = [d["payload"] for d in docs if str(d.get("cache_key", "")).startswith(cache_key_prefix)]
    return matching[:limit]


async def clear(kind: str) -> None:
    # No delete_many on the document-store proxy; this cache is small (bounded by
    # population size), so a per-row loop is fine.
    docs = await get_collection(_CACHE).find({"kind": kind}).to_list(length=10_000)
    for d in docs:
        await get_collection(_CACHE).delete_one({"_id": d["_id"]})


# ── Scoring history ─────────────────────────────────────────────────────────
# The cache above holds only the latest result for a pairing. These two keep the
# history: one row per precompute run, and one per pairing scored in it, so a
# score can be read against what the same pairing scored a run ago.

_RUNS = "match_runs"
_LEDGER = "match_ledger"


async def record_run(run: dict[str, Any]) -> None:
    await get_collection(_RUNS).insert_one(run)


async def record_ledger_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        await get_collection(_LEDGER).insert_one(row)


async def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    docs = await get_collection(_RUNS).find({}).to_list(length=None)
    docs.sort(key=lambda d: str(d.get("started_at", "")), reverse=True)
    return docs[:limit]


async def ledger_for(participant_type: str, profile_id: str, limit: int = 50) -> list[dict[str, Any]]:
    docs = await get_collection(_LEDGER).find({"participant_type": participant_type}).to_list(length=None)
    rows = [d for d in docs if str(d.get("profile_id")) == str(profile_id)]
    rows.sort(key=lambda d: (str(d.get("scored_at", "")), -float(d.get("score") or 0)), reverse=True)
    return rows[:limit]
