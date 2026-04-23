from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.compiler import CompileOptions, check_compile_sync, compile_marketplace
from app.compiler.manifest import write_manifest
from app.compiler.normalize import normalize_to_ir
from app.compiler.writer import write_artifacts
from app.core.marketplace_config import MarketplaceConfig, get_marketplace_config, set_marketplace_config

FIXTURES = Path(__file__).resolve().parents[1] / "test_config"


def _reorder(value):
    if isinstance(value, dict):
        return {k: _reorder(v) for k, v in reversed(list(value.items()))}
    if isinstance(value, list):
        return [_reorder(v) for v in value]
    return value


def test_spec_hash_is_stable_for_key_ordering(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "agriculture.yaml").read_text(encoding="utf-8"))
    shuffled = _reorder(raw)

    ir_a = normalize_to_ir(raw, project_root=tmp_path)
    ir_b = normalize_to_ir(shuffled, project_root=tmp_path)

    assert ir_a.spec_hash == ir_b.spec_hash


def test_reserved_slug_is_rejected(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))

    old_slug = raw["participant_types"][0]["slug"]
    raw["participant_types"][0]["slug"] = "admin"
    raw["profile_schemas"]["admin"] = raw["profile_schemas"].pop(old_slug)
    raw["onboarding"]["admin"] = raw["onboarding"].pop(old_slug)
    raw["discovery"]["searchable_types"] = [
        "admin" if slug == old_slug else slug
        for slug in raw["discovery"]["searchable_types"]
    ]
    for rule in raw["communication"]["conversation_rules"]:
        if rule["initiator"] == old_slug:
            rule["initiator"] = "admin"
        if rule["receiver"] == old_slug:
            rule["receiver"] = "admin"

    with pytest.raises(ValueError, match="reserved"):
        normalize_to_ir(raw, project_root=tmp_path)


def test_writer_prunes_stale_managed_files_only(tmp_path: Path):
    stale = tmp_path / "app" / "generated" / "stale.py"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale = True\n", encoding="utf-8")

    manual = tmp_path / "app" / "custom" / "manual.py"
    manual.parent.mkdir(parents=True, exist_ok=True)
    manual.write_text("manual = True\n", encoding="utf-8")

    write_manifest(
        tmp_path,
        spec_hash="oldhash",
        mode="mvp",
        generated_files=["app/generated/stale.py", "app/custom/manual.py", "generated/manifest.json"],
        migration_revision="mkt_old",
        export_path=None,
    )

    _generated, removed = write_artifacts(
        tmp_path,
        {"app/generated/new.py": "new = True\n"},
        keep_paths={"generated/manifest.json"},
    )

    assert "app/generated/stale.py" in removed
    assert not stale.exists()
    assert manual.exists()


def test_compile_marketplace_writes_managed_artifacts(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    result = compile_marketplace(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["migration_revision"].startswith("mkt_")
    assert "app/generated/role_alias_router.py" in result["generated_files"]
    assert "app/generated/enums.py" in result["generated_files"]
    assert (tmp_path / "generated" / "manifest.json").exists()
    assert (tmp_path / "app" / "generated" / "enums.py").exists()
    assert (tmp_path / "openapi" / "generated_openapi.json").exists()


def test_generated_role_alias_router_has_explicit_models(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    compile_marketplace(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    router_text = (tmp_path / "app" / "generated" / "role_alias_router.py").read_text(encoding="utf-8")

    for role_slug in ("seller", "buyer"):
        # Register is rendered as a multi-line decorator (response_model +
        # status_code=201 + summary). Assert the important tokens are present.
        assert f'"/api/roles/{role_slug}/register"' in router_text
        assert "status_code=201" in router_text
        assert f'summary="Register {role_slug} profile"' in router_text
        assert f'@router.get("/api/roles/{role_slug}/draft", response_model=' in router_text
        assert f'@router.put("/api/roles/{role_slug}/draft", response_model=' in router_text
        assert f'@router.post("/api/roles/{role_slug}/draft/submit", response_model=' in router_text
        assert f'@router.get("/api/roles/{role_slug}/me", response_model=' in router_text
        assert f'@router.get("/api/roles/{role_slug}/{{profile_id}}", response_model=' in router_text
        assert f'@router.put("/api/roles/{role_slug}/{{profile_id}}", response_model=' in router_text
        assert f'@router.post("/api/roles/{role_slug}/{{profile_id}}/ai-generate", response_model=' in router_text
        assert f'@router.post("/api/roles/{role_slug}/{{profile_id}}/ai-approve", response_model=' in router_text
        assert f'@router.post("/api/roles/{role_slug}/{{profile_id}}/ai-reject", response_model=' in router_text

    assert "ParticipantTypeEnum" in router_text
    assert "DraftStatusEnum" in router_text
    assert "ProfileStatusEnum" in router_text
    assert "AIProfileStatusEnum" in router_text


def test_select_and_multi_select_generate_option_enums(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "agriculture.yaml").read_text(encoding="utf-8"))
    compile_marketplace(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    enums_text = (tmp_path / "app" / "generated" / "enums.py").read_text(encoding="utf-8")
    router_text = (tmp_path / "app" / "generated" / "role_alias_router.py").read_text(encoding="utf-8")

    assert "class ProducerCountryOption(StrEnum):" in enums_text
    assert "class ProducerPrimaryCropsOption(StrEnum):" in enums_text
    assert "CANADA = 'Canada'" in enums_text
    assert "WHEAT = 'Wheat'" in enums_text

    assert "country: ProducerCountryOption" in router_text
    assert "primary_crops: list[ProducerPrimaryCropsOption]" in router_text


def test_writer_does_not_delete_outside_project_root(tmp_path: Path):
    outside_file = tmp_path.parent / "manifest_outside_guard.txt"
    outside_file.write_text("safe\n", encoding="utf-8")

    write_manifest(
        tmp_path,
        spec_hash="oldhash",
        mode="mvp",
        generated_files=["app/generated/../../../manifest_outside_guard.txt", "generated/manifest.json"],
        migration_revision="mkt_old",
        export_path=None,
    )

    _generated, removed = write_artifacts(tmp_path, {}, keep_paths={"generated/manifest.json"})

    assert "app/generated/../../../manifest_outside_guard.txt" not in removed
    assert outside_file.exists()
    outside_file.unlink()


def test_check_compile_sync_detects_manifest_metadata_drift(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    compile_marketplace(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    manifest_path = tmp_path / "generated" / "manifest.json"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["mode"] = "strict"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    check = check_compile_sync(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    assert check["in_sync"] is False
    assert "generated/manifest.json" in check["drift_files"]


def test_compile_and_check_are_idempotent(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    compile_marketplace(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    check = check_compile_sync(
        config=raw,
        options=CompileOptions(mode="mvp", export_enabled=False),
        project_root=tmp_path,
    )

    assert check["in_sync"] is True
    assert check["drift_files"] == []


def test_openapi_generation_does_not_mutate_runtime_config(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    previous = None
    try:
        previous = get_marketplace_config()
    except RuntimeError:
        previous = None

    baseline = MarketplaceConfig(**raw)
    try:
        set_marketplace_config(baseline)

        changed = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
        changed["marketplace"]["name"] = "Temporary Name For Compile"
        changed_config = MarketplaceConfig(**changed)

        check_compile_sync(
            config=changed_config,
            options=CompileOptions(mode="mvp", export_enabled=False),
            project_root=tmp_path,
        )

        assert get_marketplace_config().marketplace.name == baseline.marketplace.name
    finally:
        if previous is not None:
            set_marketplace_config(previous)
