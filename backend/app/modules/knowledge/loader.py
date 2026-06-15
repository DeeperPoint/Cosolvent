"""Adapter: KnowledgeSlot ``*_processed.jsonl`` -> reference-library documents.

The upstream pipeline emits one JSON object per line, each a chunk with
``chunk_id``, ``content``, ``contextual_content``, ``metadata`` and a
precomputed ``embedding``. This groups those flat chunk records back into
parent documents so they can be ingested into the two-table model.

`parse_records` is pure (no I/O) so it is unit-testable without a database.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from app.modules.knowledge.schemas import ReferenceChunkInput, ReferenceDocumentInput

logger = logging.getLogger("cosolvent.knowledge")

# Chunk-level metadata key that must NOT be promoted to the document level.
_CHUNK_ONLY_KEYS = {"topic"}


def _doc_key_for(record: dict[str, Any]) -> str:
    """Derive a stable document key for a chunk record.

    Prefers the ``source_document`` filename (minus extension); falls back to
    stripping the trailing ``_<index>`` from the chunk_id (e.g. ``27_2025_0`` ->
    ``27_2025``).
    """
    src = (record.get("metadata") or {}).get("source_document")
    if src:
        return Path(str(src)).stem
    chunk_id = str(record.get("chunk_id", ""))
    head, _, tail = chunk_id.rpartition("_")
    return head if head and tail.isdigit() else chunk_id


def _doc_metadata_from(chunk_meta: dict[str, Any]) -> dict[str, Any]:
    """Extract the document-level fields from a chunk's metadata."""
    return {k: v for k, v in chunk_meta.items() if k not in _CHUNK_ONLY_KEYS}


def parse_records(records: Iterable[dict[str, Any]], vertical: str = "default") -> list[ReferenceDocumentInput]:
    """Group flat chunk records into ReferenceDocumentInput objects (order-stable)."""
    docs: dict[str, ReferenceDocumentInput] = {}

    for record in records:
        doc_key = _doc_key_for(record)
        meta = record.get("metadata") or {}

        if doc_key not in docs:
            docs[doc_key] = ReferenceDocumentInput(
                doc_key=doc_key,
                vertical=vertical,
                title=meta.get("title"),
                source_document=meta.get("source_document") or f"{doc_key}.md",
                source_url=meta.get("source_url"),
                doc_metadata=_doc_metadata_from(meta),
                chunks=[],
            )

        docs[doc_key].chunks.append(
            ReferenceChunkInput(
                chunk_id=record["chunk_id"],
                content=record["content"],
                contextual_content=record["contextual_content"],
                metadata=meta,
                embedding=record.get("embedding"),
            )
        )

    return list(docs.values())


def parse_jsonl_text(text: str, vertical: str = "default") -> list[ReferenceDocumentInput]:
    """Parse newline-delimited JSON (skipping blank lines) into documents."""
    records = [json.loads(line) for line in text.splitlines() if line.strip()]
    return parse_records(records, vertical)


def load_paths(paths: list[Path], vertical: str = "default") -> list[ReferenceDocumentInput]:
    """Read one or more ``.jsonl`` files (or directories of them) into documents."""
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.glob("*.jsonl")))
        else:
            files.append(p)

    all_records: list[dict[str, Any]] = []
    for f in files:
        all_records.extend(
            json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        logger.info("Parsed reference chunks from %s", f)
    return parse_records(all_records, vertical)
