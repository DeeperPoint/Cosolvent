"""E2E test fixtures.

These tests talk to a **live FastAPI stack** (by default at
``http://localhost:18000``) and a real Postgres + Redis.  They are gated
by ``RUN_E2E=1`` so they don't run in unit/CI-lite modes.

Environment variables:

- ``RUN_E2E`` (required): set to ``1`` to enable the suite.
- ``E2E_BASE_URL`` (optional): override the API base URL. Default:
  ``http://localhost:18000``.
- ``E2E_ADMIN_EMAIL`` / ``E2E_ADMIN_PASSWORD`` (optional): credentials
  used to bootstrap-or-login the admin account.

Separation from the production DB is the caller's responsibility: point
the running backend at a dedicated Postgres database (e.g. via
``docker-compose -f docker-compose.test.yml up``).  The fixtures below
create unique test users (random email prefixes) so a run can be repeated
without collisions; cleanup is best-effort via admin APIs.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from tests.e2e.contract import (
    MarketplaceContract,
    OpenAPIContract,
    load_marketplace_contract,
    load_openapi_contract,
)
from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    new_client,
    random_email,
    register_update_submit,
    require_mode,
    signup_user,
)

_ADMIN_EMAIL_DEFAULT = "admin@example.com"
_ADMIN_PASSWORD_DEFAULT = "ChangeMe123!"
_USER_PASSWORD = "UserPass123!"


def _skip_unless_e2e() -> None:
    require_mode("RUN_E2E")


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    _skip_unless_e2e()
    return get_base_url("E2E_BASE_URL")


@pytest.fixture(scope="session")
def openapi_contract() -> OpenAPIContract:
    return load_openapi_contract()


@pytest.fixture(scope="session")
def marketplace_contract() -> MarketplaceContract:
    return load_marketplace_contract()


@pytest.fixture
async def admin_client(e2e_base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    email = os.getenv("E2E_ADMIN_EMAIL", _ADMIN_EMAIL_DEFAULT)
    password = os.getenv("E2E_ADMIN_PASSWORD", _ADMIN_PASSWORD_DEFAULT)
    client = new_client(e2e_base_url)
    try:
        await bootstrap_or_login_admin(client, email, password)
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def anonymous_client(e2e_base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    client = new_client(e2e_base_url)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def buyer_client(e2e_base_url: str) -> AsyncIterator[dict]:
    """Signed-up buyer user (not yet onboarded)."""

    client = new_client(e2e_base_url)
    try:
        auth = await signup_user(
            client,
            email=random_email("e2e-buyer"),
            password=_USER_PASSWORD,
            participant_type="buyer",
        )
        yield {"client": client, "auth": auth}
    finally:
        await client.aclose()


@pytest.fixture
async def onboarded_buyer(e2e_base_url: str) -> AsyncIterator[dict]:
    """Buyer who has completed the register→update→submit flow."""

    client = new_client(e2e_base_url)
    try:
        auth = await signup_user(
            client,
            email=random_email("e2e-buyer-ob"),
            password=_USER_PASSWORD,
            participant_type="buyer",
        )
        await register_update_submit(
            client,
            "buyer",
            {
                "org_name": "E2E Trading Co",
                "country": "Canada",
                "business_type": "Trading Company",
            },
        )
        yield {"client": client, "auth": auth}
    finally:
        await client.aclose()


@pytest.fixture
async def onboarded_producer(e2e_base_url: str) -> AsyncIterator[dict]:
    """Producer who has been signed up, submitted an application, and been approved."""

    admin_email = os.getenv("E2E_ADMIN_EMAIL", _ADMIN_EMAIL_DEFAULT)
    admin_password = os.getenv("E2E_ADMIN_PASSWORD", _ADMIN_PASSWORD_DEFAULT)

    producer_client = new_client(e2e_base_url)
    admin = new_client(e2e_base_url)
    try:
        await bootstrap_or_login_admin(admin, admin_email, admin_password)

        producer_auth = await signup_user(
            producer_client,
            email=random_email("e2e-producer-ob"),
            password=_USER_PASSWORD,
            participant_type="producer",
        )
        await register_update_submit(
            producer_client,
            "producer",
            {
                "farm_name": "E2E Valley Farm",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )
        apps = await admin.get("/api/admin/applications", params={"status": "pending"})
        apps.raise_for_status()
        pending = apps.json()
        app_row = next(
            (a for a in pending if a.get("user_id") == producer_auth["user_id"]),
            None,
        )
        if app_row is not None:
            approve = await admin.post(
                f"/api/admin/applications/{app_row['id']}/approve"
            )
            approve.raise_for_status()

        yield {"client": producer_client, "auth": producer_auth}
    finally:
        await producer_client.aclose()
        await admin.aclose()


@pytest.fixture
def random_suffix() -> str:
    return uuid.uuid4().hex[:10]
