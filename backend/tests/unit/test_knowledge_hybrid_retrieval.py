"""Hybrid retrieval: vector + lexical rankers fused by Reciprocal Rank Fusion.

The fusion arithmetic is tested directly against `_fuse`, and the query
construction against compiled SQL. Both matter for different reasons: the
arithmetic decides what a participant is shown, and the SQL decides whether the
lexical ranker can smuggle a filtered-out chunk back into the answer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.db_schema import reference_library
from app.modules.knowledge import service


def _row(row_id: str, score: float = 0.8, text: str = "chunk", meta: dict | None = None):
    return SimpleNamespace(
        id=row_id, chunk_text=text, reference_metadata=meta or {"source_layer": "wiki"}, score=score
    )


# ── The fusion arithmetic ────────────────────────────────────────────────────
def test_a_chunk_both_rankers_find_beats_one_only_either_finds():
    """The property that makes fusing worth doing at all."""
    both = _row("both")
    vector_only = _row("v")
    lexical_only = _row("l")

    fused = service._fuse([both, vector_only], [both, lexical_only], top_k=3)

    assert fused[0]["id"] == "both"
    assert fused[0]["vector_rank"] == 1
    assert fused[0]["lexical_rank"] == 1


def test_a_lexical_only_hit_reaches_the_answer_at_all():
    """The case the corpus argues for.

    An exact standard reference lands first lexically and outside the top 30 by
    embedding, because the embedding sees a near-identical neighbour as just as
    good. Vector-only retrieval with top_k=5 never shows it; fusion does.

    Note what is NOT asserted: that it comes first. Lexical rank 1 and vector
    rank 1 contribute identical RRF scores, so the exact hit ties with the best
    vector hit rather than beating it. That is RRF working as defined — neither
    ranker gets to decide the head of the list alone — and a test asserting
    otherwise would be pinning down a property the algorithm does not have.
    """
    vector_rows = [_row(f"v{i}") for i in range(1, 31)]
    exact = _row("AS9100D")
    fused = service._fuse(vector_rows, [exact], top_k=5)

    ids = [h["id"] for h in fused]
    assert "AS9100D" in ids, "a lexical-only hit must survive fusion"
    # It outranks every vector hit below first place.
    assert ids.index("AS9100D") <= ids.index("v2")

    exact_hit = next(h for h in fused if h["id"] == "AS9100D")
    assert exact_hit["vector_rank"] is None
    assert exact_hit["lexical_rank"] == 1


def test_rank_one_in_either_ranker_scores_the_same():
    """Stated explicitly because it is the property the test above leans on."""
    vector_first = service._fuse([_row("v")], [], top_k=1)[0]
    lexical_first = service._fuse([], [_row("l")], top_k=1)[0]
    assert vector_first["fused_score"] == pytest.approx(lexical_first["fused_score"])


def test_rrf_score_matches_the_definition():
    rows = [_row("a"), _row("b")]
    fused = service._fuse(rows, [], top_k=2)
    k = service.RRF_K
    assert fused[0]["fused_score"] == pytest.approx(1.0 / (k + 1))
    assert fused[1]["fused_score"] == pytest.approx(1.0 / (k + 2))


def test_ties_break_on_cosine_similarity_not_insertion_order():
    """Two chunks found by one ranker each, at the same rank, are otherwise
    ordered by whichever query happened to return first — an accident."""
    weak = _row("weak", score=0.10)
    strong = _row("strong", score=0.95)
    fused = service._fuse([weak], [strong], top_k=2)
    assert fused[0]["id"] == "strong"


def test_every_result_reports_how_it_was_found():
    fused = service._fuse([_row("a")], [_row("b")], top_k=2)
    for hit in fused:
        assert "fused_score" in hit
        assert "vector_rank" in hit and "lexical_rank" in hit


def test_fusion_respects_top_k():
    rows = [_row(f"r{i}") for i in range(20)]
    assert len(service._fuse(rows, rows, top_k=4)) == 4


def test_score_still_means_cosine_similarity():
    """Existing callers read `score`; fusion must not redefine it under them."""
    fused = service._fuse([_row("a", score=0.73)], [], top_k=1)
    assert fused[0]["score"] == pytest.approx(0.73)


# ── Candidate pool ───────────────────────────────────────────────────────────
def test_pool_is_wider_than_top_k_so_a_mid_ranked_chunk_can_fuse_in():
    assert service._candidate_pool(5) > 5


def test_pool_is_bounded():
    assert service._candidate_pool(10_000) == service._RRF_POOL_MAX


# ── Query construction ───────────────────────────────────────────────────────
def _compile(stmt, *, literals: bool = True) -> str:
    # The lexical statement cannot be rendered with literal binds: SQLAlchemy has
    # no literal renderer for REGCONFIG, the type of the 'english' argument to
    # websearch_to_tsquery. Compiling it with placeholders still shows the
    # function calls and operators these tests check for.
    kwargs = {"literal_binds": True} if literals else {}
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs=kwargs))


def test_both_rankers_are_scoped_by_the_same_filters():
    """If the lexical side skipped a filter, an excluded chunk could be fused
    back in on its lexical rank alone — quietly defeating the participant-safe
    exclusions that keep demo-invented material out of answers."""
    filters = {"evidence_class": {"not": ["demo_invented"]}}
    sql = _compile(service._scoped(select(reference_library.c.id), "grain", filters))
    assert "NOT IN" in sql.upper()
    assert "'demo_invented'" in sql
    assert "vertical" in sql


@pytest.mark.asyncio
async def test_without_query_text_retrieval_degrades_to_vector_only(monkeypatch):
    """A caller holding only an embedding gets the old behaviour, not an error."""
    executed = []

    class _Session:
        async def execute(self, stmt):
            executed.append(stmt)
            return SimpleNamespace(all=lambda: [_row("a")])

    class _Scope:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(service, "session_scope", lambda: _Scope())
    hits = await service.search_reference_library([0.0] * 1536, top_k=3)

    assert len(executed) == 1, "no lexical query should be issued"
    assert hits[0]["id"] == "a"
    assert "fused_score" not in hits[0]


@pytest.mark.asyncio
async def test_a_blank_query_string_does_not_issue_a_lexical_query(monkeypatch):
    executed = []

    class _Session:
        async def execute(self, stmt):
            executed.append(stmt)
            return SimpleNamespace(all=lambda: [])

    class _Scope:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(service, "session_scope", lambda: _Scope())
    await service.search_reference_library([0.0] * 1536, query_text="   ", top_k=3)
    assert len(executed) == 1


@pytest.mark.asyncio
async def test_with_query_text_both_rankers_run(monkeypatch):
    executed = []

    class _Session:
        async def execute(self, stmt):
            executed.append(_compile(stmt, literals=False))
            return SimpleNamespace(all=lambda: [_row("a")])

    class _Scope:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(service, "session_scope", lambda: _Scope())
    hits = await service.search_reference_library(
        [0.0] * 1536, query_text="GAFTA 48 weighing", top_k=3
    )

    assert len(executed) == 2
    lexical_sql = executed[1]
    assert "websearch_to_tsquery" in lexical_sql
    assert "ts_rank_cd" in lexical_sql
    assert "@@" in lexical_sql
    assert hits[0]["fused_score"] > 0


@pytest.mark.asyncio
async def test_ask_feeds_the_question_to_the_lexical_ranker(monkeypatch):
    """Without this wiring the index exists and nothing ever queries it."""
    from unittest.mock import AsyncMock, patch

    search = AsyncMock(return_value=[])
    with patch.object(service, "get_embedding", new=AsyncMock(return_value=[0.0] * 1536)), \
         patch.object(service, "search_reference_library", new=search), \
         patch.object(service, "_record_gap", new=AsyncMock()):
        await service.ask(query="what does GAFTA 48 say about weighing?", vertical="grain")

    assert search.await_args.kwargs["query_text"] == "what does GAFTA 48 say about weighing?"
