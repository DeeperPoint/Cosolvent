"""POC: seed synthetic participants into the running Machinery Trade marketplace.

Populates the empty thin market so the storefront/discovery can be demoed.
Reuses Cosolvent's own create_user / create_profile / index_profile so the rows
are indistinguishable from real ones EXCEPT a top-level ``is_synthetic: true``
marker on both the user and profile ``data`` (per the ClientSynth integration
notes — never mix with real users; this enables clean teardown).

This is the Cosolvent-side import script (C0.4) the integration doc describes,
but it generates conforming values directly instead of consuming a ClientSynth
export. Swapping in a ClientSynth JSON export later is a localized change.

Run inside the api container (has app code + env + DB):
    docker exec -w /project/backend cosolvent-api-1 python scripts/seed_synthetic_poc.py [seed|wipe]
"""
from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import connect_db, close_db, get_collection
from app.core.marketplace_config import load_marketplace_config
from app.core.security import hash_password
from app.modules.auth.repository import create_user
from app.modules.profiles.repository import create_profile
from app.modules.discovery.indexer import index_profile
from app.modules.discovery.vector_service import delete_profile_vector
from app.modules.ai.repository import upsert_llm_settings

# ── value pools (conform EXACTLY to marketplace.yaml options) ───────────────
COUNTRIES = ["USA", "Canada", "Mexico", "Germany", "Brazil", "India", "China", "Japan"]
SP_SERVICES = ["Broker", "Inspection Service", "Financing Provider", "Logistics Provider", "Dispute Manager"]
SP_REGIONS = ["North America", "South America", "Europe", "Middle East", "Africa",
              "South Asia", "East Asia", "Southeast Asia", "Oceania"]
SP_PRIMARY = ["north_america", "south_america", "europe", "middle_east", "africa", "asia", "oceania"]
CUSTOMS = ["buyer_handles", "seller_handles", "platform_assisted", "broker_managed"]
DELIVERY = ["not_started", "in_logistics", "in_transit", "delivered", "completed"]
BUDGET = ["Under 25k", "25k-100k", "100k-500k", "500k-2M", "2M+"]
MACHINES = ["CNC machining centers", "hydraulic presses", "industrial lathes",
            "injection molding machines", "packaging lines", "conveyor systems",
            "laser cutting systems", "welding robots", "textile machinery",
            "food-processing equipment", "sheet-metal brakes", "surface grinders"]
PREFIX = ["Apex", "Vanguard", "Summit", "Ironclad", "Precision", "Continental",
          "Meridian", "Atlas", "Pioneer", "Titan", "Keystone", "Cascade", "Vertex",
          "Sterling", "Granite", "Northwind", "Redstone", "Halcyon", "Brightwork", "Forge"]
CORE = ["Machinery", "Industrial", "Engineering", "Fabrication", "Equipment",
        "Manufacturing", "Tooling", "Systems", "Works", "Dynamics", "Automation", "Metalworks"]
SUFFIX = ["Inc.", "LLC", "Co.", "Ltd.", "Group", "Corp.", "GmbH", "Industries"]


def company_name() -> str:
    return f"{random.choice(PREFIX)} {random.choice(CORE)} {random.choice(SUFFIX)}"


def seller_fields() -> tuple[dict, str]:
    name, country = company_name(), random.choice(COUNTRIES)
    m1, m2 = random.sample(MACHINES, 2)
    desc = (f"{name} manufactures and exports {m1} and {m2} for industrial buyers, "
            f"with quality-certified production and global shipping.")
    fields = {"company_name": name, "country": country, "description": desc}
    ai = (f"{name} is a {country}-based machinery seller specializing in {m1} and {m2}. "
          f"It serves industrial buyers worldwide with certified equipment and export experience.")
    return fields, ai


def buyer_fields() -> tuple[dict, str]:
    name, country = company_name(), random.choice(COUNTRIES)
    m1, m2 = random.sample(MACHINES, 2)
    budget = random.choice(BUDGET)
    desc = f"{name} sources {m1} and {m2} for its production facilities and is actively evaluating suppliers."
    fields = {"company_name": name, "country": country, "description": desc, "budget_range": budget}
    ai = (f"{name} is a {country}-based industrial buyer seeking {m1} and {m2}, "
          f"with a typical procurement budget of {budget}.")
    return fields, ai


def service_provider_fields() -> tuple[dict, str]:
    name, country = company_name(), random.choice(COUNTRIES)
    services = random.sample(SP_SERVICES, random.randint(1, 3))
    regions = random.sample(SP_REGIONS, random.randint(1, 3))
    fields = {
        "company_name": name,
        "country": country,
        "description": f"{name} provides {', '.join(services)} services across {', '.join(regions)} for machinery trade.",
        "services_offered": services,
        "service_regions": regions,
        "region": random.choice(SP_PRIMARY),
        "customs_handling": random.choice(CUSTOMS),
        "delivery_status": random.choice(DELIVERY),
    }
    ai = (f"{name} is a {country}-based service provider offering {', '.join(services)} "
          f"across {', '.join(regions)}, supporting machinery trade deals end to end.")
    return fields, ai


GENERATORS = {"seller": seller_fields, "buyer": buyer_fields, "service_provider": service_provider_fields}
PLAN = {"seller": 12, "service_provider": 6, "buyer": 4}


async def seed() -> None:
    config = load_marketplace_config(settings.marketplace_config_path)

    # Point the marketplace's AI at OpenRouter so embeddings (and RAG) work with
    # the available key. Default is provider=openai, but OPENAI_API_KEY is empty.
    await upsert_llm_settings({
        "embedding_provider": "openrouter",
        "embedding_model": "openai/text-embedding-3-small",
        "embedding_dimensions": 1536,
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
    })
    print("AI settings -> OpenRouter (embeddings: openai/text-embedding-3-small)")

    created, indexed = 0, 0
    for slug, count in PLAN.items():
        gen = GENERATORS[slug]
        for _ in range(count):
            fields, ai_profile = gen()
            # NB: Cosolvent's auth validates email format and REJECTS reserved TLDs
            # like .test (the integration doc's @digital-twin.test can't log in).
            email = f"synthetic-{slug}-{uuid.uuid4().hex[:8]}@digitaltwin-demo.com"
            user = await create_user(
                email=email,
                password_hash=hash_password("synthetic-Demo-123!"),
                participant_type=slug,
                role="user",
            )
            await get_collection("users").find_one_and_update(
                {"_id": user["_id"]},
                {"$set": {"is_synthetic": True, "has_onboarded": True}},
            )
            profile = await create_profile(
                user_id=str(user["_id"]),
                participant_type=slug,
                fields=fields,
                status="active",
                ai_profile=ai_profile,
                ai_profile_status="approved",
                ai_profile_updated_at=datetime.now(timezone.utc),
                completeness=100,
            )
            await get_collection("profiles").find_one_and_update(
                {"_id": profile["_id"]},
                {"$set": {"is_synthetic": True}},
            )
            created += 1
            try:
                await index_profile(profile, config)
                indexed += 1
            except Exception as exc:  # keep going; profile still exists, just unsearchable
                print(f"  ! index failed for {slug} {profile['_id']}: {exc}")
    print(f"Seeded {created} synthetic profiles ({indexed} indexed) across {PLAN}")


async def wipe() -> None:
    profs = await get_collection("profiles").find({"is_synthetic": True}).to_list(length=10000)
    for p in profs:
        await delete_profile_vector(str(p["_id"]))
        await get_collection("profiles").delete_one({"_id": p["_id"]})
    users = await get_collection("users").find({"is_synthetic": True}).to_list(length=10000)
    for u in users:
        await get_collection("users").delete_one({"_id": u["_id"]})
    print(f"Wiped {len(profs)} synthetic profiles and {len(users)} synthetic users")


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    await connect_db()
    try:
        await (wipe() if mode == "wipe" else seed())
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
