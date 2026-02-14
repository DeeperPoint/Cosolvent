"""WebSocket connection manager for real-time messaging."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("cosolvent.ws")


class ConnectionManager:
    """Manages active WebSocket connections per conversation."""

    def __init__(self):
        self._connections: dict[str, list[tuple[str, WebSocket]]] = {}

    async def connect(self, conversation_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        if conversation_id not in self._connections:
            self._connections[conversation_id] = []
        self._connections[conversation_id].append((user_id, ws))
        logger.info("WS connected: user=%s conv=%s", user_id, conversation_id)

    def disconnect(self, conversation_id: str, user_id: str, ws: WebSocket | None = None) -> None:
        if conversation_id in self._connections:
            if ws:
                self._connections[conversation_id] = [
                    (uid, w) for uid, w in self._connections[conversation_id] if w is not ws
                ]
            else:
                self._connections[conversation_id] = [
                    (uid, w) for uid, w in self._connections[conversation_id] if uid != user_id
                ]
            if not self._connections[conversation_id]:
                del self._connections[conversation_id]
        logger.info("WS disconnected: user=%s conv=%s", user_id, conversation_id)

    async def broadcast(self, conversation_id: str, message: dict[str, Any]) -> None:
        conns = self._connections.get(conversation_id, [])
        data = json.dumps(message, default=str)
        for uid, ws in conns:
            try:
                await ws.send_text(data)
            except Exception:
                logger.warning("Failed to send to user=%s", uid)


manager = ConnectionManager()
