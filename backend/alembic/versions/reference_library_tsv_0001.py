"""Add a full-text index to reference_library, so retrieval is not semantic only.

The reference corpus is an adverse case for pure vector search. Its discriminating
tokens are contract numbers, grade codes, standard references and measured
thresholds — "GAFTA 48", "AS9100D", "Ti-6Al-4V", "17-4 PH", "0.0005 in" — terms
whose exact form carries the meaning. An embedding places "AS9100D" and "AS9102"
close together because they are near-identical strings about aerospace quality
systems; a buyer who needs one and is shown the other has been given the wrong
answer, confidently.

This adds the lexical half. `chunk_tsv` is a stored generated column so every
writer gets it without knowing it exists — the same reason chunk_text_hash is
generated rather than supplied, and the same reason that choice survived contact
with three different ingestion paths.

The configuration is pinned to 'english' rather than left to default_text_search_config.
to_tsvector(text) with one argument is STABLE, not IMMUTABLE, because the session
GUC can change under it, and Postgres refuses it in a generated column. Naming the
configuration also means the index does not silently change meaning when a database
is restored somewhere with a different default.

Revision ID: reference_library_tsv
Revises: merge_heads_0003
Create Date: 2026-11-24
"""

from __future__ import annotations

from alembic import op

# Alembic stores this in alembic_version.version_num, a VARCHAR(32).
revision = "reference_library_tsv"
down_revision = "merge_heads_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE reference_library "
        "ADD COLUMN IF NOT EXISTS chunk_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED"
    )
    # GIN rather than GiST: the corpus is read far more than written, and the
    # chunks are long, which is where GIN's lookup advantage is largest.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reference_library_chunk_tsv "
        "ON reference_library USING GIN (chunk_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reference_library_chunk_tsv")
    op.execute("ALTER TABLE reference_library DROP COLUMN IF EXISTS chunk_tsv")
