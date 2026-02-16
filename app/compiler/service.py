from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.core.marketplace_config import MarketplaceConfig, load_marketplace_config, set_marketplace_config

from .exporter import create_export_archive
from .ir import CompileOptions
from .manifest import MANIFEST_PATH, load_manifest, stale_managed_files, write_manifest
from .normalize import normalize_to_ir
from .render import render_artifacts
from .writer import write_artifacts

_CODEBASE_ROOT = Path(__file__).resolve().parents[2]


def compile_marketplace(
    *,
    config: MarketplaceConfig | dict[str, Any],
    options: CompileOptions,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    _validate_compile_options(options)

    ir = normalize_to_ir(config, project_root=root, mode=options.mode)
    artifacts, migration_revision, _migration_path = render_artifacts(ir)
    generated_files, removed_files = write_artifacts(
        root,
        artifacts,
        keep_paths={str(MANIFEST_PATH), "openapi/generated_openapi.json"},
    )

    openapi_rel = "openapi/generated_openapi.json"
    include_generated_aliases = _can_include_generated_aliases(root)
    openapi_doc = _build_openapi_doc(
        MarketplaceConfig(**ir.config), include_generated_aliases=include_generated_aliases
    )
    if include_generated_aliases:
        _assert_generated_alias_contracts(openapi_doc, [role.slug for role in ir.roles])
    openapi_text = json.dumps(openapi_doc, indent=2, sort_keys=True)
    (root / openapi_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / openapi_rel).write_text(openapi_text, encoding="utf-8")
    generated_files.append(openapi_rel)

    warnings: list[str] = []
    if options.mode == "strict":
        warnings.append(
            "Strict mode currently reuses shared runtime tables; per-role projection tables are planned next."
        )

    export_path = None
    if options.export_enabled:
        export_path = create_export_archive(root, export_dir=options.export_dir, spec_hash=ir.spec_hash)

    manifest = write_manifest(
        root,
        spec_hash=ir.spec_hash,
        mode=options.mode,
        generated_files=sorted(set(generated_files + [str(MANIFEST_PATH)])),
        migration_revision=migration_revision,
        export_path=export_path,
    )

    return {
        "ok": True,
        "spec_hash": ir.spec_hash,
        "generated_files": manifest["generated_files"],
        "removed_files": removed_files,
        "migration_revision": migration_revision,
        "export_path": export_path,
        "warnings": warnings,
    }


def check_compile_sync(
    *,
    config: MarketplaceConfig | dict[str, Any],
    options: CompileOptions,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    _validate_compile_options(options)

    ir = normalize_to_ir(config, project_root=root, mode=options.mode)
    artifacts, _migration_revision, _migration_path = render_artifacts(ir)
    include_generated_aliases = _can_include_generated_aliases(root)
    expected_openapi = json.dumps(
        _build_openapi_doc(MarketplaceConfig(**ir.config), include_generated_aliases=include_generated_aliases),
        indent=2,
        sort_keys=True,
    )
    if include_generated_aliases:
        _assert_generated_alias_contracts(json.loads(expected_openapi), [role.slug for role in ir.roles])
    artifacts["openapi/generated_openapi.json"] = expected_openapi

    drift_files: list[str] = []
    for rel, expected_content in artifacts.items():
        target = root / rel
        if not target.exists():
            drift_files.append(rel)
            continue
        current = target.read_text(encoding="utf-8")
        if current != expected_content:
            drift_files.append(rel)

    stale = stale_managed_files(root, set(artifacts.keys()) | {str(MANIFEST_PATH)})
    drift_files.extend(stale)

    manifest = load_manifest(root)
    current_manifest_hash = manifest.get("spec_hash") if manifest else None
    if current_manifest_hash != ir.spec_hash:
        drift_files.append(str(MANIFEST_PATH))

    deduped = sorted(set(drift_files))
    return {
        "in_sync": len(deduped) == 0,
        "expected_spec_hash": ir.spec_hash,
        "current_manifest_hash": current_manifest_hash,
        "drift_files": deduped,
    }


def load_config(path: str | Path) -> MarketplaceConfig:
    return load_marketplace_config(path)


def _validate_compile_options(options: CompileOptions) -> None:
    if options.overwrite_policy != "managed":
        raise ValueError("overwrite_policy must be 'managed'")
    if options.mode not in ("mvp", "strict"):
        raise ValueError("mode must be 'mvp' or 'strict'")


def _can_include_generated_aliases(root: Path) -> bool:
    """Only include import-based generated aliases when compiling in this codebase root.

    OpenAPI generation imports `app.generated.role_alias_router` as a Python module.
    That module import resolves against the currently-running codebase, not an arbitrary
    temporary `project_root`. Restricting this avoids false failures in temp-dir tests.
    """
    return root == _CODEBASE_ROOT and (root / "app/generated/role_alias_router.py").exists()


def _build_openapi_doc(
    config: MarketplaceConfig, *, include_generated_aliases: bool = True
) -> dict[str, Any]:
    set_marketplace_config(config)
    app = FastAPI(
        title=config.marketplace.name,
        description=config.marketplace.description,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    from app.modules.admin.router import router as admin_router
    from app.modules.ai.router import router as ai_router
    from app.modules.auth.router import router as auth_router
    from app.modules.communication.router import router as comms_router
    from app.modules.discovery.router import router as discovery_router
    from app.modules.files.router import router as files_router
    from app.modules.notifications.router import router as notif_router
    from app.modules.profiles.router import router as profiles_router
    from app.modules.setup.router import router as setup_router

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(profiles_router, prefix="/api/profiles", tags=["profiles"])
    app.include_router(files_router, prefix="/api/files", tags=["files"])
    app.include_router(comms_router, prefix="/api", tags=["communication"])
    app.include_router(discovery_router, prefix="/api/search", tags=["discovery"])
    app.include_router(notif_router, prefix="/api/notifications", tags=["notifications"])
    app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(setup_router, tags=["setup"])

    if include_generated_aliases:
        try:
            from app.generated.role_alias_router import router as generated_role_router

            app.include_router(generated_role_router)
        except Exception:
            # If generated aliases are not available yet we still emit base OpenAPI.
            pass
    return app.openapi()


def _assert_generated_alias_contracts(openapi_doc: dict[str, Any], role_slugs: list[str]) -> None:
    paths = openapi_doc.get("paths", {})
    missing: list[str] = []

    def _op(path: str, method: str) -> dict[str, Any] | None:
        operation = paths.get(path, {}).get(method)
        if operation is None:
            missing.append(f"{method.upper()} {path}: operation missing")
            return None
        return operation

    def _require_response_schema(path: str, method: str) -> None:
        operation = _op(path, method)
        if operation is None:
            return
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if not schema:
            missing.append(f"{method.upper()} {path}: 200 response schema missing")

    def _require_request_schema(path: str, method: str) -> None:
        operation = _op(path, method)
        if operation is None:
            return
        schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if not schema:
            missing.append(f"{method.upper()} {path}: request body schema missing")

    for role_slug in role_slugs:
        base = f"/api/roles/{role_slug}"
        _require_response_schema(f"{base}/register", "post")
        _require_response_schema(f"{base}/draft", "get")
        _require_request_schema(f"{base}/draft", "put")
        _require_response_schema(f"{base}/draft", "put")
        _require_response_schema(f"{base}/draft/submit", "post")
        _require_response_schema(f"{base}/me", "get")
        _require_response_schema(f"{base}/{{profile_id}}", "get")
        _require_request_schema(f"{base}/{{profile_id}}", "put")
        _require_response_schema(f"{base}/{{profile_id}}", "put")
        _require_response_schema(f"{base}/{{profile_id}}/ai-generate", "post")
        _require_response_schema(f"{base}/{{profile_id}}/ai-approve", "post")
        _require_response_schema(f"{base}/{{profile_id}}/ai-reject", "post")

    if missing:
        formatted = "\n".join(f"- {item}" for item in missing)
        raise ValueError(f"Generated role alias OpenAPI contract is incomplete:\n{formatted}")
