"""Background task: process and index documents for RAG."""

from __future__ import annotations

import logging

logger = logging.getLogger("cosolvent.worker.docindex")


async def process_document_task(ctx: dict, doc_id: str) -> None:
    from app.modules.ai.document_processor import process_document
    logger.info("Processing document %s", doc_id)
    await process_document(doc_id)
