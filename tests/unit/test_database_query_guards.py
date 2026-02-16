from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import CollectionProxy


def _collection(name: str = "users") -> CollectionProxy:
    with patch("app.core.database.get_db", return_value=object()):
        return CollectionProxy(name)


@pytest.mark.asyncio
async def test_find_docs_rejects_unsupported_query_operator():
    collection = _collection()
    with pytest.raises(ValueError, match="Unsupported query"):
        await collection._find_docs({"created_at": {"$gt": "2025-01-01"}}, None, [], 0, 10)


@pytest.mark.asyncio
async def test_find_docs_rejects_unsupported_sort_field():
    collection = _collection()
    with pytest.raises(ValueError, match="Unsupported sort fields"):
        await collection._find_docs({}, None, [("", 1)], 0, 10)


@pytest.mark.asyncio
async def test_find_one_for_update_uses_row_lock():
    collection = _collection()
    session = AsyncMock()
    result = type("Result", (), {"first": lambda self: None})()
    session.execute = AsyncMock(return_value=result)

    await collection._find_one_for_update(session, {"_id": "abc-123"})

    statement = session.execute.await_args.args[0]
    assert statement._for_update_arg is not None


def test_upsert_lock_key_is_stable_for_key_ordering():
    collection = _collection("drafts")
    left = {"user_id": "u1", "status": {"$ne": "closed"}}
    right = {"status": {"$ne": "closed"}, "user_id": "u1"}
    assert collection._upsert_lock_key(left) == collection._upsert_lock_key(right)
