"""Static coverage scanner for e2e test files.

Parses every ``test_e2e_*.py`` file under ``tests/e2e/`` looking for HTTP
method calls against known paths (via ``client.get``, ``c.post`` and
similar patterns).  Matched paths are normalised to their OpenAPI
templates so we can report the delta against the declared contract.

The scanner is deliberately textual rather than AST-based because
```client.get(f"/api/foo/{id}")``` and similar dynamic paths are the
norm in the suite; we extract the f-string contents and fold path
parameter names into OpenAPI's ``{name}`` template form.
"""

from __future__ import annotations

import re
from pathlib import Path

from .openapi_contract import OpenAPIContract

_PATH_START = r"/(?:api/|onboarding|docs|openapi\.json|health)"
_METHOD_CALL_DOUBLE_RE = re.compile(
    r'\.\s*(?P<method>get|post|put|patch|delete|request)\s*\('
    r'(?:\s*"(?P<method2>[A-Z]+)"\s*,)?'
    r'\s*f?"(?P<path>' + _PATH_START + r'[^"]*)"'
)
_METHOD_CALL_SINGLE_RE = re.compile(
    r"\.\s*(?P<method>get|post|put|patch|delete|request)\s*\("
    r"(?:\s*'(?P<method2>[A-Z]+)'\s*,)?"
    r"\s*f?'(?P<path>" + _PATH_START + r"[^']*)'"
)


def _normalise_path(path: str) -> str:
    """Fold common dynamic segments back to their OpenAPI template form.

    - UUIDs → ``{id}``
    - ``{...}`` from Python f-strings (including ``{row['id']}``, nested
      expressions, format specs) → generic ``{id}``.
    """

    uuid_like = re.compile(r"/(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
    path = uuid_like.sub("/{id}", path)
    # Collapse f-string placeholders even when they contain quotes,
    # subscripts, or nested braces like ``{row['id']}`` or ``{obj.attr}``.
    path = re.sub(r"\{[^{}]*\}", "{id}", path)
    # Run once more to catch singly-nested placeholders.
    path = re.sub(r"\{[^{}]*\}", "{id}", path)
    return path


def _template_matches_literal(template: str, literal: str) -> bool:
    """True when ``literal`` satisfies an OpenAPI ``template``.

    A template segment ``{name}`` matches any single non-empty literal
    segment, so ``/api/profiles/{type_slug}/register`` matches
    ``/api/profiles/producer/register``.
    """

    t_parts = template.strip("/").split("/")
    l_parts = literal.strip("/").split("/")
    if len(t_parts) != len(l_parts):
        return False
    for t_seg, l_seg in zip(t_parts, l_parts):
        if t_seg.startswith("{") and t_seg.endswith("}"):
            if not l_seg:
                return False
            continue
        if t_seg != l_seg:
            return False
    return True


def _template_specificity(template: str) -> int:
    """Lower = more specific (fewer wildcard segments).

    Used to break ties when a concrete path matches several templates,
    e.g. ``/api/profiles/producer/me`` matches both
    ``/api/profiles/{type_slug}/me`` (1 wildcard) and
    ``/api/profiles/{type_slug}/{profile_id}`` (2 wildcards). The former
    wins because it has fewer wildcards.
    """

    return sum(
        1 for seg in template.strip("/").split("/") if seg.startswith("{") and seg.endswith("}")
    )


def _map_to_openapi_path(openapi: OpenAPIContract, method: str, path: str) -> str | None:
    """Find the OpenAPI path template that matches ``path`` under ``method``.

    When several templates match (e.g. a concrete ``/me`` path also matches
    the generic ``/{id}`` template), the most specific one wins — defined
    as the template with the fewest wildcard segments.
    """

    candidates: list[str] = []
    for template, ops in openapi.paths.items():
        if method.lower() not in (ops or {}):
            continue
        if template == path:
            return template
        normalised_template = _normalise_path(template)
        if normalised_template == path or _template_matches_literal(template, path):
            candidates.append(template)
    if not candidates:
        return None
    return min(candidates, key=_template_specificity)


def scan_test_files(
    test_dir: Path, openapi: OpenAPIContract
) -> dict[str, set[tuple[str, str]]]:
    """Return ``{test_module: {(METHOD, path_template), ...}}``."""

    coverage: dict[str, set[tuple[str, str]]] = {}
    files = list(test_dir.glob("test_e2e_*.py")) + [test_dir / "helpers.py"]
    for path in sorted({p.resolve() for p in files if p.exists()}):
        calls: set[tuple[str, str]] = set()
        text = path.read_text(encoding="utf-8")
        for regex in (_METHOD_CALL_DOUBLE_RE, _METHOD_CALL_SINGLE_RE):
            for match in regex.finditer(text):
                method = (match.group("method2") or match.group("method")).upper()
                if method == "REQUEST":
                    continue
                raw_path = match.group("path")
                normalised = _normalise_path(raw_path)
                template = _map_to_openapi_path(openapi, method, normalised) or normalised
                calls.add((method, template))
        if calls:
            coverage[path.name] = calls
    return coverage


def coverage_summary(
    openapi: OpenAPIContract, coverage: dict[str, set[tuple[str, str]]]
) -> dict[str, object]:
    all_endpoints = {(m, p) for p, m in openapi.endpoints()}
    exercised: set[tuple[str, str]] = set()
    for pairs in coverage.values():
        exercised.update(pairs)
    tested = exercised & all_endpoints
    return {
        "total_endpoints": len(all_endpoints),
        "tested_endpoints": len(tested),
        "tested": sorted(tested),
        "untested": sorted(all_endpoints - tested),
        "by_module": {name: sorted(pairs) for name, pairs in coverage.items()},
    }
