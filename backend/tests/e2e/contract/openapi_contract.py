"""OpenAPI contract helpers for runtime validation in e2e tests.

The contract is loaded from ``openapi/generated_openapi.json`` (checked in)
by default.  It exposes three capabilities:

- ``OpenAPIContract.endpoints()``: enumerate every declared (path, method).
- ``OpenAPIContract.declared_status_codes(path, method)``: the success status
  codes declared for the operation.
- ``assert_matches_openapi(response, ...)``: validate an ``httpx.Response``
  body + status against the OpenAPI schema.

``assert_matches_openapi`` uses ``jsonschema`` with a ``$ref`` resolver that
walks ``#/components/schemas/...``.  Operations with no declared response
schema are treated as permissive — they only assert the status code matches
the declared set (or the default 2xx bucket) to avoid false positives while
still surfacing status-code mismatches.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_SPEC_PATH = _REPO_ROOT / "openapi" / "generated_openapi.json"


@dataclass(frozen=True)
class OpenAPIContract:
    """In-memory view of a FastAPI-generated OpenAPI document."""

    spec: dict[str, Any]
    source_path: Path

    @property
    def paths(self) -> dict[str, Any]:
        return self.spec.get("paths", {}) or {}

    @property
    def components(self) -> dict[str, Any]:
        return self.spec.get("components", {}) or {}

    def endpoints(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for path, operations in self.paths.items():
            if not isinstance(operations, dict):
                continue
            for method, op in operations.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                if isinstance(op, dict):
                    result.append((path, method.upper()))
        return sorted(result)

    def find_operation(self, path: str, method: str) -> dict[str, Any] | None:
        """Locate an operation, handling FastAPI path-parameter naming drift.

        Tests may express real-world paths like ``/api/conversations/abc``;
        OpenAPI declares them as ``/api/conversations/{conv_id}``.  Try the
        literal path first, then a template-matching fallback.
        """

        method_lc = method.lower()
        literal = self.paths.get(path)
        if isinstance(literal, dict) and method_lc in literal:
            return literal[method_lc]

        for template, operations in self.paths.items():
            if not isinstance(operations, dict):
                continue
            if _path_matches(template, path) and method_lc in operations:
                return operations[method_lc]
        return None

    def declared_status_codes(self, path: str, method: str) -> list[int]:
        op = self.find_operation(path, method)
        if not op:
            return []
        codes: list[int] = []
        for key in (op.get("responses") or {}):
            try:
                codes.append(int(str(key)))
            except (TypeError, ValueError):
                continue
        return sorted(codes)

    def response_schema(
        self, path: str, method: str, status_code: int
    ) -> dict[str, Any] | None:
        op = self.find_operation(path, method)
        if not op:
            return None
        responses = op.get("responses") or {}
        response = responses.get(str(status_code)) or responses.get(status_code)
        if not isinstance(response, dict):
            return None
        schema = (
            (response.get("content") or {})
            .get("application/json", {})
            .get("schema")
        )
        return schema or None

    def request_body_schema(self, path: str, method: str) -> dict[str, Any] | None:
        op = self.find_operation(path, method)
        if not op:
            return None
        body = op.get("requestBody") or {}
        schema = (body.get("content") or {}).get("application/json", {}).get("schema")
        return schema or None

    def build_validator(self, schema: dict[str, Any]) -> Draft202012Validator:
        # Fully expand ``$ref`` so the validator never needs to resolve a
        # pointer against the schema under test (which ``jsonschema`` does by
        # default for inline $refs).  This sidesteps a well-known gotcha
        # where ``#/components/...`` cannot be resolved when the validator's
        # root document is an individual schema instead of the full spec.
        resolved = self._inline_refs(schema)
        registry = _build_registry(self.spec)
        return Draft202012Validator(resolved, registry=registry)

    def _inline_refs(self, node: Any, _seen: frozenset[str] = frozenset()) -> Any:
        """Recursively replace ``$ref: '#/components/...'`` entries with the
        resolved sub-schema from ``self.spec``.  Self-recursive schemas are
        short-circuited to ``{}`` (permissive) to avoid infinite loops.
        """

        if isinstance(node, list):
            return [self._inline_refs(item, _seen) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/"):
            ref = node["$ref"]
            if ref in _seen:
                return {}
            target: Any = self.spec
            for segment in ref[2:].split("/"):
                segment = segment.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, dict) or segment not in target:
                    return {}
                target = target[segment]
            merged = self._inline_refs(target, _seen | {ref})
            # Merge sibling keywords (OpenAPI allows ``description`` alongside ``$ref``).
            if isinstance(merged, dict):
                extras = {k: v for k, v in node.items() if k != "$ref"}
                if extras:
                    merged = {**merged, **self._inline_refs(extras, _seen | {ref})}
            return merged
        return {k: self._inline_refs(v, _seen) for k, v in node.items()}


def load_openapi_contract(spec_path: Path | None = None) -> OpenAPIContract:
    path = spec_path or _DEFAULT_SPEC_PATH
    with path.open("r", encoding="utf-8") as handle:
        spec = json.load(handle)
    return OpenAPIContract(spec=spec, source_path=path)


_TEMPLATE_RE = re.compile(r"\{([^}]+)\}")


def _path_matches(template: str, literal: str) -> bool:
    """Best-effort path-parameter match (treats each ``{name}`` as ``[^/]+``)."""

    if template == literal:
        return True
    if "{" not in template:
        return False
    pattern = "^" + _TEMPLATE_RE.sub(r"([^/]+)", re.escape(template).replace("\\{", "{").replace("\\}", "}")) + "$"
    return re.match(pattern, literal) is not None


def _build_registry(spec: dict[str, Any]) -> Registry:
    resource = Resource(contents=spec, specification=DRAFT202012)
    # Register under the common FastAPI base URI so ``#/components/...`` refs
    # resolve correctly from embedded schemas.
    return Registry().with_resource(uri="", resource=resource)


def assert_matches_openapi(
    response: httpx.Response,
    *,
    contract: OpenAPIContract,
    path_template: str | None = None,
    method: str | None = None,
    expected_status: int | Iterable[int] | None = None,
) -> None:
    """Validate an ``httpx.Response`` against the OpenAPI contract.

    Parameters
    ----------
    response:
        The live response.
    contract:
        Loaded OpenAPI contract.
    path_template:
        Optional override for the OpenAPI path template.  If omitted, the
        raw request path is used (with template-matching fallback).
    method:
        HTTP method override.
    expected_status:
        If provided, asserts the response status is one of these codes.
        Otherwise, the status is only asserted to be in the declared set if
        the contract declares any non-validation responses.
    """

    req_method = (method or response.request.method).upper()
    req_path = path_template or response.request.url.path

    actual_status = response.status_code
    if expected_status is not None:
        allowed = {expected_status} if isinstance(expected_status, int) else set(expected_status)
        if actual_status not in allowed:
            raise AssertionError(
                f"Unexpected status for {req_method} {req_path}: "
                f"got {actual_status}, expected one of {sorted(allowed)}"
            )

    declared = contract.declared_status_codes(req_path, req_method)
    non_validation = [c for c in declared if c != 422]
    # Universal error statuses are allowed on any endpoint without being
    # declared explicitly: 404 (missing resource / unknown route), 401/403
    # (auth), 409/429 (rate / conflict), 5xx (server). This matches common
    # FastAPI behavior where these may bubble up from middleware/dependencies.
    _UNIVERSAL_CODES = {401, 403, 404, 405, 409, 422, 429, 500, 502, 503}
    if (
        declared
        and actual_status not in declared
        and actual_status not in _UNIVERSAL_CODES
        and non_validation
    ):
        raise AssertionError(
            f"Status {actual_status} for {req_method} {req_path} is not in "
            f"declared responses {declared}"
        )

    if actual_status >= 400:
        return  # Don't validate error bodies against success schemas.

    schema = contract.response_schema(req_path, req_method, actual_status)
    if schema is None:
        return  # Unconstrained response — nothing to validate.

    try:
        body = response.json()
    except ValueError as exc:
        raise AssertionError(
            f"Response for {req_method} {req_path} was not JSON as declared"
        ) from exc

    validator = contract.build_validator(schema)
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.absolute_path))
    if errors:
        summary = "\n".join(_format_error(err) for err in errors[:10])
        raise AssertionError(
            f"Response body for {req_method} {req_path} does not match "
            f"OpenAPI schema:\n{summary}"
        )


def _format_error(err: ValidationError) -> str:
    location = "/".join(str(part) for part in err.absolute_path) or "<root>"
    return f"  - {location}: {err.message}"
