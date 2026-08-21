"""Fix reference_library's unique constraint: hash chunk_text instead of indexing it
directly.

``UNIQUE (source_doc_id, chunk_text)`` indexes the full chunk text via a btree,
which has a hard per-row size limit (~2704 bytes at the default 8KB page size).
Ordinary prose-length chunks (a converted Wikipedia section, a standards-body
overview page — anything beyond a short synthetic sample) routinely exceed that,
so inserting real reference content fails with
``index row size ... exceeds btree version 4 maximum ...``. This was never caught
by the fixture data used elsewhere in the pipeline, which happened to stay under
the limit; it surfaced the first time this table was loaded with real long-form
content.

Fix: dedup on ``md5(chunk_text)`` (a server-computed, fixed-size generated column)
instead of the raw text. Same dedup semantics — identical chunk_text still
collides — without a size-dependent index.

Revision ID: reference_library_chunk_hash_0001
Revises: reference_library_table_0001
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "reference_library_chunk_hash_0001"
down_revision = "reference_library_table_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE reference_library "
        "ADD COLUMN IF NOT EXISTS chunk_text_hash TEXT GENERATED ALWAYS AS (md5(chunk_text)) STORED"
    )
    op.execute("ALTER TABLE reference_library DROP CONSTRAINT IF EXISTS uq_reference_library_doc_chunk")
    op.execute(
        "ALTER TABLE reference_library "
        "ADD CONSTRAINT uq_reference_library_doc_chunk UNIQUE (source_doc_id, chunk_text_hash)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE reference_library DROP CONSTRAINT IF EXISTS uq_reference_library_doc_chunk")
    op.execute(
        "ALTER TABLE reference_library "
        "ADD CONSTRAINT uq_reference_library_doc_chunk UNIQUE (source_doc_id, chunk_text)"
    )
    op.execute("ALTER TABLE reference_library DROP COLUMN IF EXISTS chunk_text_hash")
