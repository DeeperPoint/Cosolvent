"""Document processing for RAG knowledge base ingestion."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.modules.ai import repository as repo

logger = logging.getLogger("cosolvent.docproc")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


async def process_document(doc_id: str) -> None:
    """Process a queued document: chunk, embed, index to Pinecone."""
    doc = await repo.get_document(doc_id)
    if not doc or doc["status"] != "QUEUED":
        return

    await repo.update_document_status(doc_id, "PROCESSING")

    try:
        text = doc.get("content", "")
        chunks = chunk_text(text)

        if not settings.openai_api_key or not settings.pinecone_api_key:
            logger.warning("API keys not configured, marking as indexed without vectors")
            await repo.update_document_status(doc_id, "INDEXED", chunk_count=len(chunks))
            return

        from openai import AsyncOpenAI
        from app.modules.discovery.vector_service import _get_index

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        index = _get_index()

        vectors = []
        for i, chunk in enumerate(chunks):
            resp = await client.embeddings.create(input=chunk, model="text-embedding-3-small")
            embedding = resp.data[0].embedding
            vector_id = f"doc_{doc_id}_chunk_{i}"
            vectors.append((vector_id, embedding, {
                "source": "document",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "chunk_index": i,
                "text": chunk[:500],
            }))

        if index and vectors:
            # Batch upsert
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                index.upsert(vectors=vectors[i:i + batch_size])

        await repo.update_document_status(doc_id, "INDEXED", chunk_count=len(chunks))
        logger.info("Processed document %s: %d chunks", doc_id, len(chunks))

    except Exception:
        logger.error("Failed to process document %s", doc_id, exc_info=True)
        await repo.update_document_status(doc_id, "FAILED")
