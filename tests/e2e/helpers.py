"""Shared helpers for integration and end-to-end API tests."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from urllib.parse import urlparse, urlunparse

import httpx
import pytest


def require_mode(flag_name: str) -> None:
    if os.getenv(flag_name) != "1":
        pytest.skip(f"{flag_name}=1 required to run this suite")


def get_base_url(env_name: str, default: str = "http://localhost:18000") -> str:
    return os.getenv(env_name, default).rstrip("/")


def random_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def http_to_ws(http_url: str) -> str:
    parsed = urlparse(http_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "", "", "", ""))


def new_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=20.0, follow_redirects=True)


async def bootstrap_or_login_admin(
    client: httpx.AsyncClient, email: str, password: str
) -> dict:
    resp = await client.post(
        "/api/auth/bootstrap",
        json={"email": email, "password": password},
    )
    if resp.status_code == 200:
        body = resp.json()
        token = client.cookies.get("session_token")
        if token:
            body["session_token"] = token
        return body
    if resp.status_code == 409:
        login = await client.post("/api/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        body = login.json()
        token = client.cookies.get("session_token")
        if token:
            body["session_token"] = token
        return body
    resp.raise_for_status()
    return {}


async def signup_user(
    client: httpx.AsyncClient, email: str, password: str, participant_type: str
) -> dict:
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": password,
            "participant_type": participant_type,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    token = client.cookies.get("session_token")
    if token:
        body["session_token"] = token
    return body


def _default_field_value(field: dict) -> object:
    field_type = field.get("type")
    options = field.get("options") or []
    if field_type == "number":
        return 1
    if field_type == "multi_select":
        return [options[0]] if options else ["sample"]
    if field_type == "select":
        return options[0] if options else "sample"
    if field_type == "date":
        return "2026-01-01"
    if field_type == "file":
        return "sample-file"
    if field_type == "location":
        return {"text": "sample-location"}
    return f"sample-{field.get('name', 'value')}"


def _alias_candidates(name: str) -> list[str]:
    aliases: dict[str, list[str]] = {
        "organization_name": ["org_name"],
        "org_name": ["organization_name"],
    }
    generated = []
    if name.endswith("_name"):
        generated.append(name.replace("_name", ""))
    if name.startswith("org_"):
        generated.append(name.replace("org_", "organization_", 1))
    if name.startswith("organization_"):
        generated.append(name.replace("organization_", "org_", 1))
    return aliases.get(name, []) + generated


async def _coerce_fields_to_current_schema(
    client: httpx.AsyncClient, type_slug: str, supplied_fields: dict
) -> dict:
    template = await client.get("/api/setup/config-template")
    template.raise_for_status()
    config = template.json().get("config", {})
    schema = (((config.get("profile_schemas") or {}).get(type_slug) or {}).get("sections") or [])
    schema_fields: list[dict] = []
    for section in schema:
        schema_fields.extend(section.get("fields") or [])

    if not schema_fields:
        return supplied_fields

    result: dict[str, object] = {}
    for field in schema_fields:
        name = str(field.get("name", ""))
        if not name:
            continue
        if name in supplied_fields:
            result[name] = supplied_fields[name]
            continue
        alias_used = False
        for alias in _alias_candidates(name):
            if alias in supplied_fields:
                result[name] = supplied_fields[alias]
                alias_used = True
                break
        if alias_used:
            continue
        if field.get("required"):
            result[name] = _default_field_value(field)

    # Keep explicitly supplied fields that still exist in schema.
    valid_names = {str(field.get("name", "")) for field in schema_fields}
    for key, value in supplied_fields.items():
        if key in valid_names:
            result[key] = value
    return result


async def _onboarding_requires_document(client: httpx.AsyncClient, type_slug: str) -> bool:
    template = await client.get("/api/setup/config-template")
    template.raise_for_status()
    config = template.json().get("config", {})
    onboarding = (config.get("onboarding") or {}).get(type_slug) or {}
    return bool(onboarding.get("document_upload_required"))


async def register_update_submit(
    client: httpx.AsyncClient, type_slug: str, fields: dict
) -> dict:
    reg = await client.post(f"/api/profiles/{type_slug}/register")
    reg.raise_for_status()
    draft_id = reg.json()["id"]

    payload_fields = await _coerce_fields_to_current_schema(client, type_slug, fields)
    upd = await client.put(f"/api/profiles/{type_slug}/draft", json={"fields": payload_fields})
    upd.raise_for_status()

    if await _onboarding_requires_document(client, type_slug):
        upload = await client.post(
            "/api/files/upload",
            data={"privacy": "private", "category": "onboarding", "profile_id": draft_id},
            files={"file": ("onboarding.txt", b"onboarding-document", "text/plain")},
        )
        upload.raise_for_status()

    sub = await client.post(f"/api/profiles/{type_slug}/draft/submit")
    sub.raise_for_status()
    return sub.json()


async def wait_for(
    fetcher,
    predicate,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.5,
):
    start = time.monotonic()
    while True:
        value = await fetcher()
        if predicate(value):
            return value
        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError("wait_for timed out")
        await asyncio.sleep(interval_seconds)
