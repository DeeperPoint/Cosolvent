"""Seed the machine-market (CNC capacity exchange) vertical with a synthetic,
watermarked, login-capable population — through the real GAP-9/10 import path
(see seed_demo_users.py, which this mirrors for the machine-market schema).

Run against the docker stack (with MARKETPLACE_CONFIG_PATH pointed at the
machine-market marketplace.yaml):
    POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    MARKETPLACE_CONFIG_PATH=../marketplace.yaml \
    .venv/bin/python scripts/seed_machine_market.py
"""
from __future__ import annotations

import asyncio
import os
import random

from app.core import watermark
from app.core.config import settings
from app.core.database import close_db, connect_db
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.security import hash_password
from app.modules.population.service import import_population

CFG_PATH = os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml")
PASSWORD = os.environ.get("SEED_PASSWORD", "Passw0rd!23")
DOMAIN = os.environ.get("SEED_DOMAIN", "demo-machine-market.com")

CFG = load_marketplace_config(CFG_PATH)
rng = random.Random(7)

COUNTS = {
    "machine_shop": 20,
    "buyer": 15,
    "quality_inspector": 3,
    "rigging_logistics_provider": 3,
    "cargo_insurer": 2,
    "trade_finance_provider": 2,
    "certification_body": 2,
}

SHOP_NAMES = [
    "Northshore Precision", "Kestrel Machine Works", "Ironbridge CNC", "Bluewater Tooling",
    "Sterling Precision Machining", "Redline Manufacturing", "Granite City Machine",
    "Vantage Precision Ltd", "Copperline Fabrication", "Alloy Point Machining",
    "Highwater CNC Solutions", "Meridian Precision Works", "Brightwell Machine Shop",
    "Trillium Precision", "Cascadia Machining", "Fieldstone CNC", "Longbow Precision",
    "Silverline Manufacturing", "Basecamp Machine Works", "Northgate Precision",
]
BUYER_NAMES = [
    "AeroDelta Systems", "Vertex Robotics", "Halcyon Aerospace", "Turbine Dynamics",
    "Orbital Components", "Skyline Defense Group", "Meridian Aerostructures",
    "Vantage Powertrain", "Novacore Medical Devices", "Apex Turbomachinery",
    "Frontier Robotics Inc", "Continuum Aerospace", "Blackline Automotive",
    "Ridgeview Manufacturing", "Northstar Powergen",
]
FACILITATOR_NAMES = {
    "quality_inspector": ["Precision CMM Services", "TrueMeasure Inspection", "Calibre Quality Labs",
                          "Vertex Metrology", "Ontario NDT & Inspection"],
    "rigging_logistics_provider": ["Heavylift Rigging Co", "TransIndustrial Movers", "Solid Ground Rigging",
                                   "Provincial Machinery Transport", "Trillium Heavy Haul"],
    "cargo_insurer": ["Cascade Marine & Cargo", "Northbridge Cargo Underwriters", "Assurex Industrial"],
    "trade_finance_provider": ["Meridian Trade Capital", "Ontario Factoring Partners", "Kestrel Trade Finance"],
    "certification_body": ["Great Lakes Registrar", "Dominion Certification Services", "TrueNorth QMS Audit"],
}

MACHINE_TYPES = ["vertical_machining_center", "cnc_lathe", "3_axis_mill", "4_axis_mill",
                  "5_axis_machining_center", "multiaxis_machining_center"]
TOOL_TAPERS = ["ct40", "bt40", "big_plus_no_40", "big_plus_no_50"]
DEAL_INSTRUMENTS = ["spot_purchase", "capacity_rental", "ongoing_subcontract"]
MATERIAL_GRADES = ["aluminum_7075_t6", "aluminum_6061", "ti_6al_4v", "inconel_625", "inconel_718",
                   "stainless_steel", "carbon_steel"]
MATERIAL_FAMILIES = {"aluminum_7075_t6": "aluminum_alloy", "aluminum_6061": "aluminum_alloy",
                     "ti_6al_4v": "titanium_alloy", "inconel_625": "nickel_superalloy",
                     "inconel_718": "nickel_superalloy", "stainless_steel": "steel", "carbon_steel": "steel"}
REQUIRED_PROCESSES = ["heat_treatment", "coating", "edm", "threadmilling", "inspection_cmm", "deburring"]
END_USE_SECTORS = ["aerospace", "defense", "automotive", "medical", "power_generation", "marine", "general_industrial"]
QUALITY_CERTS = ["iso_9001", "as9100d", "as9110", "as9120", "none"]
TOLERANCE_CLASSES = ["general", "tight_precision", "first_article_inspection", "statistical_sampling"]
INSPECTION_METHODS = ["cmm_report", "first_article_inspection", "statistical_sampling_plan", "visual"]
RATE_STRUCTURES = ["per_part", "per_machine_hour", "fixed_price"]
PAYMENT_TERMS = ["net_30", "net_45", "net_60", "on_delivery"]
CURRENCIES = ["cad", "usd"]
CONTRACT_STAGES = ["anonymous", "mutual_nda", "deal_context", "subcontract_agreement"]
ECONOMIC_REGIONS = ["toronto", "kitchener_waterloo_barrie", "windsor_sarnia", "hamilton_niagara",
                    "london", "ottawa", "stratford_bruce"]
BUDGET_RANGES = ["under_25k", "25k_100k", "100k_500k", "500k_2m", "2m"]
SERVICE_REGIONS = ["north_america", "south_america", "europe", "middle_east", "africa",
                   "south_asia", "east_asia", "southeast_asia", "oceania"]


def _machine_party_fields(rng: random.Random, is_buyer: bool) -> dict:
    material = rng.choice(MATERIAL_GRADES)
    fields = {
        "country": "canada",
        "machine_type": rng.sample(MACHINE_TYPES, k=rng.randint(1, 2)),
        "tool_taper": rng.sample(TOOL_TAPERS, k=rng.randint(1, 2)),
        "max_spindle_speed_rpm": rng.choice([8100, 12000, 15000, 20000, 24000]),
        "table_load_limit_kg": rng.choice([500, 1000, 1361, 2000, 3000]),
        "deal_instrument": rng.sample(DEAL_INSTRUMENTS, k=rng.randint(1, 2)),
        "material_grade": [material],
        "material_family": [MATERIAL_FAMILIES[material]],
        "required_processes": rng.sample(REQUIRED_PROCESSES, k=rng.randint(1, 3)),
        "end_use_sector": rng.sample(END_USE_SECTORS, k=rng.randint(1, 2)),
        "quality_certification": rng.sample(QUALITY_CERTS[:-1], k=rng.randint(1, 2)),
        "tolerance_class": rng.sample(TOLERANCE_CLASSES, k=rng.randint(1, 2)),
        "inspection_method": rng.sample(INSPECTION_METHODS, k=rng.randint(1, 2)),
        "rate_structure": rng.sample(RATE_STRUCTURES, k=rng.randint(1, 2)),
        "payment_terms": rng.sample(PAYMENT_TERMS, k=rng.randint(1, 2)),
        "currency": rng.choice(CURRENCIES),
        "contract_stage": "anonymous",
        "economic_region": rng.sample(ECONOMIC_REGIONS, k=rng.randint(1, 2)),
    }
    if is_buyer:
        fields["budget_range"] = rng.choice(BUDGET_RANGES)
    return fields


def _machine_shop_description(rng: random.Random, name: str, fields: dict) -> str:
    machine = fields["machine_type"][0].replace("_", " ")
    material = fields["material_grade"][0].replace("_", " ").upper()
    region = fields["economic_region"][0].replace("_", " ").title()
    certs = ", ".join(c.upper().replace("_", " ") for c in fields["quality_certification"])
    return (
        f"{name} runs {machine} capacity out of the {region} area, with recent work in "
        f"{material} for {fields['end_use_sector'][0].replace('_', ' ')} customers. "
        f"Certified: {certs}. Typical inspection: {fields['inspection_method'][0].replace('_', ' ')}."
    )


def _buyer_description(rng: random.Random, name: str, fields: dict) -> str:
    machine = fields["machine_type"][0].replace("_", " ")
    material = fields["material_grade"][0].replace("_", " ").upper()
    region = fields["economic_region"][0].replace("_", " ").title()
    return (
        f"{name} is sourcing {machine} capacity in {material} for "
        f"{fields['end_use_sector'][0].replace('_', ' ')} work, based near {region}. "
        f"Prefers {fields['rate_structure'][0].replace('_', ' ')} pricing, {fields['payment_terms'][0].replace('_', ' ')} terms."
    )


def _facilitator_fields(rng: random.Random) -> dict:
    return {
        "country": "canada",
        "service_regions": rng.sample(SERVICE_REGIONS, k=rng.randint(1, 3)),
    }


def _align_demo_pair(shop_fields: dict, buyer_fields: dict) -> None:
    """Force machine_shop01 <-> buyer01 onto matching dimensions so discovery
    surfaces them as an obvious top match (mirrors _demo_data.align_demo_pair)."""
    shared = {
        "machine_type": ["5_axis_machining_center"],
        "material_grade": ["ti_6al_4v"],
        "material_family": ["titanium_alloy"],
        "quality_certification": ["as9100d"],
        "economic_region": ["kitchener_waterloo_barrie"],
        "end_use_sector": ["aerospace"],
        "country": "canada",
    }
    for fields in (shop_fields, buyer_fields):
        fields.update({k: (list(v) if isinstance(v, list) else v) for k, v in shared.items()})


def _build_records() -> list[dict]:
    records = []
    shop_fields_01 = _machine_party_fields(rng, is_buyer=False)
    buyer_fields_01 = _machine_party_fields(rng, is_buyer=True)
    _align_demo_pair(shop_fields_01, buyer_fields_01)

    for i in range(1, COUNTS["machine_shop"] + 1):
        name = f"{SHOP_NAMES[(i - 1) % len(SHOP_NAMES)]}" + (f" {i}" if i > len(SHOP_NAMES) else "")
        fields = shop_fields_01 if i == 1 else _machine_party_fields(rng, is_buyer=False)
        fields["company_name"] = name
        fields["description"] = _machine_shop_description(rng, name, fields)
        records.append({"participant_type": "machine_shop", "external_id": f"machine_shop{i:02d}", "fields": fields})

    for i in range(1, COUNTS["buyer"] + 1):
        name = f"{BUYER_NAMES[(i - 1) % len(BUYER_NAMES)]}" + (f" {i}" if i > len(BUYER_NAMES) else "")
        fields = buyer_fields_01 if i == 1 else _machine_party_fields(rng, is_buyer=True)
        fields["company_name"] = name
        fields["description"] = _buyer_description(rng, name, fields)
        records.append({"participant_type": "buyer", "external_id": f"buyer{i:02d}", "fields": fields})

    for slug in ("quality_inspector", "rigging_logistics_provider", "cargo_insurer",
                 "trade_finance_provider", "certification_body"):
        names = FACILITATOR_NAMES[slug]
        for i in range(1, COUNTS[slug] + 1):
            name = names[(i - 1) % len(names)]
            fields = _facilitator_fields(rng)
            fields["company_name"] = name
            fields["description"] = f"{name} provides {slug.replace('_', ' ')} services across " + \
                ", ".join(r.replace("_", " ").title() for r in fields["service_regions"])
            records.append({"participant_type": slug, "external_id": f"{slug}{i:02d}", "fields": fields})

    return records


async def main():
    await connect_db()
    set_marketplace_config(CFG)

    records = _build_records()
    stamped = [watermark.stamp(r, settings.synthetic_watermark_secret) for r in records]
    pw_hash = hash_password(PASSWORD)

    res = await import_population(CFG, stamped, mode="demo", email_domain=DOMAIN, password_hash=pw_hash)

    total = res.loaded + res.updated
    print(f"\n✓ Seeded {total} participants ({res.indexed} embedded for vector search)")
    for slug, n in COUNTS.items():
        print(f"  {slug}: {n}")
    if res.rejected_watermark or res.skipped_invalid:
        print(f"  ! rejected_watermark={res.rejected_watermark} skipped_invalid={res.skipped_invalid}")
        for e in res.errors[:15]:
            print(f"    - {e}")

    print("\n─────────── LOGIN CREDENTIALS ───────────")
    print(f"  password (all users): {PASSWORD}")
    print(f"    machine_shop      →  machine_shop01@{DOMAIN}")
    print(f"    buyer             →  buyer01@{DOMAIN}")
    print(f"    quality_inspector →  quality_inspector01@{DOMAIN}")
    print("  (aligned demo pair: machine_shop01 <-> buyer01, both Ti-6Al-4V / 5-axis / AS9100D / Kitchener-Waterloo)")
    print("──────────────────────────────────────────")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
