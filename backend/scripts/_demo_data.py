"""Shared demo-profile data generation for seed_demo_users.py and enrich_demo_profiles.py.

Produces structured field values *and* a prose description that actually references
them (e.g. a seller's description names the same brand/category/condition its fields
carry), instead of one interchangeable boilerplate sentence per participant type.
This matters for two things in this marketplace: the vector-search embedding is built
from these fields (see discovery/indexer.py), so incoherent text makes semantic search
worse; and it makes seeded profiles readable in a demo instead of looking obviously fake.
"""

from __future__ import annotations

import random
from typing import Any

COMPANIES = [
    "Atlas", "Summit", "Ironclad", "Vanguard", "Meridian", "Titan", "Cascade", "Bedrock",
    "Northwind", "Keystone", "Redwood", "Granite", "Pioneer", "Sterling", "Apex", "Forge",
    "Beacon", "Harbor", "Ridgeline", "Copperfield",
]
SUFFIX = ["Machinery", "Equipment Co", "Industrial", "Trading", "Heavy Group", "Works", "Logistics"]

COUNTRY_NAMES = {
    "usa": "the United States", "canada": "Canada", "mexico": "Mexico", "germany": "Germany",
    "brazil": "Brazil", "india": "India", "china": "China", "japan": "Japan",
}
BRAND_NAMES = {
    "caterpillar": "Caterpillar", "komatsu": "Komatsu", "john_deere": "John Deere", "volvo": "Volvo",
    "hitachi": "Hitachi", "jcb": "JCB", "liebherr": "Liebherr", "doosan": "Doosan", "mitsubishi": "Mitsubishi",
}
CATEGORY_NAMES = {
    "construction": "construction", "agriculture": "agriculture", "manufacturing_cnc": "CNC manufacturing",
    "material_handling": "material handling", "mining": "mining", "power_generation": "power generation",
    "forestry": "forestry", "oil_gas": "oil & gas",
}
CONDITION_NAMES = {"new": "new", "used": "used", "refurbished": "refurbished", "parts_only": "parts-only"}
EMISSIONS_NAMES = {
    "epa_tier_2": "EPA Tier 2", "epa_tier_3": "EPA Tier 3", "epa_tier_4": "EPA Tier 4", "eu_stage_v": "EU Stage V",
}
SERVICE_NAMES = {
    "transport_carrier": "transport carrier services", "rigging_specialist": "rigging & heavy-lift services",
    "machinery_inspector": "third-party inspection", "customs_broker": "customs brokerage",
    "cargo_insurer": "cargo insurance",
}
REGION_NAMES = {
    "north_america": "North America", "south_america": "South America", "europe": "Europe",
    "middle_east": "the Middle East", "africa": "Africa", "south_asia": "South Asia",
    "east_asia": "East Asia", "southeast_asia": "Southeast Asia", "oceania": "Oceania",
}
CARRIER_NAMES = {
    "dot_compliant": "DOT compliance", "adr_eu": "ADR (EU)", "tir_carnet": "TIR Carnet",
    "iso_9001": "ISO 9001", "c_tpat": "C-TPAT",
}
BUDGET_NAMES = {
    "under_25k": "under $25k", "25k_100k": "$25k–100k", "100k_500k": "$100k–500k",
    "500k_2m": "$500k–2M", "2m": "$2M+",
}


def _label(mapping: dict[str, str], value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        names = [mapping.get(v, str(v).replace("_", " ")) for v in value]
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + f", and {names[-1]}"
    return mapping.get(value, str(value).replace("_", " "))


def _pick(rng: random.Random, field: Any) -> Any:
    opts = list(field.options or [])
    if not opts:
        return None
    if field.type == "multi_select":
        k = rng.randint(2, min(3, len(opts)))
        return rng.sample(opts, k)
    return rng.choice(opts)


SELLER_OPENERS = [
    "{company} has moved {condition} {category} equipment out of {country} for {years} years",
    "{company} stocks {condition} {category} machinery sourced across {country}",
    "Based in {country}, {company} specializes in {condition} {category} equipment",
]
SELLER_CLOSERS = [
    "Every unit ships with full maintenance records and our standard 90-day powertrain warranty.",
    "Inventory turns fast — most listings sell within three weeks of going live.",
    "All units are inspected on-site before listing and priced against current resale benchmarks.",
]


def _seller_description(rng: random.Random, fields: dict) -> str:
    company = fields.get("company_name", "This seller")
    years = rng.randint(4, 25)
    opener = rng.choice(SELLER_OPENERS).format(
        company=company,
        category=_label(CATEGORY_NAMES, fields.get("category")),
        country=_label(COUNTRY_NAMES, fields.get("country")),
        condition=_label(CONDITION_NAMES, fields.get("condition")),
        years=years,
    )
    mid = f"The current lineup leans heavily on {_label(BRAND_NAMES, fields.get('brand'))}"
    if fields.get("emissions_standard"):
        mid += f", with most units meeting {_label(EMISSIONS_NAMES, fields['emissions_standard'])} emissions requirements"
    mid += "."
    return f"{opener}. {mid} {rng.choice(SELLER_CLOSERS)}"


BUYER_OPENERS = [
    "{company} operates active job sites across {country} and buys {condition} {category} equipment on a rolling basis",
    "{company} is sourcing {condition} {category} machinery for fleet renewal across {country}",
    "As a {category} operator based in {country}, {company} regularly adds {condition} equipment to its fleet",
]
BUYER_CLOSERS = [
    "Deals typically close within two to four weeks of an accepted offer.",
    "Financing is pre-arranged, so verified listings can move to close quickly.",
    "Preference goes to sellers who can provide full service history.",
]


def _buyer_description(rng: random.Random, fields: dict) -> str:
    company = fields.get("company_name", "This buyer")
    opener = rng.choice(BUYER_OPENERS).format(
        company=company,
        country=_label(COUNTRY_NAMES, fields.get("country")),
        condition=_label(CONDITION_NAMES, fields.get("condition")),
        category=_label(CATEGORY_NAMES, fields.get("category")),
    )
    mid = f"Preferred brands include {_label(BRAND_NAMES, fields.get('brand'))}"
    if fields.get("emissions_standard"):
        mid += f", and units must meet {_label(EMISSIONS_NAMES, fields['emissions_standard'])} emissions requirements"
    if fields.get("budget_range"):
        mid += f". Typical order size is {BUDGET_NAMES.get(fields['budget_range'], fields['budget_range'])}"
    mid += "."
    return f"{opener}. {mid} {rng.choice(BUYER_CLOSERS)}"


SERVICE_OPENERS = [
    "{company} supports machinery trades across {regions} with {services}",
    "{company} is a {services} provider covering {regions}",
]


def _service_description(rng: random.Random, fields: dict) -> str:
    company = fields.get("company_name", "This provider")
    opener = rng.choice(SERVICE_OPENERS).format(
        company=company,
        services=_label(SERVICE_NAMES, fields.get("services_offered")),
        regions=_label(REGION_NAMES, fields.get("service_regions")),
    )
    tail = ""
    if fields.get("carrier_credentials"):
        tail += f" Certifications include {_label(CARRIER_NAMES, fields['carrier_credentials'])}."
    if fields.get("cargo_insurance_usd"):
        tail += f" Cargo coverage up to ${int(fields['cargo_insurance_usd']):,}."
    return f"{opener}.{tail}"


def make_fields(cfg: Any, slug: str, rng: random.Random) -> dict[str, Any]:
    """Generate a full, internally-consistent field set for one profile."""
    schema = cfg.profile_schemas[slug]
    fields: dict[str, Any] = {}
    for f in schema.all_fields:
        if f.type in ("files", "file") or f.name == "description":
            continue
        if f.name == "company_name":
            fields[f.name] = f"{rng.choice(COMPANIES)} {rng.choice(SUFFIX)}"
        elif f.name == "operating_hours":
            bounds = {
                "new": (0, 500), "used": (1500, 9000),
                "refurbished": (3000, 12000), "parts_only": (8000, 20000),
            }
            lo, hi = bounds.get(fields.get("condition"), (500, 12000))
            fields[f.name] = rng.randint(lo, hi)
        elif f.name == "cargo_insurance_usd":
            fields[f.name] = rng.choice([250_000, 500_000, 1_000_000, 2_000_000, 5_000_000])
        elif f.type == "number":
            fields[f.name] = rng.choice([1200, 3500, 8000, 15000, 40000])
        elif f.type in ("select", "multi_select"):
            v = _pick(rng, f)
            if v is not None:
                fields[f.name] = v

    if slug == "seller":
        fields["description"] = _seller_description(rng, fields)
    elif slug == "buyer":
        fields["description"] = _buyer_description(rng, fields)
    elif slug == "service_provider":
        fields["description"] = _service_description(rng, fields)
    return fields


def align_demo_pair(buyer_fields: dict, seller_fields: dict) -> None:
    """Force buyer01 <-> seller01 onto the same country/category/brand/condition/
    emissions so marketplace.yaml's discovery.matching.per_target (see matching.py)
    scores them as an unambiguous, demoable top match. `condition="used"` also
    satisfies the seller-side hard gate (working_machines_only)."""
    country = "usa"
    category = ["construction", "mining"]
    brand = ["caterpillar", "komatsu"]
    condition = "used"
    emissions = "epa_tier_4"

    for fields in (buyer_fields, seller_fields):
        fields["country"] = country
        fields["category"] = list(category)
        fields["brand"] = list(brand)
        fields["condition"] = condition
        fields["emissions_standard"] = emissions

    seller_fields["company_name"] = "Titan Heavy Equipment"
    buyer_fields["company_name"] = "Meridian Construction Group"
    buyer_fields["budget_range"] = "100k_500k"

    seller_fields["description"] = (
        "Titan Heavy Equipment stocks used construction and mining machinery sourced across the "
        "United States, with a lineup built around Caterpillar and Komatsu excavators, dozers, and "
        "loaders. Every unit meets EPA Tier 4 emissions requirements, ships with full maintenance "
        "records, and carries our standard 90-day powertrain warranty. Inventory turns fast — "
        "most listings sell within three weeks of going live."
    )
    buyer_fields["description"] = (
        "Meridian Construction Group operates active construction and mining job sites across the "
        "United States and buys used Caterpillar and Komatsu equipment on a rolling basis. Every "
        "purchase must meet EPA Tier 4 emissions requirements. Typical order size is $100k–500k, "
        "financing is pre-arranged, and deals close within two to four weeks of an accepted offer."
    )
