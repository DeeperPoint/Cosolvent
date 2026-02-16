"""Tests for WebSocket auth/session enforcement."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.modules.communication.router import WS_CLOSE_AUTH, router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_ws_rejects_expired_session_token(client: TestClient):
    with patch(
        "app.modules.communication.router.get_current_user_from_token",
        new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Session expired")),
    ), patch(
        "app.modules.communication.router.service.get_conversation",
        new=AsyncMock(return_value={"id": "conv-1"}),
    ):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/ws/conv-1") as ws:
                ws.send_json({"type": "auth", "token": "expired-token"})
                ws.receive_json()

    assert exc.value.code == WS_CLOSE_AUTH


def test_ws_revalidates_session_during_message_loop(client: TestClient):
    token_checks = AsyncMock(
        side_effect=[
            {"_id": "user-1", "role": "user"},
            {"_id": "user-1", "role": "user"},
            HTTPException(status_code=401, detail="Session expired"),
        ]
    )

    with patch(
        "app.modules.communication.router.get_current_user_from_token",
        new=token_checks,
    ), patch(
        "app.modules.communication.router.service.get_conversation",
        new=AsyncMock(return_value={"id": "conv-1"}),
    ):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/ws/conv-1") as ws:
                ws.send_json({"type": "auth", "token": "token-123"})
                assert ws.receive_json()["type"] == "connected"

                ws.send_json({"type": "ping"})
                assert ws.receive_json()["type"] == "pong"

                ws.send_json({"type": "ping"})
                ws.receive_json()

    assert exc.value.code == WS_CLOSE_AUTH
    assert token_checks.await_count == 3
