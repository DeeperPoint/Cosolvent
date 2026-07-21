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

IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


async def extract_text_from_image(base64_content: str, content_type: str) -> str:
    """Use multimodal model to extract text from an image document."""
    from app.modules.ai.client_factory import get_chat_client

    cfg = await repo.get_multimodal_config()
    if not cfg["enabled"]:
        return ""

    client = get_chat_client(cfg["provider"])
    try:
        response = await client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all text from this image. Return only the extracted text."},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{base64_content}"}},
                ],
            }],
            max_tokens=cfg["max_tokens"],
        )
        return response.choices[0].message.content or ""
    except Exception:
        logger.error("Multimodal image extraction failed", exc_info=True)
        return ""


async def process_document(doc_id: str) -> None:
    """Process a queued document: chunk, embed, index to Postgres vectors."""
    doc = await repo.get_document(doc_id)
    if not doc or doc["status"] != "QUEUED":
        return

    await repo.update_document_status(doc_id, "PROCESSING")

    try:
        content_type = doc.get("content_type", "text/plain")
        if content_type in IMAGE_MIME_TYPES:
            text = await extract_text_from_image(doc.get("content", ""), content_type)
        else:
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

        # Also feed the curated knowledge base ("LLM wiki") so admin uploads are answerable
        # through Knowledge Q&A, which reads exclusively from the reference library. Reuse the
        # embeddings already computed above. Idempotent per source_doc_id.
        if batch_rows:
            await _feed_reference_library(doc_id, doc, batch_rows)

        await repo.update_document_status(doc_id, "INDEXED", chunk_count=len(chunks))
        logger.info("Processed document %s: %d chunks", doc_id, len(chunks))

    except Exception:
        logger.error("Failed to process document %s", doc_id, exc_info=True)
        await repo.update_document_status(doc_id, "FAILED")


async def _feed_reference_library(doc_id: str, doc: dict, batch_rows: list[dict]) -> None:
    """Load an admin-uploaded document's chunks into the reference library (the wiki) so
    Knowledge Q&A can answer from them. Tagged source_layer='wiki' for ranking preference."""
    try:
        from app.core.marketplace_config import get_marketplace_config
        from app.modules.knowledge import load_reference_records

        try:
            vertical = getattr(getattr(get_marketplace_config(), "marketplace", None), "name", None)
        except Exception:
            vertical = None
        vertical = vertical or "default"

        records = [
            {
                "source_doc_id": doc_id,
                "vertical": vertical,
                "chunk_text": row["chunk_text"],
                "embedding": row["embedding"],
                "metadata": {
                    "source_layer": "wiki",
                    "source": "admin_upload",
                    "filename": doc.get("filename"),
                    "doc_id": doc_id,
                    "chunk_index": row["chunk_index"],
                },
            }
            for row in batch_rows
        ]
        result = await load_reference_records(records, default_vertical=vertical)
        logger.info("Fed document %s into reference library: %s", doc_id, result)
    except Exception:
        # Non-fatal: the document is still indexed in ai_document_chunks even if wiki feed fails.
        logger.error("Failed to feed document %s into reference library", doc_id, exc_info=True)
