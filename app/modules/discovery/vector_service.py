"""Pinecone vector search operations."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("cosolvent.vector")

_index = None


def _get_index():
    global _index
    if _index is None:
        if not settings.pinecone_api_key:
            return None
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        _index = pc.Index(settings.pinecone_index)
    return _index


async def upsert_profile_vector(
    profile_id: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> None:
    index = _get_index()
    if not index:
        logger.warning("Pinecone not configured, skipping upsert")
        return
    index.upsert(vectors=[(profile_id, embedding, metadata)])


async def search_vectors(
    query_embedding: list[float],
    top_k: int = 20,
    filter_dict: dict | None = None,
) -> list[dict[str, Any]]:
    index = _get_index()
    if not index:
        return []
    kwargs: dict[str, Any] = {
        "vector": query_embedding,
        "top_k": top_k,
        "include_metadata": True,
    }
    if filter_dict:
        kwargs["filter"] = filter_dict
    result = index.query(**kwargs)
    return [
        {"id": m.id, "score": m.score, "metadata": m.metadata}
        for m in result.matches
    ]


async def delete_profile_vector(profile_id: str) -> None:
    index = _get_index()
    if not index:
        return
    index.delete(ids=[profile_id])
