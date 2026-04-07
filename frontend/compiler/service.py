"""Frontend compiler orchestration — the top-level pipeline entry point."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .constants import GENERATOR_VERSION
from .generators.scaffold import emit_scaffold
from .parsers.yaml_config import MarketplaceYaml, load_marketplace_yaml
from .writer import write_frontend

logger = logging.getLogger("cosolvent.frontend_compiler")


def compile_frontend(
    *,
    openapi_path: str | Path,
    marketplace_path: str | Path,
    output_dir: str | Path = "frontend",
    clean: bool = False,
) -> dict[str, Any]:
    """Run the full frontend compiler pipeline.

    1. Parse inputs (OpenAPI + marketplace.yaml)
    2. Build intermediate representation
    3. Transform (page conventions, navigation)
    4. Generate code
    5. Write files

    Returns a summary dict with generated/removed file lists.
    """
    output = Path(output_dir).resolve()
    logger.info("Frontend compiler %s starting", GENERATOR_VERSION)
    logger.info("  openapi:      %s", openapi_path)
    logger.info("  marketplace:  %s", marketplace_path)
    logger.info("  output:       %s", output)

    # ── Stage 1: Parse ────────────────────────────────────────────────
    openapi_doc = _load_openapi(openapi_path)
    config = load_marketplace_yaml(marketplace_path)

    # ── Stage 2+3: Build IR ───────────────────────────────────────────
    from .parsers.openapi_parser import parse_openapi
    from .parsers.marketplace_parser import parse_marketplace
    from .transforms.merge import build_frontend_ir

    raw_openapi = parse_openapi(openapi_doc)
    raw_marketplace = parse_marketplace(config)
    ir = build_frontend_ir(raw_openapi, raw_marketplace, generator_version=GENERATOR_VERSION)

    logger.info(
        "IR built: %d entities, %d operations, %d pages",
        len(ir.entities),
        len(ir.operations),
        len(ir.pages),
    )

    # ── Stage 4: Generate ─────────────────────────────────────────────
    artifacts: dict[str, str] = {}

    artifacts.update(emit_scaffold())

    from .generators.types_gen import emit_types
    from .generators.schemas_gen import emit_schemas
    from .generators.api_client_gen import emit_api_clients
    from .generators.hooks_gen import emit_hooks
    from .generators.navigation_gen import emit_navigation
    from .generators.routes_gen import emit_routes
    from .generators.components_gen import emit_components

    artifacts.update(emit_types(ir))
    artifacts.update(emit_schemas(ir))
    artifacts.update(emit_api_clients(ir))
    artifacts.update(emit_hooks(ir))
    artifacts.update(emit_navigation(ir))
    artifacts.update(emit_routes(ir))
    artifacts.update(emit_components(ir))

    logger.info("Generated %d artifacts", len(artifacts))

    # ── Stage 5: Write ────────────────────────────────────────────────
    result = write_frontend(
        output,
        artifacts,
        spec_hash=ir.spec_hash,
        generator_version=GENERATOR_VERSION,
        clean=clean,
    )

    logger.info(
        "Write complete: %d generated, %d removed, %d skipped",
        len(result["generated"]),
        len(result["removed"]),
        len(result["skipped"]),
    )

    return {
        "ok": True,
        "spec_hash": ir.spec_hash,
        "generator_version": GENERATOR_VERSION,
        "output_dir": str(output),
        **result,
    }


def _load_openapi(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in OpenAPI spec: {exc}") from exc


def compute_spec_hash(openapi_doc: dict, config: MarketplaceYaml) -> str:
    """Compute a combined SHA-256 hash from both inputs for determinism checks."""
    mkt_dict = {
        "name": config.name,
        "description": config.description,
        "industry": config.industry,
        "participants": [
            {"slug": p.slug, "name": p.name, "role": p.role} for p in config.participants
        ],
    }
    canonical = json.dumps(
        {"openapi": openapi_doc, "marketplace": mkt_dict},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
