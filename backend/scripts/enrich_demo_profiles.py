"""Refresh field detail on an already-seeded demo DB, in place.

Unlike seed_demo_users.py (which deletes + recreates demo users), this updates
existing sellerNN/buyerNN/service_providerNN@<domain> profiles' fields and
re-embeds them — user_ids, sessions, conversations, and deals built against them
stay valid. Also forces buyer01/seller01 onto aligned fields so discovery matching
surfaces them as each other's top match.

Run against the docker stack:
    POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    OPENROUTER_API_KEY=... \
    .venv/bin/python scripts/enrich_demo_profiles.py
"""
import asyncio
import os
import random
import re

from app.core.database import connect_db, close_db, get_collection
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.modules.profiles import repository as prof_repo
from _demo_data import align_demo_pair, make_fields

CFG_PATH = os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml")
DOMAIN = os.environ.get("SEED_DOMAIN", "demo-machinery.com")
SEED_MARKER = "demo-seed"

CFG = load_marketplace_config(CFG_PATH)
rng = random.Random(42)

EMAIL_RE = re.compile(r"^(seller|buyer|service_provider)(\d+)@")


async def main():
    await connect_db()
    set_marketplace_config(CFG)

    users = await get_collection("users").find({"seed_marker": SEED_MARKER}).to_list(length=100000)
    by_slug: dict[str, list[dict]] = {"seller": [], "buyer": [], "service_provider": []}
    for u in users:
        m = EMAIL_RE.match(str(u.get("email", "")))
        if not m:
            continue
        slug, idx = m.group(1), int(m.group(2))
        by_slug.setdefault(slug, []).append((idx, u))
    for slug in by_slug:
        by_slug[slug].sort(key=lambda pair: pair[0])

    demo_seller_fields = make_fields(CFG, "seller", rng)
    demo_buyer_fields = make_fields(CFG, "buyer", rng)
    align_demo_pair(demo_buyer_fields, demo_seller_fields)

    from app.modules.discovery.indexer import index_profile

    updated = 0
    indexed = 0
    for slug, entries in by_slug.items():
        for idx, user in entries:
            uid = str(user["_id"])
            profile = await prof_repo.get_profile_by_user(uid)
            if not profile:
                continue

            if slug == "seller" and idx == 1:
                fields = demo_seller_fields
            elif slug == "buyer" and idx == 1:
                fields = demo_buyer_fields
            else:
                fields = make_fields(CFG, slug, rng)

            updated_profile = await prof_repo.update_profile(
                str(profile["_id"]), {"fields": fields, "completeness": 100}
            )
            updated += 1
            try:
                await index_profile(updated_profile, CFG)
                indexed += 1
            except Exception:
                pass

    print(f"✓ Refreshed {updated} demo profiles ({indexed} re-embedded)")
    print(f"  aligned pair → seller01@{DOMAIN} ↔ buyer01@{DOMAIN}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
