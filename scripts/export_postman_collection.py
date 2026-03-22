#!/usr/bin/env python3
"""
Export FastAPI OpenAPI schema to a Postman Collection v2.1 JSON file.

Usage:
  .venv/bin/python scripts/export_postman_collection.py \\
    --out postman/Cosolvent-API.postman_collection.json

Requires project imports (loads marketplace.yaml / app.main).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _resolve_schema(spec: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten $ref, allOf, anyOf (first branch) for JSON body examples."""
    if not schema:
        return {}
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/components/schemas/"):
            name = ref.split("/")[-1]
            comp = (spec.get("components") or {}).get("schemas") or {}
            if name in comp:
                return _resolve_schema(spec, comp[name])
        return {}
    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in schema["allOf"]:
            r = _resolve_schema(spec, part)
            if r.get("type") == "object":
                merged["properties"].update(r.get("properties") or {})
                merged["required"] = list(
                    dict.fromkeys((merged.get("required") or []) + (r.get("required") or []))
                )
            else:
                merged.update({k: v for k, v in r.items() if k not in ("properties", "required")})
        return merged
    if "anyOf" in schema and schema["anyOf"]:
        return _resolve_schema(spec, schema["anyOf"][0])
    if "oneOf" in schema and schema["oneOf"]:
        return _resolve_schema(spec, schema["oneOf"][0])
    return schema


def _example_from_schema(spec: dict[str, Any], schema: dict[str, Any] | None) -> Any:
    """Build a JSON-serializable example from an OpenAPI schema (resolved)."""
    if not schema:
        return {}
    if "example" in schema:
        return schema["example"]
    if "default" in schema and schema.get("type") != "object":
        return schema["default"]

    s = _resolve_schema(spec, schema)
    st = s.get("type")

    if st == "object":
        props = s.get("properties") or {}
        out: dict[str, Any] = {}
        req = set(s.get("required") or [])
        for key, sub in props.items():
            sub_r = _resolve_schema(spec, sub)
            out[key] = _example_from_schema(spec, sub_r)
        # Ensure required keys exist
        for key in req:
            if key not in out and key in props:
                out[key] = _example_from_schema(spec, _resolve_schema(spec, props[key]))
        return out

    if st == "array":
        items = s.get("items") or {}
        item_ex = _example_from_schema(spec, _resolve_schema(spec, items))
        return [item_ex] if item_ex != {} else []

    if st == "string":
        fmt = s.get("format")
        if fmt == "email":
            return "user@example.com"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        return ""
    if st == "integer":
        return 0
    if st == "number":
        return 0.0
    if st == "boolean":
        return False
    if st == "null":
        return None

    return None


def _json_body_from_schema(spec: dict[str, Any], schema: dict[str, Any] | None) -> str:
    if not schema:
        return "{}"
    resolved = _resolve_schema(spec, schema)
    try:
        ex = _example_from_schema(spec, resolved)
        if ex is None:
            return "{}"
        return json.dumps(ex, indent=2, ensure_ascii=False)
    except Exception:
        return "{}"


def _path_param_placeholder(name: str) -> str:
    n = name.lower()
    if "uuid" in n or n.endswith("_id") or n == "id":
        return "00000000-0000-0000-0000-000000000000"
    return ""


def _url_object(
    base_var: str,
    path: str,
    op: dict[str, Any],
    default_base: str = "http://localhost:18000",
) -> dict[str, Any]:
    """
    Postman needs protocol + host + port + path (not only `raw`), or the URL bar /
    route preview can look empty. `raw` still uses {{baseUrl}} so environments work.
    """
    u = urlparse(default_base)
    proto = u.scheme or "http"
    host_list = [u.hostname or "localhost"]
    port_str = str(u.port) if u.port else ""

    path_segments: list[str] = []
    path_vars: list[dict[str, str]] = []
    for segment in path.strip("/").split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            path_segments.append(f"{{{{{name}}}}}")
            path_vars.append({"key": name, "value": _path_param_placeholder(name)})
        else:
            path_segments.append(segment)

    raw_path = "/" + "/".join(path_segments) if path_segments else ""
    raw_full = f"{{{{{base_var}}}}}{raw_path}"

    out: dict[str, Any] = {
        "raw": raw_full,
        "protocol": proto,
        "host": host_list,
        "path": path_segments,
    }
    if port_str:
        out["port"] = port_str
    if path_vars:
        out["variable"] = path_vars

    q = _query_params(op)
    if q:
        qs = "&".join(f"{item['key']}=" for item in q)
        out["raw"] = f"{raw_full}?{qs}"
        out["query"] = q

    return out


def _request_body(spec: dict[str, Any], op: dict[str, Any]) -> dict[str, Any] | None:
    rb = op.get("requestBody")
    if not rb:
        return None
    content = rb.get("content") or {}
    if "application/json" in content:
        schema = (content["application/json"] or {}).get("schema") or {}
        raw = _json_body_from_schema(spec, schema)
        return {
            "mode": "raw",
            "raw": raw,
            "options": {"raw": {"language": "json"}},
        }
    if "multipart/form-data" in content or "application/x-www-form-urlencoded" in content:
        return {"mode": "formdata", "formdata": []}
    return {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}


def _query_params(op: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in op.get("parameters") or []:
        if p.get("in") == "query":
            name = p.get("name", "")
            out.append({"key": name, "value": "", "disabled": True})
    return out


def _operation_to_request(
    spec: dict[str, Any],
    method: str,
    path: str,
    op: dict[str, Any],
    base_var: str,
) -> dict[str, Any]:
    url_obj = _url_object(base_var, path, op)

    headers = [{"key": "Accept", "value": "application/json"}]
    body = _request_body(spec, op)
    if body and method in ("post", "put", "patch"):
        headers.append({"key": "Content-Type", "value": "application/json"})

    req: dict[str, Any] = {
        "method": method.upper(),
        "header": headers,
        "url": url_obj,
    }
    if body and method in ("post", "put", "patch", "delete"):
        if body["mode"] == "raw" and method in ("post", "put", "patch"):
            req["body"] = body
        elif body["mode"] == "formdata":
            req["body"] = body

    name = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"
    return {"name": name, "request": req}


def openapi_to_postman(spec: dict[str, Any], collection_name: str, base_var: str) -> dict[str, Any]:
    paths = spec.get("paths") or {}
    methods = ("get", "post", "put", "patch", "delete", "options", "head")

    by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path, path_item in sorted(paths.items()):
        for m in methods:
            if m not in path_item:
                continue
            op = path_item[m]
            if op.get("include_in_schema") is False:
                continue
            item = _operation_to_request(spec, m, path, op, base_var)
            tags = op.get("tags") or ["default"]
            tag = tags[0]
            by_tag[tag].append(item)

    folder_items: list[dict[str, Any]] = []
    for tag in sorted(by_tag.keys()):
        folder_items.append({"name": tag, "item": by_tag[tag]})

    return {
        "info": {
            "name": collection_name,
            "description": (
                "Auto-generated from FastAPI OpenAPI.\n\n"
                "**URLs:** Each request includes `protocol`, `host`, `port`, and `path` so Postman shows the route. "
                "`raw` uses `{{baseUrl}}` — set **Collection variables → baseUrl** to `http://localhost:18000` "
                "(no trailing slash). If the address bar is empty, open the collection and confirm `baseUrl` is set.\n\n"
                "**Auth:** Call **Login** under `auth`, then copy `session_token` from response **Headers** → `Set-Cookie`, "
                "and add header `Cookie: session_token=<value>` on other requests (or use Postman Cookies)."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {
                "key": base_var,
                "value": "http://localhost:18000",
                "type": "string",
            },
        ],
        "item": folder_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="postman/Cosolvent-API.postman_collection.json")
    parser.add_argument("--name", default="Cosolvent API")
    parser.add_argument(
        "--base-var", default="baseUrl", help="Collection variable name for API base URL"
    )
    args = parser.parse_args()

    from app.main import app

    spec = app.openapi()
    collection = openapi_to_postman(spec, args.name, args.base_var)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {out_path} ({len(collection['item'])} folders)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
