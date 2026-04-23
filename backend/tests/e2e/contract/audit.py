"""Static audit of spec-vs-implementation mismatches.

Produces a list of structured :class:`Finding` objects that the test suite
can surface in a single failing assertion, and a markdown renderer used
for the generated ``MISMATCH_REPORT.md``.

The audit is deliberately heuristic; each check encodes a concrete
expectation the rest of the QA layer depends on (e.g. that every
participant type has role-aliased routes, that admin routes require auth,
that routes touching data have a declared response schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .openapi_contract import OpenAPIContract
from .yaml_contract import MarketplaceContract

Severity = str  # "critical" | "warning" | "info"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    category: str
    path: str
    method: str
    detail: str

    def __str__(self) -> str:
        prefix = {"critical": "CRITICAL", "warning": "WARN", "info": "INFO"}.get(
            self.severity, self.severity.upper()
        )
        loc = f"{self.method} {self.path}" if self.path else "-"
        return f"[{prefix}] {self.category} ({loc}): {self.detail}"


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def info(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]


# Paths that are expected to enforce admin-only access.
_ADMIN_PREFIX = "/api/admin"

# Paths that are public by design (no auth required).
_PUBLIC_EXACT = {
    "/api/auth/bootstrap",
    "/api/auth/login",
    "/api/auth/signup",
    "/api/auth/logout",
    "/api/health",
    "/api/setup/presets",
    "/api/setup/config-template",
    "/api/setup/validate",
    "/api/setup/render-yaml",
    "/api/setup/save",
    "/api/setup/generate",
    "/api/setup/generate/check",
    "/onboarding",
}
_PUBLIC_PREFIX = ("/api/setup/assets/",)


def audit_contracts(
    *,
    openapi: OpenAPIContract,
    marketplace: MarketplaceContract,
) -> AuditResult:
    result = AuditResult()
    _audit_endpoints_have_responses(openapi, result)
    _audit_participant_type_coverage(openapi, marketplace, result)
    _audit_role_alias_parity(openapi, marketplace, result)
    _audit_admin_auth(openapi, result)
    _audit_status_codes(openapi, result)
    _audit_marketplace_rules(marketplace, result)
    return result


def _audit_endpoints_have_responses(
    openapi: OpenAPIContract, result: AuditResult
) -> None:
    """Every declared 2xx response should have a schema.

    Endpoints without a schema silently allow breaking changes; this is the
    biggest contract gap in a FastAPI app where ``response_model`` is not
    set.  We flag these as warnings (not critical) because they still
    function; the recommended fix is to add ``response_model`` to the
    router.
    """

    for path, method in openapi.endpoints():
        op = openapi.find_operation(path, method)
        if not op:
            continue
        responses = op.get("responses") or {}
        success = {
            code: resp
            for code, resp in responses.items()
            if str(code).startswith("2")
        }
        if not success:
            result.findings.append(
                Finding(
                    severity="warning",
                    category="missing-success-response",
                    path=path,
                    method=method,
                    detail="No 2xx response declared in OpenAPI spec.",
                )
            )
            continue
        for code, resp in success.items():
            content = (resp or {}).get("content") or {}
            # Endpoints that deliberately return non-JSON (HTML pages,
            # file downloads, streamed binaries) are legitimately
            # schemaless for JSON contract purposes.
            non_json_types = {
                ct
                for ct in content.keys()
                if ct != "application/json"
            }
            if content and not content.get("application/json") and non_json_types:
                continue
            schema = (
                content.get("application/json", {}).get("schema")
            )
            if not schema:
                result.findings.append(
                    Finding(
                        severity="warning",
                        category="missing-response-schema",
                        path=path,
                        method=method,
                        detail=(
                            f"{code} response has no JSON schema — consider "
                            "adding a response_model for contract safety."
                        ),
                    )
                )


def _audit_participant_type_coverage(
    openapi: OpenAPIContract,
    marketplace: MarketplaceContract,
    result: AuditResult,
) -> None:
    """Every participant type in marketplace.yaml should have routes."""

    endpoint_paths = {p for p, _ in openapi.endpoints()}
    for pt in marketplace.participant_types:
        generic = "/api/profiles/{type_slug}/register"
        alias = f"/api/roles/{pt.slug}/register"
        if generic not in endpoint_paths and alias not in endpoint_paths:
            result.findings.append(
                Finding(
                    severity="critical",
                    category="missing-participant-route",
                    path=alias,
                    method="POST",
                    detail=(
                        f"Participant type '{pt.slug}' defined in marketplace.yaml "
                        "but no register route exists."
                    ),
                )
            )


def _audit_role_alias_parity(
    openapi: OpenAPIContract,
    marketplace: MarketplaceContract,
    result: AuditResult,
) -> None:
    """Role-alias routes under /api/roles/{slug}/... should mirror /api/profiles/{type_slug}/...

    The compiler (``backend/cli/compile.py``) emits a per-slug alias in
    ``app/generated/role_alias_router.py`` that shadows each generic
    ``/api/profiles/{type_slug}`` route.  We compare the generic route
    set against the alias route set, not against substituted generics,
    to avoid false positives.
    """

    endpoint_paths = {(p, m) for p, m in openapi.endpoints()}
    generic_ops = [
        (p, m)
        for p, m in endpoint_paths
        if p.startswith("/api/profiles/{type_slug}")
    ]

    for pt in marketplace.participant_types:
        for generic_path, method in generic_ops:
            alias_path = generic_path.replace(
                "/api/profiles/{type_slug}", f"/api/roles/{pt.slug}"
            )
            if (alias_path, method) not in endpoint_paths:
                result.findings.append(
                    Finding(
                        severity="warning",
                        category="missing-role-alias",
                        path=alias_path,
                        method=method,
                        detail=(
                            "Generic profile route exists but no role alias "
                            f"was generated for '{pt.slug}'."
                        ),
                    )
                )


def _audit_admin_auth(openapi: OpenAPIContract, result: AuditResult) -> None:
    """Every admin route should declare 401/403 responses (they use require_admin)."""

    for path, method in openapi.endpoints():
        if not path.startswith(_ADMIN_PREFIX):
            continue
        declared = set(openapi.declared_status_codes(path, method))
        # FastAPI auto-declares 422 for body-validation; require_admin
        # raises 401/403 at runtime but those codes aren't in the spec by
        # default.  Flag as info so teams can add ``responses=`` annotations
        # to lock the contract.
        if 401 not in declared and 403 not in declared:
            result.findings.append(
                Finding(
                    severity="info",
                    category="admin-auth-not-declared",
                    path=path,
                    method=method,
                    detail=(
                        "Admin route uses require_admin but 401/403 are not "
                        "declared in OpenAPI responses."
                    ),
                )
            )


def _audit_status_codes(openapi: OpenAPIContract, result: AuditResult) -> None:
    """Mutating routes (POST/PUT/DELETE) without an explicit status typically return 200.

    RESTful convention prefers 201 for POST-create.  We flag POSTs that
    return 200 and whose summary suggests creation, as an info-level hint.
    """

    for path, method in openapi.endpoints():
        if method != "POST":
            continue
        op = openapi.find_operation(path, method) or {}
        responses = op.get("responses") or {}
        if "201" in responses:
            continue
        summary = str(op.get("summary", "")).lower()
        if any(kw in summary for kw in ("create", "signup", "register", "upload")):
            if "200" in responses:
                result.findings.append(
                    Finding(
                        severity="info",
                        category="post-returns-200",
                        path=path,
                        method=method,
                        detail=(
                            "POST endpoint semantically creates a resource "
                            "but returns 200 instead of 201."
                        ),
                    )
                )


def _audit_marketplace_rules(
    marketplace: MarketplaceContract, result: AuditResult
) -> None:
    """Sanity-check the marketplace.yaml file itself for clarity."""

    if not marketplace.participant_types:
        result.findings.append(
            Finding(
                severity="critical",
                category="marketplace-missing-participants",
                path="marketplace.yaml",
                method="",
                detail="No participant_types declared.",
            )
        )

    for pt in marketplace.participant_types:
        if pt.role not in {"supply", "demand", "peer"}:
            result.findings.append(
                Finding(
                    severity="warning",
                    category="marketplace-role-value",
                    path=f"participant_types[{pt.slug}].role",
                    method="",
                    detail=(
                        f"Unexpected role '{pt.role}'. Known values are "
                        "supply, demand, peer."
                    ),
                )
            )
        if not pt.required_fields:
            result.findings.append(
                Finding(
                    severity="info",
                    category="marketplace-no-required-fields",
                    path=f"profile_schemas.{pt.slug}",
                    method="",
                    detail=(
                        f"Type '{pt.slug}' has no required fields — "
                        "profile completeness/validation will be trivially met."
                    ),
                )
            )

    for rule in marketplace.conversation_rules:
        initiator = rule.get("initiator")
        receiver = rule.get("receiver")
        known_slugs = {p.slug for p in marketplace.participant_types}
        if initiator not in known_slugs or receiver not in known_slugs:
            result.findings.append(
                Finding(
                    severity="critical",
                    category="marketplace-unknown-slug",
                    path=f"communication.conversation_rules[{initiator}->{receiver}]",
                    method="",
                    detail=(
                        f"Conversation rule references unknown slug "
                        f"(initiator={initiator!r}, receiver={receiver!r})."
                    ),
                )
            )


def render_report(result: AuditResult, *, source_paths: dict[str, str]) -> str:
    """Render the audit result as a markdown report."""

    lines: list[str] = []
    lines.append("# Spec ↔ Implementation Audit")
    lines.append("")
    lines.append("Automatically generated by `tests/e2e/contract/audit.py`.")
    lines.append("")
    for name, path in source_paths.items():
        lines.append(f"- **{name}**: `{path}`")
    lines.append("")
    lines.append(
        f"**Totals** — critical: {len(result.critical)}, "
        f"warnings: {len(result.warnings)}, info: {len(result.info)}"
    )
    lines.append("")
    for section, entries in (
        ("Critical findings", result.critical),
        ("Warnings", result.warnings),
        ("Informational", result.info),
    ):
        lines.append(f"## {section} ({len(entries)})")
        lines.append("")
        if not entries:
            lines.append("_None._")
            lines.append("")
            continue
        by_category: dict[str, list[Finding]] = {}
        for f in entries:
            by_category.setdefault(f.category, []).append(f)
        for category, items in sorted(by_category.items()):
            lines.append(f"### `{category}` ({len(items)})")
            lines.append("")
            for f in items:
                loc = f"{f.method} {f.path}".strip()
                lines.append(f"- **{loc}**: {f.detail}")
            lines.append("")
    return "\n".join(lines)


def collect_coverage(
    openapi: OpenAPIContract, tested: dict[str, set[tuple[str, str]]]
) -> dict[str, Any]:
    """Compute coverage numbers for reporting.

    ``tested`` maps test-module name → set of (method, path_template) pairs
    exercised.
    """

    all_endpoints = set(openapi.endpoints())
    # Flip to (method, path) order since tests report that way.
    all_pairs = {(method, path) for path, method in all_endpoints}
    exercised: set[tuple[str, str]] = set()
    for pairs in tested.values():
        exercised.update(pairs)
    return {
        "total_endpoints": len(all_pairs),
        "tested_endpoints": len(exercised & all_pairs),
        "untested": sorted(all_pairs - exercised),
    }
