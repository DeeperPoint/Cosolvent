"""Unit tests for the population import service (GAP-10) + watermark gating (GAP-9).

Persistence + indexing are mocked; validation uses the real agriculture config.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core import watermark
from app.core.marketplace_config import load_marketplace_config
from app.modules.population import service
from app.modules.population.loader import parse_population_text

FIXTURES = Path(__file__).parent.parent / "test_config"
SECRET = "test-secret"


def _cfg():
    return load_marketplace_config(FIXTURES / "agriculture.yaml")


def _producer(ext: str, country: str = "Canada", crops=None) -> dict:
    return {"participant_type": "producer", "external_id": ext,
            "fields": {"farm_name": f"Farm {ext}", "country": country, "primary_crops": crops or ["Wheat"]}}


@contextmanager
def _mock_persist(created: bool = True):
    async def _upsert(external_id, participant_type, fields, completeness, *, email=None, password_hash=None):
        return {"_id": external_id, "participant_type": participant_type, "fields": fields}, created
    with patch.object(service.repo, "upsert_synthetic_profile", side_effect=_upsert) as up, \
         patch.object(service, "index_profile", new=AsyncMock()) as idx:
        yield up, idx


async def _run(records, mode="demo", do_index=False, created=True):
    with _mock_persist(created=created):
        return await service.import_population(_cfg(), records, mode=mode, secret=SECRET, do_index=do_index)


# ── loader ────────────────────────────────────────────────────────────────

def test_loader_accepts_list_and_records_object():
    assert parse_population_text('[{"a":1}]') == [{"a": 1}]
    assert parse_population_text('{"records":[{"a":1}]}') == [{"a": 1}]
    with pytest.raises(ValueError):
        parse_population_text('{"nope": 1}')


# ── demo mode: watermark required ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_rejects_unwatermarked():
    res = await _run([_producer("s1")])  # no watermark
    assert res.rejected_watermark == 1 and res.loaded == 0
    assert "missing synthetic watermark" in res.errors[0]


@pytest.mark.asyncio
async def test_demo_accepts_valid_watermark():
    res = await _run([watermark.stamp(_producer("s1"), SECRET)])
    assert res.loaded == 1 and res.rejected_watermark == 0 and res.skipped_invalid == 0


@pytest.mark.asyncio
async def test_demo_rejects_tampered_watermark():
    rec = watermark.stamp(_producer("s1"), SECRET)
    rec["fields"]["country"] = "USA"  # tamper after signing
    res = await _run([rec])
    assert res.rejected_watermark == 1
    assert "invalid synthetic watermark" in res.errors[0]


# ── production mode: clean cutover ────────────────────────────────────────

@pytest.mark.asyncio
async def test_production_rejects_watermarked():
    res = await _run([watermark.stamp(_producer("s1"), SECRET)], mode="production")
    assert res.rejected_watermark == 1 and res.loaded == 0


@pytest.mark.asyncio
async def test_production_accepts_unwatermarked_real_record():
    res = await _run([_producer("real-1")], mode="production")  # no watermark = real data
    assert res.loaded == 1 and res.rejected_watermark == 0


# ── schema validation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_field_type_skipped():
    # primary_crops is multi_select (a list); a scalar violates the schema.
    bad = {"participant_type": "producer", "external_id": "s1",
           "fields": {"farm_name": "F", "country": "Canada", "primary_crops": "Wheat"}}
    res = await _run([watermark.stamp(bad, SECRET)])
    assert res.skipped_invalid == 1 and res.loaded == 0
    assert "validation failed" in res.errors[0]


@pytest.mark.asyncio
async def test_unknown_participant_type_skipped():
    rec = watermark.stamp({"participant_type": "ghost", "external_id": "g1", "fields": {}}, SECRET)
    res = await _run([rec])
    assert res.skipped_invalid == 1
    assert "unknown participant_type" in res.errors[0]


@pytest.mark.asyncio
async def test_missing_required_keys_skipped():
    res = await _run([{"external_id": "x", "fields": {}}])  # no participant_type
    assert res.skipped_invalid == 1


# ── idempotency + indexing ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reimport_counts_as_updated():
    res = await _run([watermark.stamp(_producer("s1"), SECRET)], created=False)
    assert res.updated == 1 and res.loaded == 0


@pytest.mark.asyncio
async def test_indexing_invoked_when_enabled():
    with _mock_persist() as (_up, idx):
        res = await service.import_population(
            _cfg(), [watermark.stamp(_producer("s1"), SECRET)], mode="demo", secret=SECRET, do_index=True)
    assert res.indexed == 1
    idx.assert_awaited_once()


# ── interactive demo accounts: email_domain + password_hash (still watermark-gated) ──

@pytest.mark.asyncio
async def test_no_login_credentials_by_default():
    """The plain C0 path (no email_domain/password_hash) still produces an
    unaddressable, no-login synthetic user — unchanged default behavior."""
    with _mock_persist() as (up, _idx):
        await service.import_population(
            _cfg(), [watermark.stamp(_producer("s1"), SECRET)], mode="demo", secret=SECRET, do_index=False)
    assert up.call_args.kwargs == {"email": None, "password_hash": None}


@pytest.mark.asyncio
async def test_email_domain_and_password_hash_threaded_to_repo():
    """A caller building login-capable demo accounts (e.g. seed_demo_users.py) still
    goes through the same watermark-gated, schema-validated import path — it just
    asks for a real email + password on the synthetic user this creates."""
    with _mock_persist() as (up, _idx):
        await service.import_population(
            _cfg(), [watermark.stamp(_producer("s1"), SECRET)], mode="demo", secret=SECRET,
            do_index=False, email_domain="demo.example.com", password_hash="hashed-pw",
        )
    assert up.call_args.kwargs == {"email": "s1@demo.example.com", "password_hash": "hashed-pw"}


@pytest.mark.asyncio
async def test_login_credentials_do_not_bypass_the_watermark_gate():
    """email_domain/password_hash must not become a side door around GAP-9: an
    unwatermarked record is still rejected even when demo-login fields are requested."""
    with _mock_persist() as (up, _idx):
        res = await service.import_population(
            _cfg(), [_producer("s1")], mode="demo", secret=SECRET,  # no watermark
            do_index=False, email_domain="demo.example.com", password_hash="hashed-pw",
        )
    assert res.rejected_watermark == 1 and res.loaded == 0
    up.assert_not_awaited()
