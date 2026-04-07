from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.core.db_schema import ai_document_chunks, profile_vectors


def test_ai_document_chunks_has_foreign_key():
    targets = {fk.target_fullname for fk in ai_document_chunks.c.document_id.foreign_keys}
    assert "ai_documents.id" in targets


def test_ai_document_chunks_has_unique_document_chunk_constraint():
    unique_names = {
        c.name for c in ai_document_chunks.constraints if isinstance(c, UniqueConstraint) and c.name
    }
    assert "uq_ai_document_chunks_document_chunk" in unique_names


def test_profile_vectors_has_foreign_key():
    targets = {fk.target_fullname for fk in profile_vectors.c.profile_id.foreign_keys}
    assert "profiles.id" in targets
