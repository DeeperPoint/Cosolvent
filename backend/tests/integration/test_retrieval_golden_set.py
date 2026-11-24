"""Measure retrieval against a golden set, on a real database.

Against a real Postgres on purpose. The lexical half of retrieval is
`websearch_to_tsquery` and `ts_rank_cd` over a GIN index — reimplementing either
in Python to avoid the dependency would measure the imitation rather than the
system, and the whole value of a golden set is that it measures the system.

The corpus is seeded with deterministic embeddings built from named clusters, so
the run needs no embedding provider and gives the same numbers every time. The
clusters reproduce what makes this corpus hard: inside a cluster every chunk
looks alike to an embedding, and a single token — AS9100D against AS9102, GAFTA
48 against 49 — carries the whole difference.

Run with:
    RUN_INTEGRATION=1 pytest tests/integration/test_retrieval_golden_set.py -s
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.core.database import close_db, connect_db, session_scope
from app.core.db_schema import reference_library
from app.modules.knowledge import service
from app.modules.knowledge.evaluation import (
    QueryResult,
    cluster_embedding,
    compare,
    evaluate,
    query_embedding,
)
from tests.e2e.helpers import require_mode

GOLDEN_SET_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "retrieval_golden_set.json"
VERTICAL = "golden-set"

# Floors, not targets. They exist so a change that halves retrieval quality fails
# the build; they are deliberately below what the system currently scores, so
# ordinary variation does not make this test a nuisance that gets deleted.
MIN_HYBRID_MRR = 0.70
MIN_HYBRID_RECALL_AT_5 = 0.85


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))


# Function-scoped, not module-scoped. The connection pool binds to the event loop
# that opened it, and each test runs on its own loop, so a module-scoped
# connection is used from a loop it does not belong to — which surfaces as
# "attached to a different loop" and "Event loop is closed" rather than as
# anything resembling a retrieval problem. Reseeding twelve rows per test is
# cheap; debugging that is not.
@pytest.fixture
async def seeded(golden):
    """Load the fixture corpus, and remove it again afterwards."""
    require_mode("RUN_INTEGRATION")
    await connect_db()

    rows = []
    for entry in golden["corpus"]:
        rows.append({
            "id": uuid.uuid4(),
            "source_doc_id": service.coerce_doc_id(entry["doc_id"]),
            "vertical": VERTICAL,
            "chunk_text": entry["text"],
            "embedding": cluster_embedding(entry["cluster"], entry["doc_id"]),
            "reference_metadata": {
                "source_doc_id": entry["doc_id"],
                "source_layer": "wiki",
                "cluster": entry["cluster"],
            },
        })

    async with session_scope() as session:
        await session.execute(
            reference_library.delete().where(reference_library.c.vertical == VERTICAL)
        )
        await session.execute(reference_library.insert(), rows)
        await session.commit()

    yield golden

    async with session_scope() as session:
        await session.execute(
            reference_library.delete().where(reference_library.c.vertical == VERTICAL)
        )
        await session.commit()
    await close_db()


async def _run(golden: dict, *, lexical: bool, top_k: int = 5) -> list[QueryResult]:
    results = []
    for case in golden["queries"]:
        hits = await service.search_reference_library(
            query_embedding(case["near_cluster"], case.get("nearest_doc", "")),
            query_text=case["query"] if lexical else None,
            top_k=top_k,
            vertical=VERTICAL,
            lexical=lexical,
        )
        results.append(QueryResult(
            query_id=case["id"],
            query=case["query"],
            retrieved=[(h.get("metadata") or {}).get("source_doc_id", "") for h in hits],
            expected=case["expected"],
        ))
    return results


@pytest.mark.asyncio
async def test_hybrid_retrieval_beats_vector_only(seeded, capsys):
    """The headline claim, measured rather than asserted in a commit message."""
    baseline = evaluate("vector-only", await _run(seeded, lexical=False))
    candidate = evaluate("hybrid", await _run(seeded, lexical=True))
    delta = compare(baseline, candidate)

    with capsys.disabled():
        print()
        print(f"  {delta['baseline']}")
        print(f"  {delta['candidate']}")
        print(f"  MRR {delta['mrr_delta']:+.3f} · recall@5 {delta['recall_delta']:+.3f}")
        if delta["fixed"]:
            print(f"  newly answered: {', '.join(delta['fixed'])}")
        if delta["regressions"]:
            print(f"  REGRESSED: {', '.join(delta['regressions'])}")

    assert candidate.mrr > baseline.mrr, "hybrid retrieval must beat vector-only on this corpus"
    assert not delta["regressions"], (
        f"queries that worked before and do not now: {delta['regressions']}. "
        "A mean that improves while breaking a query is not an improvement to ship."
    )


@pytest.mark.asyncio
async def test_hybrid_retrieval_clears_the_floor(seeded):
    report = evaluate("hybrid", await _run(seeded, lexical=True))
    assert report.mrr >= MIN_HYBRID_MRR, report.summary()
    assert report.recall_at(5) >= MIN_HYBRID_RECALL_AT_5, report.summary()


@pytest.mark.asyncio
async def test_exact_term_queries_are_the_ones_that_improve(seeded):
    """Where the gain is supposed to come from.

    If hybrid improved the mean without improving the exact-term queries, the
    gain would be coming from somewhere unexplained and the explanation in the
    commit message would be wrong.
    """
    exact = [q for q in seeded["queries"] if q["id"].startswith("exact_")]
    subset = {**seeded, "queries": exact}

    baseline = evaluate("vector-only", await _run(subset, lexical=False))
    candidate = evaluate("hybrid", await _run(subset, lexical=True))

    assert candidate.recall_at(1) > baseline.recall_at(1), (
        f"exact-term recall@1 did not improve: {baseline.summary()} vs {candidate.summary()}"
    )


@pytest.mark.asyncio
async def test_semantic_queries_do_not_regress(seeded):
    """The control.

    Adding a lexical ranker must not cost the questions that share no tokens
    with their answer — those are the ones only the embedding can find.
    """
    semantic = [q for q in seeded["queries"] if q["id"].startswith("semantic_")]
    subset = {**seeded, "queries": semantic}

    baseline = evaluate("vector-only", await _run(subset, lexical=False))
    candidate = evaluate("hybrid", await _run(subset, lexical=True))

    assert candidate.mrr >= baseline.mrr, (
        f"semantic queries regressed: {baseline.summary()} vs {candidate.summary()}"
    )


@pytest.mark.asyncio
async def test_the_fixture_is_actually_adversarial(seeded):
    """Guards the measurement itself.

    If the deterministic embeddings drifted apart enough that vector-only solved
    the exact-term queries on its own, every test above would still pass and all
    of them would have stopped measuring anything. This fails instead.
    """
    exact = [q for q in seeded["queries"] if q["id"].startswith("exact_")]
    baseline = evaluate("vector-only", await _run({**seeded, "queries": exact}, lexical=False))
    assert baseline.recall_at(1) < 0.75, (
        "vector-only already solves the exact-term queries, so this golden set no "
        f"longer measures the problem it was built for: {baseline.summary()}"
    )
