"""The retrieval metrics, and the fixture's deterministic embeddings.

These run without a database. The integration test measures the system; this
measures the ruler, which has to be right first — a metric that silently
mis-defines recall turns every later comparison into a confident wrong number.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.knowledge.evaluation import (
    EMBEDDING_DIMENSIONS,
    QueryResult,
    cluster_embedding,
    compare,
    evaluate,
    query_embedding,
    recall_at_k,
    reciprocal_rank,
)

GOLDEN_SET_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "retrieval_golden_set.json"


def _result(query_id, retrieved, expected):
    return QueryResult(query_id=query_id, query="q", retrieved=retrieved, expected=expected)


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


# ── Metrics ──────────────────────────────────────────────────────────────────
def test_recall_counts_only_the_first_k():
    assert recall_at_k(["a", "b", "c"], ["c"], k=3) == 1.0
    assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0


def test_recall_is_a_fraction_of_what_was_wanted():
    assert recall_at_k(["a", "x"], ["a", "b"], k=5) == 0.5


def test_recall_of_nothing_wanted_is_one():
    assert recall_at_k(["a"], [], k=5) == 1.0


def test_reciprocal_rank_uses_the_first_hit():
    assert reciprocal_rank(["a", "b"], ["a"]) == 1.0
    assert reciprocal_rank(["x", "a"], ["a"]) == 0.5
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_reciprocal_rank_ignores_later_hits():
    """It answers "how far must a reader look", so only the first one counts."""
    assert reciprocal_rank(["x", "a", "b"], ["a", "b"]) == 0.5


def test_report_averages_across_queries():
    report = evaluate("r", [_result("1", ["a"], ["a"]), _result("2", ["x"], ["a"])])
    assert report.mrr == 0.5
    assert report.recall_at(1) == 0.5


def test_report_names_the_queries_that_returned_nothing_useful():
    """An average moving from 0.74 to 0.71 says nothing about which question a
    participant can no longer get an answer to."""
    report = evaluate("r", [_result("good", ["a"], ["a"]), _result("bad", ["x"], ["a"])])
    assert [m.query_id for m in report.misses] == ["bad"]


def test_an_empty_report_does_not_divide_by_zero():
    report = evaluate("r", [])
    assert report.mrr == 0.0
    assert report.recall_at(5) == 0.0


# ── Comparison ───────────────────────────────────────────────────────────────
def test_compare_reports_a_regression_even_when_the_mean_improves():
    """The reason compare() exists.

    A change that lifts the average while breaking a query that previously
    worked is not an improvement to ship silently, and the mean hides it.
    """
    # Two queries move from 5th place to 1st (+0.8 each); one stops returning
    # its answer at all (-1.0). The mean rises; a participant who could get an
    # answer to the third question no longer can.
    far = ["x", "x", "x", "x", "a"]
    baseline = evaluate("before", [
        _result("lifted_a", far, ["a"]),
        _result("lifted_b", far, ["a"]),
        _result("broken", ["a"], ["a"]),
    ])
    candidate = evaluate("after", [
        _result("lifted_a", ["a"], ["a"]),
        _result("lifted_b", ["a"], ["a"]),
        _result("broken", ["x"], ["a"]),
    ])
    delta = compare(baseline, candidate)

    assert delta["mrr_delta"] > 0, "the mean improved"
    assert delta["regressions"] == ["broken"], "and a query broke"


def test_compare_reports_what_was_fixed():
    baseline = evaluate("before", [_result("q", ["x"], ["a"])])
    candidate = evaluate("after", [_result("q", ["a"], ["a"])])
    assert compare(baseline, candidate)["fixed"] == ["q"]


# ── Deterministic embeddings ─────────────────────────────────────────────────
def test_embeddings_are_the_right_shape_and_deterministic():
    first = cluster_embedding("aerospace_quality", "as9100d_scope")
    second = cluster_embedding("aerospace_quality", "as9100d_scope")
    assert len(first) == EMBEDDING_DIMENSIONS
    assert first == second, "the same inputs must give the same vector on every run"


def test_members_of_a_cluster_are_closer_to_each_other_than_to_another_cluster():
    """The property the fixture rests on."""
    a = cluster_embedding("aerospace_quality", "as9100d_scope")
    b = cluster_embedding("aerospace_quality", "as9102_fai")
    far = cluster_embedding("payment_terms", "payment_against_documents")
    assert _cos(a, b) > _cos(a, far)


def test_a_cluster_is_tight_enough_to_be_adversarial():
    """If members drifted apart, the vector ranker would start solving the
    exact-term queries on its own and the golden set would stop measuring the
    problem it exists for."""
    a = cluster_embedding("aerospace_quality", "as9100d_scope")
    b = cluster_embedding("aerospace_quality", "as9102_fai")
    assert _cos(a, b) > 0.9


def test_a_query_can_be_aimed_at_the_wrong_neighbour_on_purpose():
    """The fixture states "the embedding's best guess is this wrong chunk"
    rather than hoping the vectors happen to land that way."""
    wrong = cluster_embedding("aerospace_quality", "as9102_fai")
    right = cluster_embedding("aerospace_quality", "as9100d_scope")
    q = query_embedding("aerospace_quality", "as9102_fai")
    assert _cos(q, wrong) > _cos(q, right)


def test_vectors_do_not_depend_on_global_random_state():
    import random

    random.seed(1)
    first = cluster_embedding("c", "m")
    random.seed(99999)
    assert cluster_embedding("c", "m") == first


# ── The fixture ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))


def test_every_expected_document_exists_in_the_corpus(golden):
    """A typo in an expected id would make a query permanently unanswerable and
    look like a retrieval failure forever."""
    corpus_ids = {entry["doc_id"] for entry in golden["corpus"]}
    for case in golden["queries"]:
        missing = set(case["expected"]) - corpus_ids
        assert not missing, f"query {case['id']} expects documents not in the corpus: {missing}"


def test_every_query_names_a_real_cluster(golden):
    clusters = set(golden["clusters"])
    for case in golden["queries"]:
        assert case["near_cluster"] in clusters, case["id"]


def test_the_adversarial_neighbour_is_a_different_document(golden):
    """Pointing a query at its own expected answer would make it trivially
    solvable by vector search and silently weaken the measurement."""
    for case in golden["queries"]:
        nearest = case.get("nearest_doc")
        if not nearest or not case["id"].startswith("exact_"):
            continue
        assert nearest not in case["expected"], (
            f"query {case['id']} is aimed at its own answer, so it tests nothing"
        )


def test_the_set_covers_both_kinds_of_query(golden):
    """Exact-term queries are what the lexical ranker is for; semantic ones are
    the control that keeps a lexical-only fix from passing."""
    ids = [case["id"] for case in golden["queries"]]
    assert any(i.startswith("exact_") for i in ids)
    assert any(i.startswith("semantic_") for i in ids)


def test_every_query_explains_itself(golden):
    """A golden set nobody can read stops being maintained, and a case nobody
    understands gets deleted the first time it fails."""
    for case in golden["queries"]:
        assert case.get("why"), f"query {case['id']} does not say what it is testing"
