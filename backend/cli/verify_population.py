"""CLI: verify the watermarks on a population file (GAP-9 / M1-GAP-5).

    python -m cli verify-population population.json
    python -m cli verify-population population.json --policy hash

Checks each record against the synthetic watermark specification without touching
a database, so it can run as a pipeline stage before a load — the standalone
"verify" half of the apply/verify pair, where `stamp-population` is "apply".

Exits non-zero if any record fails, so a build step can gate on it.
"""

from __future__ import annotations

from typing import Any


def _tier(block: dict[str, Any]) -> str:
    if block.get("signature"):
        return "L2 signed"
    if block.get("content_hash"):
        return "L1 hashed"
    return "unmarked"


def verify_population(path: str, policy: str | None = None, secret: str | None = None) -> bool:
    from app.core import watermark
    from app.core.config import settings
    from app.modules.population.loader import load_population_file

    policy = policy or settings.watermark_policy
    key = secret if secret is not None else settings.synthetic_watermark_secret

    try:
        records = load_population_file(path)
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}")
        return False

    total = len(records)
    ok = 0
    failures: list[str] = []
    tiers: dict[str, int] = {}

    for i, rec in enumerate(records):
        ident = rec.get("external_id") if isinstance(rec, dict) else None
        ident = ident or f"record {i}"

        if not isinstance(rec, dict):
            failures.append(f"{ident}: not a JSON object")
            continue

        block = rec.get(watermark.WATERMARK_KEY)
        if not isinstance(block, dict):
            failures.append(f"{ident}: missing watermark")
            continue

        tier = _tier(block)
        tiers[tier] = tiers.get(tier, 0) + 1

        if watermark.verify_at_policy(rec, key, policy):
            ok += 1
            continue

        # Name the specific failure: the operator fix differs for each.
        if block.get("signature") and not watermark.verify_signature(rec, key):
            failures.append(f"{ident}: signature does not match (wrong secret, or edited after stamping)")
        elif block.get("content_hash") and not watermark.verify_content_hash(rec):
            failures.append(f"{ident}: content hash does not match — record edited after stamping")
        elif not block.get("signature") and policy == "signature":
            failures.append(f"{ident}: unsigned under 'signature' policy (use --policy hash to accept)")
        else:
            failures.append(f"{ident}: watermark invalid")

    print(f"file:   {path}")
    print(f"policy: {policy}")
    print(f"records: {total}   valid: {ok}   failed: {len(failures)}")
    if tiers:
        print("tiers:  " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))

    for line in failures[:20]:
        print(f"  - {line}")
    if len(failures) > 20:
        print(f"  ... and {len(failures) - 20} more")

    if failures:
        print("[fail] population did not verify")
        return False
    print("[ok] all records verified")
    return True
