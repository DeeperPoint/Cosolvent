from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Response

from app.core.config import settings
from app.core.dependencies import extract_bearer_token, get_config, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth import service
from app.modules.auth.cookies import clear_session_cookie, set_session_cookie
from app.modules.auth.signup_policy import public_signup_allowed
from app.modules.auth.schemas import (
    AuthResponse,
    BootstrapRequest,
    DemoPersonaRequest,
    DemoPersonaResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter()


def _public_auth_response(result: dict) -> dict:
    """Shape the service result for the client.

    The internal ``session_token`` key never leaves as-is; it's re-exposed as
    ``access_token`` (GAP-1) — the bearer credential a cross-origin frontend, native app,
    or server-to-server caller sends back as ``Authorization: Bearer <access_token>`` when
    it can't rely on the cookie. Browsers on the API's own origin can ignore the field
    entirely and rely on the HttpOnly cookie set alongside it; nothing about the cookie's
    behavior changes.
    """
    body = {k: v for k, v in result.items() if k != "session_token"}
    body["access_token"] = result["session_token"]
    return body


@router.post("/signup", response_model=AuthResponse)
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


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str = Cookie(None),
    authorization: str = Header(None),
):
    token = extract_bearer_token(authorization) or session_token
    if token:
        await service.logout(token)
    clear_session_cookie(response)
    return {"detail": "Logged out"}


@router.get("/verify", response_model=UserResponse)
@router.get("/me", response_model=UserResponse)
async def verify(user: dict = Depends(get_current_user)):
    return await service.verify(user)


@router.post("/bootstrap", response_model=AuthResponse)
async def bootstrap(body: BootstrapRequest, response: Response):
    result = await service.bootstrap_admin(body.email, body.password)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result)


@router.post("/demo-persona", response_model=DemoPersonaResponse)
async def demo_persona(
    body: DemoPersonaRequest,
    response: Response,
    config: MarketplaceConfig = Depends(get_config),
):
    """Log in as a random synthetic participant of the requested type — never
    available outside demo mode (see assign_demo_persona's docstring for why)."""
    if settings.demo_mode == "off":
        raise ForbiddenError("Persona assignment is only available in demo mode")
    result = await service.assign_demo_persona(body.participant_type, config)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result)
