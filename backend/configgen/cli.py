"""CLI: generate a marketplace.yaml from a CommonContext domain schema.

    python -m configgen --domain-schema <vertical>_schema.yaml -o marketplace.yaml

Add ``--enrich`` to use an LLM (OpenRouter) to refine and repair; otherwise the run
is fully deterministic and offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .generate import generate_from_schema
from .validate import ConfigValidationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="configgen",
        description="Generate a Cosolvent marketplace.yaml from a domain schema.",
    )
    parser.add_argument("--domain-schema", required=True, help="Path to <vertical>_schema.yaml (CommonContext output)")
    parser.add_argument("-o", "--output", default="marketplace.yaml", help="Output path (default: marketplace.yaml)")
    parser.add_argument("--name", help="Marketplace display name (default: derived from vertical)")
    parser.add_argument("--industry", help="Industry label (default: derived from vertical)")
    parser.add_argument("--enrich", action="store_true", help="Use OpenRouter LLM for repair (needs OPENROUTER_API_KEY)")
    parser.add_argument("--stdout", action="store_true", help="Print YAML to stdout instead of writing a file")
    parser.add_argument("--provenance", action="store_true", help="Also print the field->source provenance map")
    args = parser.parse_args(argv)

    llm_client = None
    if args.enrich:
        from .llm import OpenRouterClient

        llm_client = OpenRouterClient()

    try:
        result = generate_from_schema(
            args.domain_schema, name=args.name, industry=args.industry, llm_client=llm_client
        )
    except ConfigValidationError as e:
        print("Generation failed validation after repairs:", file=sys.stderr)
        for err in e.errors:
            loc = ".".join(str(p) for p in err.get("loc", []))
            print(f"  - {loc}: {err.get('msg')}", file=sys.stderr)
        return 1

    yaml_text = result.to_yaml()
    if args.stdout:
        print(yaml_text)
    else:
        Path(args.output).write_text(yaml_text)
        types = ", ".join(f"{p.name} ({p.role})" for p in result.market.participants)
        print(f"✓ Wrote {args.output} — validates against MarketplaceConfig")
        print(f"  Participant types: {types}")
        for p in result.market.participants:
            if p.collapsed_subtypes:
                print(f"  ⚠ '{p.slug}' collapsed {len(p.collapsed_subtypes)} subtypes "
                      f"(MVP 3-type cap): {', '.join(p.collapsed_subtypes)}")

    if args.provenance:
        print("\nProvenance (field -> source):")
        for field_key, src in sorted(result.provenance.items()):
            print(f"  {field_key} <- {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
