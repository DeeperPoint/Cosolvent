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
        return resp.json()
    if resp.status_code == 409:
        login = await client.post("/api/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        return login.json()
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
    return resp.json()


async def register_update_submit(
    client: httpx.AsyncClient, type_slug: str, fields: dict
) -> dict:
    reg = await client.post(f"/api/profiles/{type_slug}/register")
    reg.raise_for_status()

    upd = await client.put(f"/api/profiles/{type_slug}/draft", json={"fields": fields})
    upd.raise_for_status()

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
