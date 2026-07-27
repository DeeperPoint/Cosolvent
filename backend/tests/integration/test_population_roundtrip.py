"""Live pgvector round-trip for C0 population ingest (GAP-10) + watermark gating (GAP-9).

Deterministic, provider-free: embeddings are stubbed with a content-derived
vector, so the full ingest path (validate -> upsert synthetic profile + user ->
index into profile_vectors -> retrieve) runs against a real migrated database
without an embedding provider.

Gated by RUN_INTEGRATION.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core import watermark
from app.core.database import close_db, connect_db, get_collection
from app.core.marketplace_config import load_marketplace_config
from app.modules.discovery import vector_service
from app.modules.population.service import import_population
from tests.e2e.helpers import require_mode

FIXTURES = Path(__file__).parent.parent / "test_config"
SECRET = "it-watermark-secret"
DIM = 1536

_POP = [
    {"participant_type": "producer", "external_id": "it-prod-1",
     "fields": {"farm_name": "North Ridge Farms", "country": "Canada", "primary_crops": ["Wheat", "Barley"]}},
    {"participant_type": "buyer", "external_id": "it-buyer-1", "fields": {"org_name": "Acme Mills"}},
]


def _vec_for(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    base = [b / 255.0 for b in digest]  # 32 values in [0,1]
    v = (base * (DIM // len(base) + 1))[:DIM]
    norm = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norm for x in v]


async def _cleanup():
    for r in _POP:
        await get_collection("profiles").delete_one({"external_id": r["external_id"]})
        await get_collection("users").delete_one({"external_id": r["external_id"]})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_population_import_roundtrip():
    require_mode("RUN_INTEGRATION")
    cfg = load_marketplace_config(FIXTURES / "agriculture.yaml")
    stamped = [watermark.stamp(r, SECRET) for r in _POP]

    await connect_db()
    try:
        await _cleanup()

        with patch("app.modules.discovery.indexer.get_embedding",
                   new=AsyncMock(side_effect=lambda text: _vec_for(text))):
            # 1. Import demo + index: both records land and are indexed.
            res = await import_population(cfg, stamped, mode="demo", secret=SECRET, do_index=True)
            assert res.loaded == 2 and res.indexed == 2 and res.rejected_watermark == 0, res

            prof = await get_collection("profiles").find_one({"external_id": "it-prod-1"})
            assert prof and prof.get("is_synthetic") is True and prof["participant_type"] == "producer"

            # 2. The indexed vector is retrievable via the same search matching uses.
            hits = await vector_service.find_similar_profiles(
                embedding=_vec_for("[producer] North Ridge Farms Wheat Barley"),
                participant_types=["producer"], exclude_profile_ids=[], min_score=0.0, limit=10)
            assert any(h["id"] == str(prof["_id"]) for h in hits)

            # 3. Idempotent re-import: no new profiles, updated in place.
            res2 = await import_population(cfg, stamped, mode="demo", secret=SECRET, do_index=True)
            assert res2.updated == 2 and res2.loaded == 0

        # 4. Demo mode rejects unwatermarked records.
        res3 = await import_population(cfg, _POP, mode="demo", secret=SECRET, do_index=False)
        assert res3.rejected_watermark == 2 and res3.loaded == 0

        # 5. Production mode rejects watermarked (synthetic) records — clean cutover.
        res4 = await import_population(cfg, stamped, mode="production", secret=SECRET, do_index=False)
        assert res4.rejected_watermark == 2 and res4.loaded == 0
    finally:
        await _cleanup()
        await close_db()
