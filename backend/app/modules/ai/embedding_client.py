"""Centralized embedding abstraction for multi-provider support."""

from __future__ import annotations

import logging

from app.core.exceptions import ServiceUnavailableError
from app.modules.ai import repository as repo
from app.modules.ai.client_factory import get_embedding_client

logger = logging.getLogger("cosolvent.embeddings")


async def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text."""
    config = await repo.get_embedding_config()
    provider = config["provider"]
    model = config["model"]

    client = get_embedding_client(provider)

    try:
        resp = await client.embeddings.create(input=text, model=model)
        return resp.data[0].embedding
    except Exception as exc:
        logger.error("Embedding failed (provider=%s, model=%s)", provider, model, exc_info=True)
        raise ServiceUnavailableError("AI service unavailable: embedding generation failed") from exc


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embedding vectors for a batch of texts."""
    config = await repo.get_embedding_config()
    provider = config["provider"]
    model = config["model"]

    client = get_embedding_client(provider)

    try:
        resp = await client.embeddings.create(input=texts, model=model)
        return [item.embedding for item in resp.data]
    except Exception as exc:
        logger.error("Batch embedding failed (provider=%s, model=%s)", provider, model, exc_info=True)
        raise ServiceUnavailableError("AI service unavailable: batch embedding generation failed") from exc
