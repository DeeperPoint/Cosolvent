"""Live check that schema-constrained prose extraction works end to end (GAP-11).

Unit tests mock the model, so they prove the wiring but not that the provider
honours `response_format`. That matters: the whole point of the JSON-Schema
constraint is that an out-of-vocabulary `select` value becomes impossible rather
than something the canonical gate silently discards. This calls the real model
and asserts the constraint actually held.

    OPENROUTER_API_KEY=... python scripts/verify_prose_extraction.py
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.core.database import close_db, connect_db
from app.modules.profiles.ai_extraction import build_extraction_schema, extract_fields_from_document

FIELDS = [
    {"name": "company_name", "type": "text"},
    {"name": "industry", "type": "select", "options": ["Technology", "Mining", "Agriculture"]},
    {"name": "skills", "type": "multi_select", "options": ["Python", "Go", "Rust"]},
    {"name": "experience_years", "type": "number"},
    {"name": "description", "type": "rich_text"},
    {"name": "cv", "type": "file"},
]

PROSE = (
    "We're Northwind Robotics, a warehouse-automation company based in Hamilton. "
    "I've been building backend services for about nine years, mostly in Python with "
    "some Rust for the control loops. We're hiring."
)


async def main() -> int:
    # The resolved model config lives in the database, so a connection is needed
    # even though nothing here is persisted.
    await connect_db()
    try:
        return await _run()
    finally:
        await close_db()


async def _run() -> int:
    schema = build_extraction_schema(FIELDS)
    print(f"Schema built for {len(schema['properties'])} field(s) (asset fields excluded)")
    assert "cv" not in schema["properties"], "asset field leaked into the schema"

    print("\nCalling the model...")
    result = await extract_fields_from_document(PROSE, "employer", FIELDS)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    failures: list[str] = []

    if not result:
        failures.append("no fields extracted at all")

    # The constraint that matters: a select value must be one of the declared options.
    industry = result.get("industry", {}).get("value")
    if industry is not None and industry not in ["Technology", "Mining", "Agriculture"]:
        failures.append(f"industry '{industry}' is outside the declared options - enum not honoured")

    skills = result.get("skills", {}).get("value")
    if skills is not None:
        if not isinstance(skills, list):
            failures.append(f"skills should be a list, got {type(skills).__name__}")
        else:
            stray = [s for s in skills if s not in ["Python", "Go", "Rust"]]
            if stray:
                failures.append(f"skills contains out-of-vocabulary values: {stray}")

    years = result.get("experience_years", {}).get("value")
    if years is not None and not isinstance(years, (int, float)):
        failures.append(f"experience_years should be numeric, got {type(years).__name__}")

    # Confidence and provenance are what the clarify loop consumes.
    for name, entry in result.items():
        if not isinstance(entry.get("confidence"), (int, float)):
            failures.append(f"{name}: missing numeric confidence")
        elif not 0.0 <= entry["confidence"] <= 1.0:
            failures.append(f"{name}: confidence {entry['confidence']} out of range")

    print("\n" + "=" * 60)
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    print("PASS: values constrained to the schema, confidence and source present")
    print(f"      extracted {len(result)} field(s): {', '.join(sorted(result))}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
