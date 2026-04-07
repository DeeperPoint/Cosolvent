from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.main as main


def _fake_marketplace_config():
    return SimpleNamespace(
        marketplace=SimpleNamespace(name="Test Market", description=""),
    )


@pytest.mark.asyncio
async def test_startup_continues_when_redis_unavailable():
    with (
        patch("app.main.load_marketplace_config", return_value=_fake_marketplace_config()),
        patch("app.main.set_marketplace_config"),
        patch("app.main._register_routers"),
        patch("app.main.connect_db", new=AsyncMock()) as mock_connect_db,
        patch("app.main.connect_redis", new=AsyncMock(side_effect=RuntimeError("redis down"))) as mock_connect_redis,
    ):
        app = main.create_app()
        for handler in app.router.on_startup:
            await handler()

    mock_connect_db.assert_awaited_once()
    mock_connect_redis.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_closes_db_even_if_redis_close_fails():
    with (
        patch("app.main.load_marketplace_config", return_value=_fake_marketplace_config()),
        patch("app.main.set_marketplace_config"),
        patch("app.main._register_routers"),
        patch("app.main.close_redis", new=AsyncMock(side_effect=RuntimeError("redis close failed"))),
        patch("app.main.close_db", new=AsyncMock()) as mock_close_db,
    ):
        app = main.create_app()
        for handler in app.router.on_shutdown:
            await handler()

    mock_close_db.assert_awaited_once()
