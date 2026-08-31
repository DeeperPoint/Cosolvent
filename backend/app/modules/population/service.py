"""Population import service (GAP-10) with boundary watermark enforcement (GAP-9).

For each record: enforce the watermark per mode, validate its fields against the
marketplace profile schema, idempotently upsert the synthetic profile, and index
it into pgvector — reusing the existing validation and indexing code paths.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import ValidationError

from app.core import watermark
from app.core.config import settings
from app.core.marketplace_config import MarketplaceConfig
from app.engine.schema_engine import compute_completeness, validate_profile_fields
from app.modules.discovery.indexer import index_profile
from app.modules.population import repository as repo
from app.modules.population.schemas import PopulationImportResult

logger = logging.getLogger("cosolvent.population")

Mode = Literal["demo", "production"]


def _watermark_rejection(
    rec: dict[str, Any], mode: Mode, secret: str, policy: str = "signature"
) -> str | None:
    """Return a rejection reason if the record fails the mode's watermark rule, else None."""
    if mode == "production":
        # Clean cutover: no synthetic data in production, at either tier.
        if watermark.is_watermarked(rec):
            return "watermarked (synthetic) record rejected in production mode"
        return None

    # demo / synthetic mode: the record must satisfy this instance's admission policy.
    if watermark.verify_at_policy(rec, secret, policy):
        return None
    if not watermark.is_watermarked(rec):
        return "missing synthetic watermark"
    if policy == "signature" and not (rec.get(watermark.WATERMARK_KEY) or {}).get("signature"):
        # Distinguishes "unsigned by an unkeyed generator" from "signature is wrong",
        # because the operator fix differs: relax the policy versus align the secret.
        return "unsigned watermark rejected under signature policy (set WATERMARK_POLICY=hash to accept)"
    return "invalid synthetic watermark"


async def import_population(
    config: MarketplaceConfig,
    records: list[dict[str, Any]],
    *,
    mode: Mode = "demo",
    secret: str | None = None,
    policy: str | None = None,
    do_index: bool = True,
    email_domain: str | None = None,
    password_hash: str | None = None,
) -> PopulationImportResult:
    """``email_domain``/``password_hash`` are the interactive-demo-account extension:
    when set, each created synthetic user gets ``{external_id}@{email_domain}`` and
    the given password hash instead of the default unaddressable/no-login C0 user, so
    it can log in through the normal ``/api/auth/login`` flow. Every other GAP-9/10
    guarantee (watermark gate, schema validation, idempotent upsert, `is_synthetic`
    flag) still applies — this only changes what the *user* record looks like."""
    secret = secret if secret is not None else settings.synthetic_watermark_secret
    policy = policy if policy is not None else settings.watermark_policy
    res = PopulationImportResult(mode=mode, total=len(records))

    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            res.skipped_invalid += 1
            res.errors.append(f"record {i}: not a JSON object")
            continue
        pt = rec.get("participant_type")
        ext = rec.get("external_id")
        fields = rec.get("fields")
        if not pt or not ext or not isinstance(fields, dict):
            res.skipped_invalid += 1
            res.errors.append(f"record {i}: missing participant_type / external_id / fields")
            continue

        # ── GAP-9: watermark gate at the ingest boundary ──
        reason = _watermark_rejection(rec, mode, secret, policy)
        if reason:
            res.rejected_watermark += 1
            res.errors.append(f"{ext}: {reason}")
            continue

        # ── schema validation (reuse the participant-facing validator) ──
        if config.get_type(pt) is None or pt not in config.profile_schemas:
            res.skipped_invalid += 1
            res.errors.append(f"{ext}: unknown participant_type '{pt}'")
            continue
        try:
            validated = validate_profile_fields(config, pt, fields)
        except ValidationError as exc:
            res.skipped_invalid += 1
            res.errors.append(f"{ext}: field validation failed ({exc.error_count()} error(s))")
            continue
        completeness = compute_completeness(config, pt, validated)

        email = f"{ext}@{email_domain}" if email_domain else None
        profile, created = await repo.upsert_synthetic_profile(
            ext, pt, validated, completeness, email=email, password_hash=password_hash
        )
        if created:
            res.loaded += 1
        else:
            res.updated += 1

        if do_index:
            try:
                await index_profile(profile, config)
                res.indexed += 1
            except Exception:  # noqa: BLE001 - a single indexing failure must not abort the import.
                logger.warning("Indexing failed for synthetic profile %s", ext, exc_info=True)
                res.errors.append(f"{ext}: indexing failed (loaded, will need re-index)")

    logger.info(
        "Population import (%s): loaded=%d updated=%d rejected_watermark=%d skipped_invalid=%d indexed=%d",
        mode, res.loaded, res.updated, res.rejected_watermark, res.skipped_invalid, res.indexed,
    )
    return res
