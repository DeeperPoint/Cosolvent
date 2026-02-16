from __future__ import annotations

import pytest

from app.modules.communication.websocket import ConnectionManager


class _SocketOK:
    def __init__(self):
        self.messages: list[str] = []

    async def send_text(self, data: str) -> None:
        self.messages.append(data)


class _SocketFail:
    async def send_text(self, _data: str) -> None:
        raise RuntimeError("socket write failed")


@pytest.mark.asyncio
async def test_broadcast_prunes_failed_connections():
    manager = ConnectionManager()
    ok = _SocketOK()
    bad = _SocketFail()
    manager.register("c1", "u1", ok)  # type: ignore[arg-type]
    manager.register("c1", "u2", bad)  # type: ignore[arg-type]

    await manager.broadcast("c1", {"type": "new_message", "message": {"id": "m1"}})

    assert len(ok.messages) == 1
    assert "c1" in manager._connections
    assert len(manager._connections["c1"]) == 1
    assert manager._connections["c1"][0][0] == "u1"
