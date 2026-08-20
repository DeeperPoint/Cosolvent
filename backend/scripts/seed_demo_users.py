"""Seed the running marketplace with active, login-capable synthetic participants.

Goes through the same watermarked C0 population-import path (GAP-9/10) as any other
synthetic data — these are demo accounts, not real users, and the ingest boundary
shouldn't be able to tell them apart from a ClientSynth export. The only thing that
makes them special is that ``import_population`` is asked to give each synthetic user
a real, loggable email + a shared password instead of the default unaddressable
no-login C0 user, so a human can sign in and click around.

Run against the docker stack:
    POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    OPENROUTER_API_KEY=... \
    .venv/bin/python scripts/seed_demo_users.py
"""
import asyncio
import os
import random

from app.core import watermark
from app.core.config import settings
from app.core.database import close_db, connect_db, get_collection
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.security import hash_password
from app.modules.population.service import import_population
from _demo_data import align_demo_pair, make_fields

CFG_PATH = os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml")
PASSWORD = os.environ.get("SEED_PASSWORD", "Passw0rd!23")
# A normal registrable domain — the login endpoint validates EmailStr, which rejects
# reserved TLDs like .test/.example, so those addresses could never authenticate.
DOMAIN = os.environ.get("SEED_DOMAIN", "demo-machinery.com")
COUNTS = {"seller": 40, "buyer": 30, "service_provider": 15}

CFG = load_marketplace_config(CFG_PATH)
rng = random.Random(42)


async def _cleanup_prior():
    """Remove any earlier demo batch (this domain, or the old invalid .test domain
    from before this script went through the population pipeline)."""
    users = await get_collection("users").find({"is_synthetic": True}).to_list(length=100000)
    removed = 0
    for u in users:
        email = str(u.get("email", ""))
        if email.endswith(f"@{DOMAIN}") or email.endswith("@demo.test"):
            uid = u["_id"]
            prof = await get_collection("profiles").find_one({"user_id": uid})
            if prof:
                await get_collection("profiles").delete_one({"_id": prof["_id"]})
            await get_collection("users").delete_one({"_id": uid})
            removed += 1
    if removed:
        print(f"[cleanup] removed {removed} prior demo user(s)")


def _build_records() -> list[dict]:
    """Population-import records for every demo account. Field generation is
    unchanged from before — only how the result reaches the database changes."""
    # Pre-compute an aligned pair for the flagship demo accounts (seller01/buyer01) so
    # discovery matching surfaces them as an obvious top match for each other.
    demo_seller_fields = make_fields(CFG, "seller", rng)
    demo_buyer_fields = make_fields(CFG, "buyer", rng)
    align_demo_pair(demo_buyer_fields, demo_seller_fields)

    records = []
    for slug, n in COUNTS.items():
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
    await _cleanup_prior()

    records = _build_records()
    stamped = [watermark.stamp(r, settings.synthetic_watermark_secret) for r in records]
    pw_hash = hash_password(PASSWORD)

    res = await import_population(CFG, stamped, mode="demo", email_domain=DOMAIN, password_hash=pw_hash)

    total = res.loaded + res.updated
    print(f"\n✓ Seeded {total} active participants ({res.indexed} embedded for vector search)")
    for slug, n in COUNTS.items():
        print(f"  {slug}: {n}")
    if res.rejected_watermark or res.skipped_invalid:
        print(f"  ! rejected_watermark={res.rejected_watermark} skipped_invalid={res.skipped_invalid}")
        for e in res.errors[:10]:
            print(f"    - {e}")

    print("\n─────────── LOGIN CREDENTIALS ───────────")
    print(f"  password (all users): {PASSWORD}")
    print("  sample logins:")
    print(f"    seller           →  seller01@{DOMAIN}")
    print(f"    buyer            →  buyer01@{DOMAIN}")
    print(f"    service_provider →  service_provider01@{DOMAIN}")
    print(f"  (any sellerNN/buyerNN/service_providerNN @{DOMAIN} works)")
    print("─────────────────────────────────────────")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
