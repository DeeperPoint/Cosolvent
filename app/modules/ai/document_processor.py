"""Document processing for RAG knowledge base ingestion."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, insert

from app.core.database import session_scope
from app.core.db_schema import ai_document_chunks
from app.modules.ai import repository as repo
from app.modules.ai.embedding_client import get_embedding

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
    """Process a queued document: chunk, embed, index to Postgres vectors."""
    doc = await repo.get_document(doc_id)
    if not doc or doc["status"] != "QUEUED":
        return

    await repo.update_document_status(doc_id, "PROCESSING")

    try:
        text = doc.get("content", "")
        chunks = chunk_text(text)

        document_uuid = uuid.UUID(doc_id)

        async with session_scope() as session:
            await session.execute(
                delete(ai_document_chunks).where(ai_document_chunks.c.document_id == document_uuid)
            )

            batch_rows = []
            for i, chunk in enumerate(chunks):
                embedding = await get_embedding(chunk)
                batch_rows.append(
                    {
                        "document_id": document_uuid,
                        "chunk_index": i,
                        "chunk_text": chunk,
                        "embedding": embedding,
                        "chunk_metadata": {
                            "source": "document",
                            "doc_id": doc_id,
                            "filename": doc["filename"],
                            "chunk_index": i,
                            "text": chunk[:500],
                        },
                    }
                )

            if batch_rows:
                await session.execute(insert(ai_document_chunks), batch_rows)
            await session.commit()

        await repo.update_document_status(doc_id, "INDEXED", chunk_count=len(chunks))
        logger.info("Processed document %s: %d chunks", doc_id, len(chunks))

    except Exception:
        logger.error("Failed to process document %s", doc_id, exc_info=True)
        await repo.update_document_status(doc_id, "FAILED")
