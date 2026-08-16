"""Seed the running marketplace with active participants + profiles, and print logins.

Bypasses the disabled public-signup + manual-approval flow by writing directly (real bcrypt
hashing, real profile docs with status=active) to the running Postgres. Best-effort embedding
indexing so vector search / suggested-matches also work.

Run against the docker stack:
    POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    OPENROUTER_API_KEY=... \
    .venv/bin/python scripts/seed_demo_users.py
"""
import asyncio
import os
import random
from datetime import datetime, timezone

from app.core.database import connect_db, close_db, get_collection
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.security import hash_password
from app.modules.profiles import repository as prof_repo
from _demo_data import align_demo_pair, make_fields

CFG_PATH = os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml")
PASSWORD = os.environ.get("SEED_PASSWORD", "Passw0rd!23")
# A normal registrable domain — the login endpoint validates EmailStr, which rejects
# reserved TLDs like .test/.example, so those addresses could never authenticate.
DOMAIN = os.environ.get("SEED_DOMAIN", "demo-machinery.com")
SEED_MARKER = "demo-seed"
COUNTS = {"seller": 40, "buyer": 30, "service_provider": 15}

CFG = load_marketplace_config(CFG_PATH)
rng = random.Random(42)


async def _cleanup_prior():
    """Remove any earlier demo batch (by marker or the invalid .test domain)."""
    users = await get_collection("users").find({}).to_list(length=100000)
    removed = 0
    for u in users:
        email = str(u.get("email", ""))
        if u.get("seed_marker") == SEED_MARKER or email.endswith("@demo.test"):
            uid = u["_id"]
            prof = await get_collection("profiles").find_one({"user_id": uid})
            if prof:
                await get_collection("profiles").delete_one({"_id": prof["_id"]})
            await get_collection("users").delete_one({"_id": uid})
            removed += 1
    if removed:
        print(f"[cleanup] removed {removed} prior demo user(s)")


async def main():
    await connect_db()
    set_marketplace_config(CFG)
    pw_hash = hash_password(PASSWORD)
    now = datetime.now(timezone.utc)
    await _cleanup_prior()

    created = {"seller": [], "buyer": [], "service_provider": []}
    indexed = 0

    # Pre-compute an aligned pair for the flagship demo accounts (seller01/buyer01) so
    # discovery matching surfaces them as an obvious top match for each other.
    demo_seller_fields = make_fields(CFG, "seller", rng)
    demo_buyer_fields = make_fields(CFG, "buyer", rng)
    align_demo_pair(demo_buyer_fields, demo_seller_fields)

    for slug, n in COUNTS.items():
        for i in range(1, n + 1):
            email = f"{slug}{i:02d}@{DOMAIN}"
            if await get_collection("users").find_one({"email": email}):
                created[slug].append(email)
                continue
            user = {
                "email": email, "participant_type": slug, "role": "user",
                "is_active": True, "has_onboarded": True, "password_hash": pw_hash,
                "created_at": now, "seed_marker": SEED_MARKER,
            }
            res = await get_collection("users").insert_one(user)
            uid = res.inserted_id
            if slug == "seller" and i == 1:
                fields = demo_seller_fields
            elif slug == "buyer" and i == 1:
                fields = demo_buyer_fields
            else:
                fields = make_fields(CFG, slug, rng)
            profile = await prof_repo.create_profile(
                user_id=uid, participant_type=slug, fields=fields, status="active", completeness=100
            )
            created[slug].append(email)
            try:
                from app.modules.discovery.indexer import index_profile
                await index_profile(profile, CFG)
                indexed += 1
            except Exception:
                pass

    total = sum(len(v) for v in created.values())
    print(f"\n✓ Seeded {total} active participants ({indexed} embedded for vector search)")
    for slug, emails in created.items():
        print(f"  {slug}: {len(emails)}")

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
