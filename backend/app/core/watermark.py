"""Synthetic-population watermarking (GAP-9).

Every synthetic participant record carries a tamper-evident watermark so the
ingest boundary can (a) reject unwatermarked synthetic data in demo/synthetic
mode and (b) reject watermarked data in production — the clean-cutover rule,
enforced in the data layer rather than by convention.

The watermark has two tiers, and which one an instance demands is policy:

  **L1 — content hash + provenance (always present).**
  A plain SHA-256 over the record's canonical payload, alongside a provenance
  block naming the generator. Any party can recompute it with no shared secret,
  which is what makes the ingest contract genuinely open: a third-party
  generator can emit conforming, integrity-checkable records without being
  issued a key. It proves the record has not been altered since it was stamped;
  it does not prove who stamped it.

  **L2 — HMAC-SHA256 signature (optional).**
  Keyed by a shared secret, so it additionally attests authorship. Available
  only to generators that hold the secret.

An instance running ``watermark_policy="signature"`` requires L2 and therefore
only accepts populations from keyed generators. Under ``"hash"`` it accepts L1,
admitting bring-your-own generators while still rejecting anything tampered with
after stamping. Both tiers are verified against the same canonical bytes, so a
record stamped once satisfies whichever policy the receiving instance applies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

WATERMARK_ALGO = "hmac-sha256-v1"
CONTENT_HASH_ALGO = "sha256"
WATERMARK_KEY = "_watermark"
SPEC_VERSION = "1.0"


def _canonical_payload(record: dict[str, Any]) -> bytes:
    """Deterministic bytes of the record's signed content (excludes the watermark
    itself), so signing and verification always agree regardless of key order."""
    signed = {
        "participant_type": record.get("participant_type"),
        "external_id": record.get("external_id"),
        "fields": record.get("fields", {}) or {},
    }
    return json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(record: dict[str, Any]) -> str:
    """L1: keyless SHA-256 over the canonical payload, prefixed with its algorithm.

    Prefixed so a future algorithm change is self-describing on the wire rather
    than a silent reinterpretation of the same hex string.
    """
    digest = hashlib.sha256(_canonical_payload(record)).hexdigest()
    return f"{CONTENT_HASH_ALGO}:{digest}"


def sign(record: dict[str, Any], secret: str) -> str:
    """L2: hex HMAC-SHA256 signature for a record."""
    return hmac.new(secret.encode("utf-8"), _canonical_payload(record), hashlib.sha256).hexdigest()


def stamp(
    record: dict[str, Any],
    secret: str | None = None,
    *,
    generator: str = "cosolvent/stamp-population",
    generator_version: str = SPEC_VERSION,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a copy of ``record`` with a watermark attached.

    L1 is always written. L2 is added when a secret is supplied, so the same
    call serves a keyed generator and an unkeyed third-party one.
    """
    out = dict(record)
    block: dict[str, Any] = {
        "synthetic": True,
        "spec_version": SPEC_VERSION,
        "algo": WATERMARK_ALGO,
        "content_hash": content_hash(record),
        "provenance": {
            "generator": generator,
            "generator_version": generator_version,
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        },
    }
    if secret:
        block["signature"] = sign(record, secret)
    out[WATERMARK_KEY] = block
    return out


def is_watermarked(record: dict[str, Any]) -> bool:
    """True if the record carries a watermark block (valid or not).

    Either tier counts: production's clean-cutover rule rejects anything marked
    synthetic, and an unsigned-but-hashed record is still marked synthetic.
    """
    wm = record.get(WATERMARK_KEY)
    if not isinstance(wm, dict):
        return False
    return bool(wm.get("signature") or wm.get("content_hash") or wm.get("synthetic"))


def verify_content_hash(record: dict[str, Any]) -> bool:
    """True if the record carries an L1 hash matching its current content."""
    wm = record.get(WATERMARK_KEY)
    if not isinstance(wm, dict):
        return False
    claimed = wm.get("content_hash")
    if not isinstance(claimed, str) or not claimed:
        return False
    return hmac.compare_digest(claimed, content_hash(record))


def verify_signature(record: dict[str, Any], secret: str) -> bool:
    """True if the record carries an L2 signature matching its content under ``secret``."""
    wm = record.get(WATERMARK_KEY)
    if not isinstance(wm, dict):
        return False
    if wm.get("algo") != WATERMARK_ALGO:
        return False
    signature = wm.get("signature")
    if not isinstance(signature, str) or not signature:
        return False
    return hmac.compare_digest(signature, sign(record, secret))


def verify(record: dict[str, Any], secret: str) -> bool:
    """Backwards-compatible alias for L2 verification."""
    return verify_signature(record, secret)


def verify_at_policy(record: dict[str, Any], secret: str, policy: str = "signature") -> bool:
    """Verify a record against an instance's admission policy.

    ``signature`` demands L2 — only keyed generators are admitted.
    ``hash`` accepts L1, so an unkeyed third-party generator is admitted while
    tampering is still caught. A record carrying a signature is checked against
    it under either policy, so a broken signature never passes as merely hashed.
    """
    wm = record.get(WATERMARK_KEY)
    if not isinstance(wm, dict):
        return False

    if wm.get("signature"):
        if not verify_signature(record, secret):
            return False
        # A signed record must still carry a truthful hash when it declares one.
        if wm.get("content_hash") and not verify_content_hash(record):
            return False
        return True

    if policy == "hash":
        return verify_content_hash(record)
    return False
