from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Path, Query, WebSocket, WebSocketDisconnect

from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.communication import service
from app.modules.communication.schemas import (
    CreateConversationRequest,
    EditMessageRequest,
    SendMessageRequest,
    ShareAssetsRequest,
)
from app.modules.communication.websocket import manager

router = APIRouter()


@router.post("/conversations")
async def create_conversation(
    body: CreateConversationRequest,
    user: dict = Depends(get_current_user),
    config: MarketplaceConfig = Depends(get_config),
):
    return await service.create_conversation(user, body.receiver_user_id, body.initial_message, config)


@router.get("/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    return await service.list_conversations(user)


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.get_conversation(conv_id, user)


@router.post("/conversations/{conv_id}/accept")
async def accept_conversation(conv_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.accept_conversation(conv_id, user)


@router.post("/conversations/{conv_id}/reject")
async def reject_conversation(conv_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.reject_conversation(conv_id, user)


@router.post("/conversations/{conv_id}/close")
async def close_conversation(conv_id: str = Path(...), user: dict = Depends(get_current_user)):
    return await service.close_conversation(conv_id, user)


@router.get("/conversations/{conv_id}/messages")
async def list_messages(
    conv_id: str = Path(...),
    skip: int = Query(0),
    limit: int = Query(50),
    user: dict = Depends(get_current_user),
):
    return await service.list_messages(conv_id, user, skip, limit)


@router.post("/conversations/{conv_id}/messages")
async def send_message(
    body: SendMessageRequest,
    conv_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    msg = await service.send_message(conv_id, user, body.content, body.content_type)
    # Broadcast via WebSocket
    await manager.broadcast(conv_id, {"type": "new_message", "message": msg})
    return msg


@router.put("/conversations/{conv_id}/messages/{msg_id}")
async def edit_message(
    body: EditMessageRequest,
    conv_id: str = Path(...),
    msg_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    msg = await service.edit_message(conv_id, msg_id, user, body.content)
    await manager.broadcast(conv_id, {"type": "message_edited", "message": msg})
    return msg


@router.delete("/conversations/{conv_id}/messages/{msg_id}")
async def delete_message(
    conv_id: str = Path(...),
    msg_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    await service.delete_message(conv_id, msg_id, user)
    await manager.broadcast(conv_id, {"type": "message_deleted", "message_id": msg_id})
    return {"detail": "Deleted"}


@router.post("/conversations/{conv_id}/share-assets")
async def share_assets(
    body: ShareAssetsRequest,
    conv_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    return await service.share_assets(conv_id, user, body.asset_ids)


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for real-time messaging.

    Client must send an auth message first: {"type": "auth", "token": "session_token"}
    """
    # Accept and wait for auth message
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        data = json.loads(raw)
        if data.get("type") != "auth" or not data.get("token"):
            await websocket.close(code=4001, reason="Auth required")
            return

        # Verify session
        from app.core.database import get_collection
        session = await get_collection("sessions").find_one({"token": data["token"]})
        if not session:
            await websocket.close(code=4001, reason="Invalid session")
            return

        user_id = str(session["user_id"])

        # Verify participant
        conv = await get_collection("conversations").find_one({"_id": conversation_id})
        if not conv:
            await websocket.close(code=4004, reason="Conversation not found")
            return
        participant_ids = [p["user_id"] for p in conv["participants"]]
        if user_id not in participant_ids:
            await websocket.close(code=4003, reason="Not a participant")
            return

        # Re-register with manager (we already accepted above, so just track)
        if conversation_id not in manager._connections:
            manager._connections[conversation_id] = []
        manager._connections[conversation_id].append((user_id, websocket))

        await websocket.send_text(json.dumps({"type": "connected", "user_id": user_id}))

        # Message loop
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            if data.get("type") == "message":
                from app.modules.communication import repository as comms_repo
                msg = await comms_repo.create_message(
                    conversation_id, user_id, data.get("content", ""), data.get("content_type", "text")
                )
                response = {
                    "type": "new_message",
                    "message": {
                        "id": str(msg["_id"]),
                        "conversation_id": conversation_id,
                        "sender_id": user_id,
                        "content": msg["content"],
                        "content_type": msg["content_type"],
                        "created_at": str(msg["created_at"]),
                    },
                }
                await manager.broadcast(conversation_id, response)
            elif data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(conversation_id, user_id if "user_id" in dir() else "", websocket)
