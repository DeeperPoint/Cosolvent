"""Synthetic-population watermarking (GAP-9).

Every synthetic participant record carries a tamper-evident watermark so the
ingest boundary can (a) reject unwatermarked synthetic data in demo/synthetic
mode and (b) reject watermarked data in production — the clean-cutover rule,
enforced in the data layer rather than by convention.

The watermark is an HMAC-SHA256 over the record's stable content (participant
type + external id + fields), keyed by a shared secret. ClientSynth signs with
the same secret+algorithm; ``sign`` here is the reference implementation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

WATERMARK_ALGO = "hmac-sha256-v1"
WATERMARK_KEY = "_watermark"


def _canonical_payload(record: dict[str, Any]) -> bytes:
    """Deterministic bytes of the record's signed content (excludes the watermark
    itself), so signing and verification always agree regardless of key order."""
    signed = {
        "participant_type": record.get("participant_type"),
        "external_id": record.get("external_id"),
        "fields": record.get("fields", {}) or {},
    }
    return json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign(record: dict[str, Any], secret: str) -> str:
    """Return the hex HMAC-SHA256 signature for a record."""
    return hmac.new(secret.encode("utf-8"), _canonical_payload(record), hashlib.sha256).hexdigest()


def stamp(record: dict[str, Any], secret: str) -> dict[str, Any]:
    """Return a copy of ``record`` with a valid watermark attached."""
    out = dict(record)
    out[WATERMARK_KEY] = {"synthetic": True, "algo": WATERMARK_ALGO, "signature": sign(record, secret)}
    return out


def is_watermarked(record: dict[str, Any]) -> bool:
    """True if the record carries a watermark block (valid or not)."""
    wm = record.get(WATERMARK_KEY)
    return isinstance(wm, dict) and bool(wm.get("signature"))


def verify(record: dict[str, Any], secret: str) -> bool:
    """True only if the record carries a well-formed watermark whose signature
    matches the record's content under ``secret`` (constant-time compare)."""
    wm = record.get(WATERMARK_KEY)
    if not isinstance(wm, dict):
        return False
    if wm.get("algo") != WATERMARK_ALGO:
        return False
    signature = wm.get("signature")
    if not isinstance(signature, str) or not signature:
        return False
    return hmac.compare_digest(signature, sign(record, secret))
