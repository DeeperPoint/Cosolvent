"""Incremental ingestion: upsert unchanged chunks instead of rewriting them.

Re-loading a document used to delete every chunk it owned and re-insert the lot,
which made the unique constraint on (source_doc_id, chunk_text_hash) unreachable
— nothing could collide with rows that had just been deleted. These tests pin the
replacement: unchanged chunks update in place, genuinely removed chunks go, and
the hash used to decide which is which is the same one the database computes.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.db_schema import reference_library
from app.modules.knowledge import service

DOC = "doc-1"
DOC_UUID = service.coerce_doc_id(DOC)


def _record(text: str) -> dict:
    return {
        "source_doc_id": DOC,
        "vertical": "grain",
        "chunk_text": text,
        "embedding": [0.1] * 1536,
        "metadata": {"topic": "payment_terms"},
    }


def _existing(*texts: str):
    """Rows the database already holds, keyed the way the generated column keys them."""
    return [
        SimpleNamespace(
            source_doc_id=DOC_UUID,
            chunk_text_hash=hashlib.md5(t.encode("utf-8")).hexdigest(),
        )
        for t in texts
    ]


class _Session:
    def __init__(self, existing):
        self._existing = existing
        self.statements = []
        self.commit = AsyncMock()

    async def execute(self, stmt):
        self.statements.append(stmt)
        # The first statement is the lookup of what is already stored.
        if len(self.statements) == 1:
            return SimpleNamespace(all=lambda: self._existing)
        return SimpleNamespace()


@pytest.fixture
def run(monkeypatch):
    def _run(records, existing):
        session = _Session(existing)

        class _Scope:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(service, "session_scope", lambda: _Scope())
        return session

    return _run


def _kinds(session) -> list[str]:
    return [type(s).__name__ for s in session.statements]


# ── The hash contract ────────────────────────────────────────────────────────
def test_the_hash_matches_the_generated_column():
    """chunk_text_hash is `md5(chunk_text)` computed by Postgres on the raw bytes.

    If the Python side ever disagrees — a different algorithm, or encoding the
    text differently — every row looks new, the upsert quietly degrades into the
    delete-and-reinsert it replaced, and the only visible symptom is the bill.

    The expected digest below is not computed here, which would make this test
    compare md5 with itself and prove nothing. It is the literal output of
    `SELECT md5('Grade A — 13.5% protein, Ti-6Al-4V')` on Postgres 16. The em-dash
    and the alloy designation are the point: a latin-1 or utf-16 encoding on the
    Python side still produces 32 valid-looking hex characters, just not these.
    """
    text = "Grade A — 13.5% protein, Ti-6Al-4V"
    postgres_md5 = "b99a929cfe0a1ae62b70c47712730e12"
    assert hashlib.md5(text.encode("utf-8")).hexdigest() == postgres_md5


# ── Counting ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_a_fresh_document_is_all_inserts(run):
    run([], [])
    result = await service.load_reference_records([_record("a"), _record("b")])
    assert result["inserted"] == 2
    assert result["updated"] == 0
    assert result["deleted"] == 0
    assert result["loaded"] == 2


@pytest.mark.asyncio
async def test_an_unchanged_reload_updates_in_place_and_deletes_nothing(run):
    """The case the cache exists for: re-ingesting a document nobody edited."""
    run([], _existing("a", "b"))
    result = await service.load_reference_records([_record("a"), _record("b")])
    assert result["updated"] == 2
    assert result["inserted"] == 0
    assert result["deleted"] == 0


@pytest.mark.asyncio
async def test_a_one_chunk_edit_touches_only_that_chunk(run):
    """A single edited paragraph must not rewrite the other chunks of the page."""
    run([], _existing("a", "b", "c"))
    result = await service.load_reference_records(
        [_record("a"), _record("b"), _record("c EDITED")]
    )
    assert result["updated"] == 2, "a and b are unchanged"
    assert result["inserted"] == 1, "the edited chunk is new text"
    assert result["deleted"] == 1, "the old text of c is gone"


@pytest.mark.asyncio
async def test_a_shrinking_document_drops_its_removed_chunks(run):
    """Otherwise the library keeps answering from a version of the page that no
    longer exists."""
    run([], _existing("a", "b", "c"))
    result = await service.load_reference_records([_record("a")])
    assert result["deleted"] == 2
    assert result["updated"] == 1


@pytest.mark.asyncio
async def test_nothing_is_deleted_when_nothing_is_stale(run):
    session = run([], _existing("a"))
    await service.load_reference_records([_record("a")])
    assert "Delete" not in _kinds(session), "no DELETE should be issued"


@pytest.mark.asyncio
async def test_a_delete_is_issued_when_something_is_stale(run):
    session = run([], _existing("a", "gone"))
    await service.load_reference_records([_record("a")])
    assert "Delete" in _kinds(session)


@pytest.mark.asyncio
async def test_malformed_records_are_skipped_not_fatal(run):
    run([], [])
    result = await service.load_reference_records(
        [_record("a"), {"source_doc_id": DOC, "vertical": "grain"}]
    )
    assert result["skipped"] == 1
    assert result["loaded"] == 1


@pytest.mark.asyncio
async def test_an_empty_batch_reports_zeroes_without_touching_the_database(run):
    session = run([], [])
    result = await service.load_reference_records([])
    assert result == {"loaded": 0, "documents": 0, "skipped": 0,
                      "inserted": 0, "updated": 0, "deleted": 0}
    assert session.statements == []


# ── The statement itself ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_the_write_is_an_upsert_on_the_existing_constraint(run):
    session = run([], _existing("a"))
    await service.load_reference_records([_record("a")])

    write = session.statements[-1]
    sql = str(write.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_reference_library_doc_chunk" in sql
    assert "DO UPDATE" in sql
    # chunk_text is the conflict target and cannot have changed; what is refreshed
    # is everything derived from it or stored beside it.
    assert "embedding" in sql and "reference_metadata" in sql


@pytest.mark.asyncio
async def test_the_stale_delete_is_scoped_to_document_and_hash_pairs(run):
    """Scoped by pair, not by document: deleting by source_doc_id alone is the
    delete-everything behaviour this replaced."""
    session = run([], _existing("a", "gone"))
    await service.load_reference_records([_record("a")])

    deletes = [s for s in session.statements if type(s).__name__ == "Delete"]
    sql = str(deletes[0].compile(dialect=postgresql.dialect()))
    assert "chunk_text_hash" in sql
    assert "source_doc_id" in sql
