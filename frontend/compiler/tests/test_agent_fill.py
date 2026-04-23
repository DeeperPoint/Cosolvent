from __future__ import annotations

from pathlib import Path

import pytest

from compiler.agent_markers import MarkerValidationError, apply_marker_replacements, find_fill_markers
from compiler.cli import run_generate_frontend
from compiler.frontend_agent import AgentFillOptions, run_agent_fill
from compiler.tests.test_compiler import _build_test_ir
from compiler.writer import check_manifest_sync, write_frontend


def test_marker_parse_and_replace():
    content = """
export default function Page() {
  return (
    <div>
      {/* AGENT_FILL:hero:start */}
      <p>Placeholder</p>
      {/* AGENT_FILL:hero:end */}
    </div>
  );
}
"""
    markers = find_fill_markers(content)
    assert [m.marker_id for m in markers] == ["hero"]

    updated = apply_marker_replacements(content, {"hero": "<h1>Filled</h1>"})
    assert "<h1>Filled</h1>" in updated
    assert "AGENT_FILL:hero:start" in updated
    assert "AGENT_FILL:hero:end" in updated


def test_marker_validator_rejects_mismatch():
    with pytest.raises(MarkerValidationError):
        find_fill_markers("/* AGENT_FILL:x:start */ only one side")


def test_writer_force_overwrite_agent_managed(tmp_path: Path):
    out = tmp_path / "frontend"
    out.mkdir()
    target = out / "src" / "app" / "demo" / "page.tsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")

    result = write_frontend(
        out,
        {"src/app/demo/page.tsx": "new"},
        spec_hash="abc",
        generator_version="1.0.0",
        clean=False,
        force_overwrite_paths={"src/app/demo/page.tsx"},
        manifest_extra={"agent_fill_enabled": True},
    )
    assert "src/app/demo/page.tsx" in result["generated"]
    assert target.read_text(encoding="utf-8") == "new"


def test_writer_force_overwrite_rejects_unmanaged(tmp_path: Path):
    out = tmp_path / "frontend"
    out.mkdir()
    with pytest.raises(ValueError):
        write_frontend(
            out,
            {"README.md": "x"},
            spec_hash="abc",
            generator_version="1.0.0",
            clean=False,
            force_overwrite_paths={"README.md"},
            manifest_extra={},
        )


def test_agent_fill_applies_only_marked_files(monkeypatch: pytest.MonkeyPatch):
    ir = _build_test_ir()
    artifacts = {
        "src/app/demo/page.tsx": """
function Demo() {
  return (
    <>
      {/* AGENT_FILL:demo:start */}
      <p>stub</p>
      {/* AGENT_FILL:demo:end */}
    </>
  );
}
""",
        "src/generated/api/client.ts": "export const x = 1;",
    }

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_call_openrouter(*, prompt: str, model: str, api_key: str, timeout: int) -> str:
        assert "AGENT_FILL:demo:start" in prompt
        return '{"replacements":[{"id":"demo","content":"<section>ok</section>"}]}'

    monkeypatch.setattr("compiler.frontend_agent._call_openrouter", fake_call_openrouter)

    result = run_agent_fill(artifacts, ir, AgentFillOptions(enabled=True))
    assert "src/app/demo/page.tsx" in result.filled_files
    assert "<section>ok</section>" in result.artifacts["src/app/demo/page.tsx"]
    assert result.artifacts["src/generated/api/client.ts"] == "export const x = 1;"


def test_cli_passes_new_flags(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake_compile_frontend(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "spec_hash": "abcdef0123456789",
            "output_dir": ".",
            "generated": [],
            "skipped": [],
            "removed": [],
            "agent_fill_enabled": kwargs.get("agent_fill", False),
            "agent_model": kwargs.get("agent_model"),
            "verified": False,
        }

    monkeypatch.setattr("compiler.service.compile_frontend", fake_compile_frontend)

    ok = run_generate_frontend(
        openapi_path="openapi.json",
        marketplace_path="marketplace.yaml",
        output_dir=".",
        clean=True,
        agent_fill=True,
        agent_model="anthropic/claude-3.5-sonnet",
        agent_timeout_seconds=42,
        verify_build=True,
        check=True,
    )
    assert ok is True
    assert captured["agent_fill"] is True
    assert captured["agent_timeout_seconds"] == 42
    assert captured["verify_build"] is True
    assert captured["check"] is True


def test_check_manifest_sync(tmp_path: Path):
    out = tmp_path / "frontend"
    out.mkdir()
    write_frontend(
        out,
        {"src/generated/types.ts": "export type X = string;"},
        spec_hash="hash123",
        generator_version="1.0.0",
        manifest_extra={},
    )
    ok, _ = check_manifest_sync(out, "hash123")
    assert ok
