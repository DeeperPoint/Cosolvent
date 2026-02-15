from __future__ import annotations

from pathlib import Path

from app.compiler import CompileOptions, check_compile_sync, compile_marketplace, load_config


def run_compile(
    *,
    config_path: str,
    mode: str,
    export_enabled: bool,
    export_dir: str,
    check: bool,
) -> bool:
    config = load_config(config_path)
    options = CompileOptions(
        mode=mode,  # type: ignore[arg-type]
        export_enabled=export_enabled,
        export_dir=export_dir,
        overwrite_policy="managed",
    )

    if check:
        result = check_compile_sync(config=config, options=options, project_root=Path.cwd())
        print(f"in_sync={result['in_sync']}")
        print(f"expected_spec_hash={result['expected_spec_hash']}")
        print(f"current_manifest_hash={result['current_manifest_hash']}")
        if result["drift_files"]:
            print("drift_files:")
            for item in result["drift_files"]:
                print(f"  - {item}")
        return bool(result["in_sync"])

    result = compile_marketplace(config=config, options=options, project_root=Path.cwd())
    print(f"spec_hash={result['spec_hash']}")
    print(f"migration_revision={result['migration_revision']}")
    if result["generated_files"]:
        print("generated_files:")
        for item in result["generated_files"]:
            print(f"  - {item}")
    if result["removed_files"]:
        print("removed_files:")
        for item in result["removed_files"]:
            print(f"  - {item}")
    if result.get("export_path"):
        print(f"export_path={result['export_path']}")
    if result["warnings"]:
        print("warnings:")
        for item in result["warnings"]:
            print(f"  - {item}")
    return True

