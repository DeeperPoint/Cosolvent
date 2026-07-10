"""Deals repository: persistence for the deal document collection.

Deals are stored as JSONB documents (same document-table pattern as conversations),
accessed through the Mongo-style DatabaseProxy. ``party_user_ids`` is a flat array of
every user_id involved (principals + assigned facilitators) so listing a user's deals
is a single JSONB-containment query.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.database import get_collection

_COLLECTION = "deals"


async def create_deal(doc: dict) -> dict:
    now = datetime.now(timezone.utc)
    doc = {**doc, "created_at": now, "updated_at": now}
    result = await get_collection(_COLLECTION).insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_deal(deal_id: str) -> dict | None:
    return await get_collection(_COLLECTION).find_one({"_id": deal_id})


async def update_deal(deal_id: str, updates: dict) -> dict | None:
    updates = {**updates, "updated_at": datetime.now(timezone.utc)}
    return await get_collection(_COLLECTION).find_one_and_update(
        {"_id": deal_id},
        {"$set": updates},
        return_document=True,
    )


async def list_deals_for_user(user_id: str) -> list[dict]:
    # Query on the `participants` array-of-objects: the DB proxy special-cases this field
    # to a JSONB array-containment match (a scalar-in-array match under a key does NOT work).
    cursor = (
        get_collection(_COLLECTION)
        .find({"participants.user_id": user_id})
        .sort("updated_at", -1)
    )
    return await cursor.to_list(length=200)
