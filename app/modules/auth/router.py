from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response

from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth import service
from app.modules.auth.schemas import (
    AuthResponse,
    BootstrapRequest,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter()


@router.post("/signup", response_model=AuthResponse)
async def signup(
    body: SignupRequest,
    response: Response,
    config: MarketplaceConfig = Depends(get_config),
):
    result = await service.signup(body.email, body.password, body.participant_type, config)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
    )
    return result


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response):
    result = await service.login(body.email, body.password)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
    )
    return result


@router.post("/logout")
async def logout(response: Response, session_token: str = Cookie(None)):
    if session_token:
        await service.logout(session_token)
    response.delete_cookie("session_token")
    return {"detail": "Logged out"}


@router.get("/verify", response_model=UserResponse)
async def verify(user: dict = Depends(get_current_user)):
    return await service.verify(user)


@router.post("/bootstrap", response_model=AuthResponse)
async def bootstrap(body: BootstrapRequest, response: Response):
    result = await service.bootstrap_admin(body.email, body.password)
    response.set_cookie(
        "session_token",
        result["session_token"],
        httponly=True,
        samesite="lax",
    )
    return result
