"""Static spec ↔ implementation audit.

Runs at e2e time so the generated report is refreshed against the live
repo state. Always writes ``tests/e2e/MISMATCH_REPORT.md``. Fails the
test only when *critical* mismatches exist; warnings/info are surfaced in
the report but don't block the build.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.contract import MarketplaceContract, OpenAPIContract
from tests.e2e.contract.audit import audit_contracts, render_report
from tests.e2e.contract.coverage import coverage_summary, scan_test_files

_REPORT_PATH = Path(__file__).parent / "MISMATCH_REPORT.md"


@pytest.mark.e2e
def test_spec_vs_implementation_audit(
    openapi_contract: OpenAPIContract,
    marketplace_contract: MarketplaceContract,
) -> None:
    result = audit_contracts(
        openapi=openapi_contract,
        marketplace=marketplace_contract,
    )

    coverage = scan_test_files(Path(__file__).parent, openapi_contract)
    summary = coverage_summary(openapi_contract, coverage)

    markdown = render_report(
        result,
        source_paths={
            "OpenAPI spec": str(openapi_contract.source_path),
            "Marketplace config": str(marketplace_contract.source_path),
        },
    )
    markdown += _render_coverage_section(summary)
    _REPORT_PATH.write_text(markdown, encoding="utf-8")

    critical = result.critical
    if critical:
        formatted = "\n".join(f"  - {f}" for f in critical)
        raise AssertionError(
            "Critical spec/implementation mismatches:\n"
            f"{formatted}\n\n"
            f"Full report: {_REPORT_PATH}"
        )


def _render_coverage_section(summary: dict) -> str:
    total = summary["total_endpoints"]
    tested = summary["tested_endpoints"]
    percent = (100.0 * tested / total) if total else 0.0
    lines = [
        "",
        "## E2E Coverage",
        "",
        f"**Tested**: {tested} / {total} endpoints ({percent:.1f}%)",
        "",
    ]
    untested = summary.get("untested", [])
    if untested:
        lines.append("### Untested endpoints")
        lines.append("")
        for method, path in untested:
            lines.append(f"- `{method} {path}`")
        lines.append("")
    lines.append("### Coverage by test module")
    lines.append("")
    for module, pairs in sorted(summary.get("by_module", {}).items()):
        lines.append(f"- **{module}** — {len(pairs)} endpoints exercised")
    lines.append("")
    return "\n".join(lines)
