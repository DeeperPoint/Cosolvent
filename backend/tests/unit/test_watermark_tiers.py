"""Two-tier watermark: keyless content hash (L1) and keyed signature (L2).

L1 is what makes the ingest contract genuinely open — a generator that holds no
shared secret can still emit records an instance will accept under the `hash`
policy, and tampering is still caught. L2 additionally attests authorship.
"""

from __future__ import annotations

import pytest

from app.core import watermark
from app.modules.population.service import _watermark_rejection

RECORD = {
    "participant_type": "producer",
    "external_id": "prod-1",
    "fields": {"farm_name": "North Ridge", "country": "Canada"},
}
SECRET = "shared-secret"


class TestContentHash:
    def test_hash_is_algorithm_prefixed(self):
        assert watermark.content_hash(RECORD).startswith("sha256:")

    def test_hash_is_deterministic_and_key_order_independent(self):
        reordered = {
            "fields": {"country": "Canada", "farm_name": "North Ridge"},
            "external_id": "prod-1",
            "participant_type": "producer",
        }
        assert watermark.content_hash(reordered) == watermark.content_hash(RECORD)

    def test_hash_changes_with_content(self):
        other = {**RECORD, "fields": {**RECORD["fields"], "country": "USA"}}
        assert watermark.content_hash(other) != watermark.content_hash(RECORD)

    def test_unkeyed_stamp_carries_l1_and_no_signature(self):
        block = watermark.stamp(RECORD)[watermark.WATERMARK_KEY]
        assert block["content_hash"].startswith("sha256:")
        assert "signature" not in block
        assert block["provenance"]["generator"]
        assert block["synthetic"] is True

    def test_keyed_stamp_carries_both_tiers(self):
        block = watermark.stamp(RECORD, SECRET)[watermark.WATERMARK_KEY]
        assert block["content_hash"] and block["signature"]

    def test_tampering_breaks_the_hash(self):
        stamped = watermark.stamp(RECORD)
        stamped["fields"]["country"] = "USA"
        assert watermark.verify_content_hash(stamped) is False


class TestAdmissionPolicy:
    def test_signed_record_passes_both_policies(self):
        s = watermark.stamp(RECORD, SECRET)
        assert watermark.verify_at_policy(s, SECRET, "signature") is True
        assert watermark.verify_at_policy(s, SECRET, "hash") is True

    def test_unsigned_record_passes_hash_only(self):
        u = watermark.stamp(RECORD)
        assert watermark.verify_at_policy(u, SECRET, "hash") is True
        assert watermark.verify_at_policy(u, SECRET, "signature") is False

    def test_broken_signature_is_rejected_even_under_hash_policy(self):
        """A record claiming a signature must satisfy it; relaxing the policy
        must not let a forged one through as merely hashed."""
        s = watermark.stamp(RECORD, SECRET)
        s[watermark.WATERMARK_KEY]["signature"] = "0" * 64
        assert watermark.verify_at_policy(s, SECRET, "hash") is False

    def test_signature_valid_but_hash_tampered_is_rejected(self):
        s = watermark.stamp(RECORD, SECRET)
        s[watermark.WATERMARK_KEY]["content_hash"] = "sha256:" + "0" * 64
        assert watermark.verify_at_policy(s, SECRET, "signature") is False

    def test_wrong_secret_fails_signature_policy(self):
        s = watermark.stamp(RECORD, SECRET)
        assert watermark.verify_at_policy(s, "other-secret", "signature") is False

    def test_unmarked_record_fails_every_policy(self):
        for policy in ("signature", "hash"):
            assert watermark.verify_at_policy(RECORD, SECRET, policy) is False


class TestBackwardCompatibility:
    def test_legacy_verify_still_checks_the_signature(self):
        assert watermark.verify(watermark.stamp(RECORD, SECRET), SECRET) is True

    def test_legacy_signature_only_block_still_verifies(self):
        """Records stamped before content hashing existed must keep working."""
        legacy = dict(RECORD)
        legacy[watermark.WATERMARK_KEY] = {
            "synthetic": True,
            "algo": watermark.WATERMARK_ALGO,
            "signature": watermark.sign(RECORD, SECRET),
        }
        assert watermark.verify(legacy, SECRET) is True
        assert watermark.verify_at_policy(legacy, SECRET, "signature") is True

    def test_unsigned_record_still_counts_as_watermarked(self):
        """Production's clean cutover must refuse hashed-only synthetic data too."""
        assert watermark.is_watermarked(watermark.stamp(RECORD)) is True


class TestIngestGate:
    @pytest.mark.parametrize("policy", ["signature", "hash"])
    def test_production_refuses_either_tier(self, policy):
        for rec in (watermark.stamp(RECORD, SECRET), watermark.stamp(RECORD)):
            reason = _watermark_rejection(rec, "production", SECRET, policy)
            assert reason and "production" in reason

    def test_demo_admits_signed_under_signature_policy(self):
        s = watermark.stamp(RECORD, SECRET)
        assert _watermark_rejection(s, "demo", SECRET, "signature") is None

    def test_demo_refuses_unsigned_under_signature_policy_with_actionable_reason(self):
        u = watermark.stamp(RECORD)
        reason = _watermark_rejection(u, "demo", SECRET, "signature")
        assert reason and "WATERMARK_POLICY=hash" in reason

    def test_demo_admits_unsigned_under_hash_policy(self):
        u = watermark.stamp(RECORD)
        assert _watermark_rejection(u, "demo", SECRET, "hash") is None

    def test_demo_refuses_unmarked(self):
        reason = _watermark_rejection(RECORD, "demo", SECRET, "hash")
        assert reason == "missing synthetic watermark"
