"""Unit tests for the synthetic-population watermark (GAP-9)."""

from __future__ import annotations

from app.core import watermark

SECRET = "test-secret"


def _rec() -> dict:
    return {"participant_type": "producer", "external_id": "syn-1",
            "fields": {"farm_name": "North Ridge", "crops": ["Wheat", "Barley"]}}


def test_stamp_and_verify_roundtrip():
    r = watermark.stamp(_rec(), SECRET)
    assert watermark.is_watermarked(r)
    assert watermark.verify(r, SECRET)
    assert r["_watermark"]["algo"] == watermark.WATERMARK_ALGO


def test_unwatermarked_record_fails_verify():
    assert not watermark.is_watermarked(_rec())
    assert not watermark.verify(_rec(), SECRET)


def test_wrong_secret_fails():
    assert not watermark.verify(watermark.stamp(_rec(), SECRET), "other-secret")


def test_tampered_fields_fail():
    r = watermark.stamp(_rec(), SECRET)
    r["fields"]["farm_name"] = "Someone Else"  # tamper after signing
    assert not watermark.verify(r, SECRET)


def test_tampered_external_id_fails():
    r = watermark.stamp(_rec(), SECRET)
    r["external_id"] = "syn-2"
    assert not watermark.verify(r, SECRET)


def test_unknown_algo_rejected():
    r = watermark.stamp(_rec(), SECRET)
    r["_watermark"]["algo"] = "md5"
    assert not watermark.verify(r, SECRET)


def test_signature_is_field_order_independent():
    r1 = {"participant_type": "p", "external_id": "e", "fields": {"a": 1, "b": 2}}
    r2 = {"participant_type": "p", "external_id": "e", "fields": {"b": 2, "a": 1}}
    assert watermark.sign(r1, SECRET) == watermark.sign(r2, SECRET)
