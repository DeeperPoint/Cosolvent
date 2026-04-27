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
    agent_fill: bool = False,
    agent_model: str = "anthropic/claude-sonnet-4",
    agent_timeout_seconds: int = 120,
    agent_max_attempts: int = 2,
    verify_build: bool = False,
    check: bool = False,
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

    if check:
        from .writer import check_manifest_sync

        ok, reason = check_manifest_sync(output, ir.spec_hash)
        if not ok:
            raise ValueError(reason)
        return {
            "ok": True,
            "spec_hash": ir.spec_hash,
            "generator_version": GENERATOR_VERSION,
            "output_dir": str(output),
            "generated": [],
            "removed": [],
            "skipped": [],
            "agent_fill_enabled": bool(agent_fill),
            "agent_model": agent_model,
            "verified": False,
        }

    logger.info(
        "IR built: %d entities, %d operations, %d pages",
        len(ir.entities),
        len(ir.operations),
        len(ir.pages),
    )

    # ── Stage 4: Generate ─────────────────────────────────────────────
    artifacts: dict[str, str] = {}

    artifacts.update(emit_scaffold(theme=ir.theme))

    from .generators.types_gen import emit_types
    from .generators.schemas_gen import emit_schemas
    from .generators.api_client_gen import emit_api_clients
    from .generators.hooks_gen import emit_hooks
    from .generators.convenience_hooks_gen import emit_convenience_hooks
    from .generators.navigation_gen import emit_navigation
    from .generators.routes_gen import emit_routes
    from .generators.components_gen import emit_components
    from .generators.operations_manifest_gen import emit_operations_manifest
    from .generators.api_explorer_gen import emit_api_explorer_page

    artifacts.update(emit_types(ir))
    artifacts.update(emit_schemas(ir))
    artifacts.update(emit_api_clients(ir))
    artifacts.update(emit_hooks(ir))
    artifacts.update(emit_convenience_hooks(ir))
    artifacts.update(emit_navigation(ir))
    artifacts.update(emit_routes(ir))
    artifacts.update(emit_components(ir))
    artifacts.update(emit_operations_manifest(ir))
    artifacts.update(emit_api_explorer_page(ir))

    # Pre-wire every page's relevant hooks (per ``_PAGE_OPERATION_RULES``) so
    # they are imported and declared in scope BEFORE the AGENT_FILL marker.
    # The marker contract requires JSX-only content, so hooks have to live
    # outside the marker — running this pre-fill keeps ``--agent-fill`` from
    # having to add imports of its own.
    from .transforms.hook_wiring import augment_pages_with_relevant_hooks

    artifacts = augment_pages_with_relevant_hooks(artifacts, ir)

    logger.info("Generated %d artifacts", len(artifacts))

    filled_files: list[str] = []
    prompt_hash: str | None = None
    verified = False
    verification_errors: str | None = None

    fill_attempts = max(1, int(agent_max_attempts))
    feedback: str | None = None
    current_artifacts = artifacts
    for attempt in range(1, fill_attempts + 1):
        if agent_fill:
            from .frontend_agent import AgentFillOptions, run_agent_fill

            fill_result = run_agent_fill(
                current_artifacts,
                ir,
                AgentFillOptions(
                    enabled=True,
                    model=agent_model,
                    timeout_seconds=agent_timeout_seconds,
                ),
                feedback=feedback,
            )
            current_artifacts = fill_result.artifacts
            filled_files = sorted(set(filled_files) | set(fill_result.filled_files))
            prompt_hash = fill_result.prompt_hash or prompt_hash

        if not verify_build:
            break

        from .verify import run_frontend_verification

        verify_result = run_frontend_verification(output, current_artifacts)
        verified = verify_result.ok
        if verified:
            verification_errors = None
            break
        verification_errors = verify_result.summary
        feedback = verify_result.summary
        logger.warning("Agent fill verification failed on attempt %d: %s", attempt, verification_errors)
        if not agent_fill:
            break

    artifacts = current_artifacts

    # ── Stage 5: Write ────────────────────────────────────────────────
    result = write_frontend(
        output,
        artifacts,
        spec_hash=ir.spec_hash,
        generator_version=GENERATOR_VERSION,
        clean=clean,
        force_overwrite_paths=set(filled_files),
        manifest_extra={
            "agent_fill_enabled": bool(agent_fill),
            "agent_model": agent_model if agent_fill else None,
            "agent_filled_files": filled_files,
            "agent_prompt_hash": prompt_hash,
            "verified": verified,
            "verification_errors": verification_errors,
        },
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
        "agent_fill_enabled": bool(agent_fill),
        "agent_model": agent_model if agent_fill else None,
        "agent_filled_files": filled_files,
        "verify_requested": bool(verify_build),
        "verified": verified,
        "verification_errors": verification_errors,
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
