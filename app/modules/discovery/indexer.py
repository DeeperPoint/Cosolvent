"""Profile → vector indexing using OpenAI embeddings + pgvector."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.marketplace_config import MarketplaceConfig
from app.modules.discovery.vector_service import upsert_profile_vector

logger = logging.getLogger("cosolvent.indexer")


async def index_profile(
    profile: dict[str, Any],
    config: MarketplaceConfig,
) -> None:
    """Generate embedding for a profile and upsert to Postgres vectors."""
    if not settings.openai_api_key:
        logger.warning("OpenAI not configured, skipping profile indexing")
        return

    type_slug = profile.get("participant_type", "")
    schema = config.profile_schemas.get(type_slug)
    if not schema:
        return

    # Build text from searchable fields
    searchable = [f for f in schema.all_fields if f.searchable]
    fields = profile.get("fields", {})
    text_parts = []
    for f in searchable:
        val = fields.get(f.name)
        if val is not None:
            if isinstance(val, list):
                text_parts.append(f"{f.label}: {', '.join(str(v) for v in val)}")
            else:
                text_parts.append(f"{f.label}: {val}")

    if profile.get("ai_profile"):
        text_parts.append(profile["ai_profile"])

    text = "\n".join(text_parts)
    if not text.strip():
        return

    embedding = await _get_embedding(text)

    metadata = {"participant_type": type_slug}
    for f in searchable:
        val = fields.get(f.name)
        if val is not None:
            metadata[f.name] = val

    profile_id = str(profile.get("_id", profile.get("id", "")))
    await upsert_profile_vector(profile_id, embedding, metadata)
    logger.info("Indexed profile %s", profile_id)


async def _get_embedding(text: str) -> list[float]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return resp.data[0].embedding
