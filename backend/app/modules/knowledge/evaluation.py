"""Retrieval evaluation: recall@k and MRR over a golden set.

Without measurement no retrieval change is verifiable. A reranking tweak that
helps three queries and quietly breaks five looks exactly like one that helps all
eight — both are "an improvement to retrieval" in a commit message, and neither
reports a number. This module is the number.

It is deliberately free of any database or embedding provider: it scores a list
of returned document ids against a list of expected ones. That lets the same
metrics run over a live corpus in an integration test and over a fixture in a
unit test, which matters because the metric definitions are the part that must
not drift.

Deterministic embeddings for the fixture corpus live here too. A golden set that
needs an embedding API cannot run in CI, and one built on random vectors measures
noise. These are built from named clusters: chunks in a cluster sit close
together, and clusters sit far apart. That reproduces the property that makes
this corpus hard — the discriminating token is the only thing separating two
chunks an embedding reads as nearly the same.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

EMBEDDING_DIMENSIONS = 1536


# ── Metrics ──────────────────────────────────────────────────────────────────
def recall_at_k(retrieved: Sequence[str], expected: Iterable[str], k: int) -> float:
    """Fraction of expected documents appearing in the first k results."""
    wanted = set(expected)
    if not wanted:
        return 1.0
    found = wanted & set(retrieved[:k])
    return len(found) / len(wanted)


def reciprocal_rank(retrieved: Sequence[str], expected: Iterable[str]) -> float:
    """1/rank of the first expected document, or 0 if none appears.

    Rank-based rather than score-based on purpose: it answers "how far does a
    reader have to look", which is the question a citation list poses, and it
    stays comparable across rankers whose scores are on different scales.
    """
    wanted = set(expected)
    for position, doc_id in enumerate(retrieved, start=1):
        if doc_id in wanted:
            return 1.0 / position
    return 0.0


@dataclass
class QueryResult:
    query_id: str
    query: str
    retrieved: list[str]
    expected: list[str]

    def recall(self, k: int) -> float:
        return recall_at_k(self.retrieved, self.expected, k)

    @property
    def rr(self) -> float:
        return reciprocal_rank(self.retrieved, self.expected)

    @property
    def hit(self) -> bool:
        return self.rr > 0


@dataclass
class EvaluationReport:
    label: str
    results: list[QueryResult]

    def recall_at(self, k: int) -> float:
        if not self.results:
            return 0.0
        return sum(r.recall(k) for r in self.results) / len(self.results)

    @property
    def mrr(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.rr for r in self.results) / len(self.results)

    @property
    def misses(self) -> list[QueryResult]:
        """Queries where no expected document was returned at all.

        Reported by name rather than only as an aggregate: an average that moves
        from 0.74 to 0.71 says nothing about which question a participant can no
        longer get an answer to.
        """
        return [r for r in self.results if not r.hit]

    def summary(self, ks: Sequence[int] = (1, 3, 5)) -> str:
        parts = [f"{self.label}: MRR {self.mrr:.3f}"]
        parts += [f"recall@{k} {self.recall_at(k):.3f}" for k in ks]
        parts.append(f"{len(self.misses)}/{len(self.results)} missed")
        return " · ".join(parts)


def evaluate(label: str, results: list[QueryResult]) -> EvaluationReport:
    return EvaluationReport(label=label, results=results)


def compare(baseline: EvaluationReport, candidate: EvaluationReport, k: int = 5) -> dict[str, Any]:
    """Candidate against baseline, including which queries changed either way.

    `regressions` is the field to read. A change that lifts the mean while
    breaking a query that previously worked is not an improvement to ship
    silently, and a mean on its own hides it completely.
    """
    baseline_hits = {r.query_id for r in baseline.results if r.hit}
    candidate_hits = {r.query_id for r in candidate.results if r.hit}
    return {
        "baseline": baseline.summary(),
        "candidate": candidate.summary(),
        "mrr_delta": candidate.mrr - baseline.mrr,
        "recall_delta": candidate.recall_at(k) - baseline.recall_at(k),
        "fixed": sorted(candidate_hits - baseline_hits),
        "regressions": sorted(baseline_hits - candidate_hits),
    }


# ── Deterministic embeddings for a fixture corpus ────────────────────────────
def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


def _stream(seed: str, count: int) -> list[float]:
    """A deterministic pseudo-random stream in [-0.5, 0.5), from a seed string.

    Hash-derived rather than `random`, so the vectors do not depend on the
    interpreter's RNG implementation or on global seeding by another test.
    """
    out: list[float] = []
    counter = 0
    while len(out) < count:
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        out.extend((b / 255.0) - 0.5 for b in digest)
        counter += 1
    return out[:count]


def cluster_embedding(
    cluster: str,
    member: str = "",
    *,
    jitter: float = 0.12,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[float]:
    """A unit vector near `cluster`'s centre, offset slightly by `member`.

    `jitter` sets how far members sit from the centre. It is small on purpose:
    the fixture must reproduce a corpus where an embedding cannot separate two
    chunks that a single token separates completely. Raise it and the vector
    ranker starts solving the exact-term queries on its own, and the fixture
    stops measuring the thing it exists to measure.
    """
    base = _stream(f"cluster:{cluster}", dimensions)
    if not member:
        return _unit(base)
    offset = _stream(f"member:{cluster}:{member}", dimensions)
    return _unit([b + jitter * o for b, o in zip(base, offset)])


def query_embedding(
    cluster: str,
    nearest_member: str = "",
    *,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[float]:
    """An embedding for a query that lands in `cluster`.

    When `nearest_member` is given the query is pulled toward that member, which
    is how the fixture states "the embedding's best guess is this wrong chunk".
    That is the adversarial case, and stating it explicitly beats hoping the
    vectors happen to land that way.
    """
    if not nearest_member:
        return cluster_embedding(cluster, dimensions=dimensions)
    centre = cluster_embedding(cluster, dimensions=dimensions)
    toward = cluster_embedding(cluster, nearest_member, dimensions=dimensions)
    return _unit([0.45 * c + 0.55 * t for c, t in zip(centre, toward)])
