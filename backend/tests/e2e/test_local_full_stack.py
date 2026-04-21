"""Local full-stack end-to-end validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    http_to_ws,
    new_client,
    random_email,
    register_update_submit,
    require_mode,
    signup_user,
)

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ChangeMe123!"
USER_PASSWORD = "UserPass123!"

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_ROOT.parent
_MARKETPLACE_EXAMPLE = _REPO_ROOT / "marketplace.example.yaml"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_local_full_stack_flow():
    require_mode("RUN_E2E")
    base_url = get_base_url("E2E_BASE_URL")
    ws_base = http_to_ws(base_url)

    validate = subprocess.run(
        [sys.executable, "-m", "cli", "validate", str(_MARKETPLACE_EXAMPLE)],
        cwd=_BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr

    admin = new_client(base_url)
    producer = new_client(base_url)
    buyer = new_client(base_url)

    try:
        health = await admin.get("/api/health")
        health.raise_for_status()

        await bootstrap_or_login_admin(admin, ADMIN_EMAIL, ADMIN_PASSWORD)

        producer_auth = await signup_user(
            producer,
            email=random_email("e2e-producer"),
            password=USER_PASSWORD,
            participant_type="producer",
        )
        await register_update_submit(
            producer,
            "producer",
            {
                "farm_name": "Valley Fields",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )

        apps = await admin.get("/api/admin/applications", params={"status": "pending"})
        apps.raise_for_status()
        pending = apps.json()
        producer_app = next(
            (item for item in pending if item.get("user_id") == producer_auth["user_id"]),
            None,
        )
        assert producer_app, "Expected pending application for producer"
        app_id = producer_app["id"]
        approve = await admin.post(f"/api/admin/applications/{app_id}/approve")
        approve.raise_for_status()

        producer_alias = await producer.get("/api/roles/producer/me")
        producer_alias.raise_for_status()
        assert producer_alias.json().get("participant_type") == "producer"

        buyer_auth = await signup_user(
            buyer,
            email=random_email("e2e-buyer"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )
        await register_update_submit(
            buyer,
            "buyer",
            {"org_name": "Global Flour Co", "country": "Canada", "business_type": "Mill"},
        )

        buyer_alias = await buyer.get("/api/roles/buyer/me")
        buyer_alias.raise_for_status()
        assert buyer_alias.json().get("participant_type") == "buyer"

        conv_resp = await buyer.post(
            "/api/conversations",
            json={
                "receiver_user_id": producer_auth["user_id"],
                "initial_message": "Can we discuss quantities?",
            },
        )
        conv_resp.raise_for_status()
        conv_id = conv_resp.json()["id"]

        accept = await producer.post(f"/api/conversations/{conv_id}/accept")
        accept.raise_for_status()

        ws_url = f"{ws_base}/api/ws/{conv_id}"
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"type": "auth", "token": buyer_auth["session_token"]}))
            connected_msg = json.loads(await ws.recv())
            assert connected_msg["type"] == "connected"

            await ws.send(json.dumps({"type": "ping"}))
            pong = json.loads(await ws.recv())
            assert pong["type"] == "pong"

        async with websockets.connect(
            ws_url,
            additional_headers={"Cookie": f"session_token={buyer_auth['session_token']}"},
        ) as ws_cookie_fallback:
            await ws_cookie_fallback.send(json.dumps({"type": "auth"}))
            connected_cookie = json.loads(await ws_cookie_fallback.recv())
            assert connected_cookie["type"] == "connected"

        async with websockets.connect(ws_url) as ws_invalid:
            await ws_invalid.send(json.dumps({"type": "auth", "token": "invalid-token"}))
            with pytest.raises(ConnectionClosed):
                await ws_invalid.recv()
            assert ws_invalid.close_code == 4001

        async with websockets.connect(ws_url) as ws_closed_conversation:
            await ws_closed_conversation.send(json.dumps({"type": "auth", "token": buyer_auth["session_token"]}))
            connected_msg = json.loads(await ws_closed_conversation.recv())
            assert connected_msg["type"] == "connected"

            close_conv = await producer.post(f"/api/conversations/{conv_id}/close")
            close_conv.raise_for_status()

            await ws_closed_conversation.send(
                json.dumps({"type": "message", "content": "should not persist", "content_type": "text"})
            )
            with pytest.raises(ConnectionClosed):
                await ws_closed_conversation.recv()
            assert ws_closed_conversation.close_code == 4008

        deactivated = await admin.post(f"/api/admin/users/{buyer_auth['user_id']}/deactivate")
        deactivated.raise_for_status()

        async with websockets.connect(ws_url) as ws_deactivated:
            await ws_deactivated.send(json.dumps({"type": "auth", "token": buyer_auth["session_token"]}))
            with pytest.raises(ConnectionClosed):
                await ws_deactivated.recv()
            assert ws_deactivated.close_code == 4003

        dashboard = await admin.get("/api/admin/dashboard")
        dashboard.raise_for_status()
        users = await admin.get("/api/admin/users")
        users.raise_for_status()
        assert isinstance(users.json(), list)
    finally:
        await admin.aclose()
        await producer.aclose()
        await buyer.aclose()
