from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response, status
from pydantic import BaseModel

from app.core.dependencies import get_config, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth import repository as auth_repo
from app.modules.auth import service
from app.modules.auth.cookies import clear_session_cookie, set_session_cookie
from app.modules.auth.signup_policy import public_signup_allowed
from app.modules.auth.schemas import (
    AuthResponse,
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter()


def _public_auth_response(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "session_token"}


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user account",
)
async def signup(
    body: SignupRequest,
    response: Response,
    config: MarketplaceConfig = Depends(get_config),
):
    if not public_signup_allowed(config):
        raise ForbiddenError("Public signup is disabled")
    result = await service.signup(body.email, body.password, body.participant_type, config)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response):
    result = await service.login(body.email, body.password)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result)


class _DetailResponse(BaseModel):
    detail: str


@router.post("/logout", response_model=_DetailResponse)
async def logout(response: Response, session_token: str = Cookie(None)):
    if session_token:
        await service.logout(session_token)
    clear_session_cookie(response)
    return {"detail": "Logged out"}


@router.get(
    "/verify",
    response_model=UserResponse,
    responses={401: {"description": "Not authenticated"}},
)
@router.get(
    "/me",
    response_model=UserResponse,
    responses={401: {"description": "Not authenticated"}},
)
async def verify(user: dict = Depends(get_current_user)):
    return await service.verify(user)


@router.post("/bootstrap", response_model=AuthResponse)
async def bootstrap(body: BootstrapRequest, response: Response):
    result = await service.bootstrap_admin(body.email, body.password)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result)


@router.post(
    "/change-password",
    response_model=_DetailResponse,
    summary="Change the current user's password",
)
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
):
    from app.core.exceptions import AppError
    try:
        await service.change_password(user, body.current_password, body.new_password)
    except ValueError as exc:
        raise AppError(str(exc), status_code=422)
    return {"detail": "Password updated"}


class _WsTicketResponse(BaseModel):
    ticket: str
    expires_in: int


@router.get(
    "/ws-ticket",
    response_model=_WsTicketResponse,
    summary="Issue a short-lived WebSocket auth ticket",
)
async def ws_ticket(user: dict = Depends(get_current_user)):
    """Exchange a session cookie for a one-shot ticket the browser can pass
    in the WebSocket auth message. HttpOnly cookies aren't reliably attached
    to cross-port WS upgrades, so the JS client uses this ticket instead."""
    token, ttl = await auth_repo.create_ws_ticket(str(user["_id"]))
    return {"ticket": token, "expires_in": ttl}
