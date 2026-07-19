from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response

from app.core.config import settings
from app.core.dependencies import get_config, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth import service
from app.modules.auth.cookies import set_session_cookie
from app.modules.auth.signup_policy import public_signup_allowed
from app.modules.auth.schemas import (
    AuthResponse,
    BootstrapRequest,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter()


def _public_auth_response(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "session_token"}


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
async def logout(response: Response, session_token: str = Cookie(None)):
    if session_token:
        await service.logout(session_token)
    response.delete_cookie(
        "session_token", secure=settings.session_cookie_secure, httponly=True, samesite="lax"
    )
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
