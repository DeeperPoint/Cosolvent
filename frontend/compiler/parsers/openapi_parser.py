"""Parse an OpenAPI 3.x document into raw intermediate structures.

This parser extracts operations (paths + methods) and component schemas
from the OpenAPI JSON document.  The output is a ``RawOpenAPI`` dataclass
consumed by the merge transform.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawSchemaProperty:
    name: str
    type_hint: str
    required: bool
    nullable: bool = False
    enum: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawSchema:
    name: str
    properties: tuple[RawSchemaProperty, ...]
    raw: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)


@dataclass(frozen=True)
class RawOperation:
    operation_id: str
    method: str
    path: str
    tags: tuple[str, ...]
    request_schema_name: str | None
    response_schema_name: str | None
    path_params: tuple[str, ...]
    query_params: tuple[RawSchemaProperty, ...]
    auth_required: bool


@dataclass(frozen=True)
class RawOpenAPI:
    operations: tuple[RawOperation, ...]
    schemas: dict[str, RawSchema]


_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")

_OPENAPI_TO_TS: dict[str, str] = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "object": "Record<string, unknown>",
}


def parse_openapi(doc: dict[str, Any]) -> RawOpenAPI:
    """Parse an OpenAPI JSON document into raw structures."""
    schemas = _parse_schemas(doc.get("components", {}).get("schemas", {}))
    operations = _parse_operations(doc.get("paths", {}), doc)
    return RawOpenAPI(operations=tuple(operations), schemas=schemas)


def _parse_schemas(schemas_dict: dict[str, Any]) -> dict[str, RawSchema]:
    result: dict[str, RawSchema] = {}
    for name, schema in sorted(schemas_dict.items()):
        props = _extract_properties(schema)
        result[name] = RawSchema(name=name, properties=tuple(props), raw=schema)
    return result


def _extract_properties(schema: dict[str, Any]) -> list[RawSchemaProperty]:
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))
    result: list[RawSchemaProperty] = []

    for prop_name, prop_schema in sorted(properties.items()):
        ts_type = _resolve_ts_type(prop_schema)
        nullable = prop_schema.get("nullable", False)
        enum_values: tuple[str, ...] = ()
        if "enum" in prop_schema:
            enum_values = tuple(str(v) for v in prop_schema["enum"])

        result.append(
            RawSchemaProperty(
                name=prop_name,
                type_hint=ts_type,
                required=prop_name in required_set,
                nullable=nullable,
                enum=enum_values,
            )
        )
    return result


def _resolve_ts_type(prop: dict[str, Any]) -> str:
    if "$ref" in prop:
        ref = prop["$ref"]
        return ref.rsplit("/", 1)[-1]

    if "allOf" in prop:
        refs = [item.get("$ref", "").rsplit("/", 1)[-1] for item in prop["allOf"] if "$ref" in item]
        return refs[0] if refs else "unknown"

    if "anyOf" in prop or "oneOf" in prop:
        variants = prop.get("anyOf") or prop.get("oneOf", [])
        types = []
        for v in variants:
            if v.get("type") == "null":
                continue
            types.append(_resolve_ts_type(v))
        if not types:
            return "unknown"
        return " | ".join(sorted(set(types))) if len(types) > 1 else types[0]

    prop_type = prop.get("type", "string")

    if prop_type == "array":
        items = prop.get("items", {})
        item_type = _resolve_ts_type(items)
        return f"{item_type}[]"

    if prop_type == "object":
        additional = prop.get("additionalProperties")
        if additional and isinstance(additional, dict):
            val_type = _resolve_ts_type(additional)
            return f"Record<string, {val_type}>"
        return "Record<string, unknown>"

    return _OPENAPI_TO_TS.get(prop_type, "unknown")


def _parse_operations(
    paths: dict[str, Any],
    doc: dict[str, Any],
) -> list[RawOperation]:
    ops: list[RawOperation] = []
    security_globally = bool(doc.get("security"))

    for path, path_item in sorted(paths.items()):
        path_level_params = path_item.get("parameters", [])

        for method in ("get", "post", "put", "delete", "patch"):
            operation = path_item.get(method)
            if not operation:
                continue

            op_id = operation.get("operationId", f"{method}_{path}")
            tags = tuple(operation.get("tags", []))

            request_schema_name = _extract_request_schema_name(operation)
            response_schema_name = _extract_response_schema_name(operation)

            all_params = path_level_params + operation.get("parameters", [])
            path_params = tuple(
                p["name"]
                for p in all_params
                if p.get("in") == "path"
            )
            query_params = tuple(
                RawSchemaProperty(
                    name=p["name"],
                    type_hint=_resolve_ts_type(p.get("schema", {})),
                    required=p.get("required", False),
                )
                for p in all_params
                if p.get("in") == "query"
            )

            has_security = bool(operation.get("security")) or (
                security_globally and "security" not in operation
            )

            ops.append(
                RawOperation(
                    operation_id=op_id,
                    method=method.upper(),
                    path=path,
                    tags=tags,
                    request_schema_name=request_schema_name,
                    response_schema_name=response_schema_name,
                    path_params=path_params,
                    query_params=query_params,
                    auth_required=has_security,
                )
            )

    return sorted(ops, key=lambda o: (o.path, o.method))


def _extract_request_schema_name(operation: dict[str, Any]) -> str | None:
    body = operation.get("requestBody", {})
    content = body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})
    ref = schema.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    return None


def _extract_response_schema_name(operation: dict[str, Any]) -> str | None:
    for code in ("200", "201"):
        resp = operation.get("responses", {}).get(code, {})
        content = resp.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})
        ref = schema.get("$ref")
        if ref:
            return ref.rsplit("/", 1)[-1]
    return None
