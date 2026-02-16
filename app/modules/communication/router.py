from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query, WebSocket, WebSocketDisconnect

from app.core.dependencies import get_config, get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
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

WS_CLOSE_AUTH = 4001
WS_CLOSE_BAD_REQUEST = 4002
WS_CLOSE_FORBIDDEN = 4003
WS_CLOSE_NOT_FOUND = 4004
WS_CLOSE_POLICY = 4008


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
    session_token: str | None = None
    user_id = ""
    try:
        raw = await websocket.receive_text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.close(code=WS_CLOSE_BAD_REQUEST, reason="Invalid payload")
            return

        if data.get("type") != "auth":
            await websocket.close(code=WS_CLOSE_AUTH, reason="Auth required")
            return

        session_token = data.get("token") or websocket.cookies.get("session_token")
        if not session_token:
            await websocket.close(code=WS_CLOSE_AUTH, reason="Auth required")
            return

        user = await get_current_user(session_token)
        user_id = user["_id"]

        await service.get_conversation(conversation_id, user)

        manager.register(conversation_id, user_id, websocket)

        await websocket.send_text(json.dumps({"type": "connected", "user_id": user_id}))

        # Message loop
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.close(code=WS_CLOSE_BAD_REQUEST, reason="Invalid payload")
                break

            if data.get("type") == "message":
                if not session_token:
                    await websocket.close(code=WS_CLOSE_AUTH, reason="Auth required")
                    break
                user = await get_current_user(session_token)
                msg = await service.send_message(
                    conversation_id,
                    user,
                    data.get("content", ""),
                    data.get("content_type", "text"),
                )
                response = {
                    "type": "new_message",
                    "message": msg,
                }
                await manager.broadcast(conversation_id, response)
            elif data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except HTTPException as exc:
        if exc.status_code == 401:
            await websocket.close(code=WS_CLOSE_AUTH, reason="Invalid session")
        elif exc.status_code == 403:
            await websocket.close(code=WS_CLOSE_FORBIDDEN, reason="Forbidden")
        elif exc.status_code == 404:
            await websocket.close(code=WS_CLOSE_NOT_FOUND, reason="Not found")
        else:
            await websocket.close(code=WS_CLOSE_BAD_REQUEST, reason="Authorization failed")
    except ForbiddenError as exc:
        reason = str(exc.message)
        if "not active" in reason.lower():
            await websocket.close(code=WS_CLOSE_POLICY, reason="Conversation is not active")
        else:
            await websocket.close(code=WS_CLOSE_FORBIDDEN, reason="Forbidden")
    except NotFoundError:
        await websocket.close(code=WS_CLOSE_NOT_FOUND, reason="Conversation not found")

    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close(code=WS_CLOSE_BAD_REQUEST, reason="Connection error")
    finally:
        manager.disconnect(conversation_id, user_id, websocket)
