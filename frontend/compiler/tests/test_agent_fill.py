from __future__ import annotations

from pathlib import Path

import pytest

from compiler.agent_markers import MarkerValidationError, apply_marker_replacements, find_fill_markers
from compiler.agent_prompt import build_fill_prompt, build_system_prompt, derive_page_facts
from compiler.cli import run_generate_frontend
from compiler.frontend_agent import (
    AgentFillOptions,
    _inject_missing_imports,
    _normalize_openrouter_api_key,
    _read_dotenv_value,
    run_agent_fill,
)
from compiler.tests.test_compiler import _build_test_ir
from compiler.writer import check_manifest_sync, write_frontend


def test_agent_fill_rejects_non_sonnet_models():
    ir = _build_test_ir()
    with pytest.raises(ValueError, match="Anthropic"):
        run_agent_fill(
            {"src/app/x/page.tsx": "x"},
            ir,
            AgentFillOptions(enabled=True, model="openai/gpt-4o-mini"),
        )
    with pytest.raises(ValueError, match="sonnet"):
        run_agent_fill(
            {"src/app/x/page.tsx": "x"},
            ir,
            AgentFillOptions(enabled=True, model="anthropic/claude-opus-4"),
        )


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
        find_fill_markers("{/* AGENT_FILL:x:start */}\n<p>no end marker</p>")


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


def test_normalize_openrouter_api_key_strips_bom_and_crlf():
    assert _normalize_openrouter_api_key("\ufeffsk-test\r\n") == "sk-test"
    assert _normalize_openrouter_api_key('"sk-quoted"') == "sk-quoted"


def test_read_dotenv_value_strips_quotes(tmp_path: Path):
    p = tmp_path / ".env"
    p.write_text('OPENROUTER_API_KEY="sk-test-123"\n', encoding="utf-8")
    assert _read_dotenv_value(p, "OPENROUTER_API_KEY") == "sk-test-123"


def test_agent_fill_hydrates_openrouter_key_from_cwd_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=sk-from-dotenv-file\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

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
    }

    captured: dict[str, str] = {}

    def fake_call_openrouter(*, prompt: str, model: str, api_key: str, timeout: int, system_prompt: str | None = None) -> str:
        captured["api_key"] = api_key
        return '{"replacements":[{"id":"demo","content":"<section>ok</section>"}]}'

    monkeypatch.setattr("compiler.frontend_agent._call_openrouter", fake_call_openrouter)

    result = run_agent_fill(artifacts, ir, AgentFillOptions(enabled=True))
    assert captured["api_key"] == "sk-from-dotenv-file"
    assert "src/app/demo/page.tsx" in result.filled_files


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

    def fake_call_openrouter(*, prompt: str, model: str, api_key: str, timeout: int, system_prompt: str | None = None) -> str:
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
        agent_model="anthropic/claude-sonnet-4",
        agent_timeout_seconds=42,
        verify_build=True,
        check=True,
    )
    assert ok is True
    assert captured["agent_fill"] is True
    assert captured["agent_timeout_seconds"] == 42
    assert captured["verify_build"] is True
    assert captured["check"] is True


def test_system_prompt_includes_design_contract_and_marketplace_identity():
    """The system prompt must carry the design contract + marketplace voice."""
    ir = _build_test_ir()
    sys = build_system_prompt(ir)
    assert ir.marketplace.name in sys
    # Design contract anchors that the model relies on.
    assert "Design contract" in sys
    assert "Skeleton" in sys  # loading-state guidance
    assert "@/components/ui/card" in sys  # component inventory
    # Output protocol must remain strict.
    assert "replacements" in sys
    assert "no markdown fences" in sys.lower()


def test_page_facts_inject_entity_field_schema_for_role_dashboards():
    """Per-page facts must include entity field schema for role-scoped pages."""
    ir = _build_test_ir()
    supply_facts = derive_page_facts(
        "src/app/(dashboard)/dashboard/supply/page.tsx", ir
    )
    assert "supply-dashboard" in supply_facts
    # Test IR's supply entity is "Seller" with a `company` field.
    assert "Seller" in supply_facts
    assert "company" in supply_facts


def test_build_fill_prompt_embeds_page_facts_and_marker_ids():
    ir = _build_test_ir()
    prompt = build_fill_prompt(
        file_path="src/app/(auth)/login/page.tsx",
        file_content="// pretend this is a file with markers\n",
        marker_ids=["login_form"],
        ir=ir,
    )
    assert "login_form" in prompt
    assert "page_intent" in prompt
    assert "src/app/(auth)/login/page.tsx" in prompt


def test_inject_missing_imports_adds_shadcn_and_lucide():
    """Auto-imports any known shadcn/lucide symbol the agent referenced."""
    content = '''"use client";

import { Card } from "@/components/ui/card";

export default function Demo() {
  return (
    <Card>
      <Tabs>
        <TabsList>
          <TabsTrigger value="a">A</TabsTrigger>
        </TabsList>
      </Tabs>
      <Loader2 className="h-4 w-4 animate-spin" />
      <AlertCircle />
    </Card>
  );
}
'''
    out = _inject_missing_imports(content)
    # shadcn/ui Tabs sub-exports auto-added in one statement
    assert 'from "@/components/ui/tabs"' in out
    for sym in ("Tabs", "TabsList", "TabsTrigger"):
        assert sym in out
    # lucide icons auto-added in one statement
    assert 'from "lucide-react"' in out
    for sym in ("Loader2", "AlertCircle"):
        assert sym in out
    # Existing import is preserved (not duplicated)
    assert out.count('from "@/components/ui/card"') == 1


def test_inject_missing_imports_is_noop_when_complete():
    content = '''"use client";

import { Button } from "@/components/ui/button";

export default function Demo() {
  return <Button>Click</Button>;
}
'''
    assert _inject_missing_imports(content) == content


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
