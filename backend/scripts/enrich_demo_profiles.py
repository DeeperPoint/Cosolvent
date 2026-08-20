"""Refresh field detail on an already-seeded demo DB, in place.

Re-runs the same watermarked population-import path (GAP-9/10) that seeded the demo
in the first place: freshly generated fields for the existing seller/buyer/
service_provider external_ids upsert in place (same user_ids, so sessions,
conversations, and deals built against them stay valid) and get re-embedded. Also
forces buyer01/seller01 onto aligned fields so discovery matching surfaces them as
each other's top match.

Run against the docker stack:
    POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    OPENROUTER_API_KEY=... \
    .venv/bin/python scripts/enrich_demo_profiles.py
"""
import asyncio
import os
import random

from app.core import watermark
from app.core.config import settings
from app.core.database import close_db, connect_db, get_collection
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.modules.population.service import import_population
from _demo_data import align_demo_pair, make_fields

CFG_PATH = os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml")
DOMAIN = os.environ.get("SEED_DOMAIN", "demo-machinery.com")
SLUGS = ("seller", "buyer", "service_provider")

CFG = load_marketplace_config(CFG_PATH)
rng = random.Random(42)


async def _existing_counts() -> dict[str, int]:
    """How many external_ids per slug (seller01, seller02, ...) seed_demo_users.py
    already created — refresh regenerates exactly that many, in the same order, so
    every external_id lands on an existing record (upsert, never a fresh create)."""
    return {
        slug: await get_collection("users").count_documents({"is_synthetic": True, "participant_type": slug})
        for slug in SLUGS
    }


def _build_records(counts: dict[str, int]) -> list[dict]:
    demo_seller_fields = make_fields(CFG, "seller", rng)
    demo_buyer_fields = make_fields(CFG, "buyer", rng)
    align_demo_pair(demo_buyer_fields, demo_seller_fields)

    records = []
    for slug, n in counts.items():
        for i in range(1, n + 1):
            if slug == "seller" and i == 1:
                fields = demo_seller_fields
            elif slug == "buyer" and i == 1:
                fields = demo_buyer_fields
            else:
                fields = make_fields(CFG, slug, rng)
            records.append({"participant_type": slug, "external_id": f"{slug}{i:02d}", "fields": fields})
    return records


async def main():
    await connect_db()
    set_marketplace_config(CFG)

    counts = await _existing_counts()
    if not any(counts.values()):
        print("No seeded demo profiles found — run seed_demo_users.py first.")
        await close_db()
        return

    records = _build_records(counts)
    stamped = [watermark.stamp(r, settings.synthetic_watermark_secret) for r in records]

    # No email_domain/password_hash: this is a pure field refresh on external_ids that
    # already exist, and upsert_synthetic_profile never touches login credentials on
    # an existing user — seller01/buyer01/... keep whatever seed_demo_users.py set.
    res = await import_population(CFG, stamped, mode="demo")

    print(f"✓ Refreshed {res.updated} demo profiles ({res.indexed} re-embedded)")
    if res.rejected_watermark or res.skipped_invalid:
        print(f"  ! rejected_watermark={res.rejected_watermark} skipped_invalid={res.skipped_invalid}")
        for e in res.errors[:10]:
            print(f"    - {e}")
    print(f"  aligned pair → seller01@{DOMAIN} ↔ buyer01@{DOMAIN}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
