from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response

from app.core.config import settings
from app.core.dependencies import (
    extract_bearer_token,
    get_config,
    get_current_user,
    require_session_principal,
)
from app.core import rate_limit
from app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
)
from app.core.marketplace_config import MarketplaceConfig
from app.modules.auth import api_keys, audit, service
from app.modules.auth.cookies import clear_session_cookie, set_session_cookie
from app.modules.auth.signup_policy import public_signup_allowed
from app.modules.auth.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    AuthResponse,
    BootstrapRequest,
    DemoPersonaRequest,
    DemoPersonaResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter()


def _wants_bearer(request: Request) -> bool:
    """True when the caller explicitly asked for a bearer credential.

    Opt-in via ``X-Auth-Mode: bearer``. The session cookie is HttpOnly precisely
    so page scripts cannot read the session token; returning that same value in
    the JSON body hands it to JavaScript anyway, and any client that parks it in
    localStorage turns one XSS into full session theft. Same-origin browser
    clients therefore never receive it — only callers that cannot use cookies
    (native apps, server-to-server, cross-site frontends) ask for it deliberately.
    """
    return (request.headers.get("x-auth-mode") or "").strip().lower() == "bearer"


def _public_auth_response(result: dict, request: Request | None = None) -> dict:
    """Shape the service result for the client.

    The internal ``session_token`` key never leaves as-is. It is re-exposed as
    ``access_token`` (GAP-1) only when the caller opts in — the bearer credential
    a cross-origin frontend, native app, or server-to-server caller sends back as
    ``Authorization: Bearer <access_token>`` when it cannot rely on the cookie.
    Everyone else gets the HttpOnly cookie alone.
    """
    body = {k: v for k, v in result.items() if k != "session_token"}
    if request is not None and _wants_bearer(request):
        body["access_token"] = result["session_token"]
    return body


@router.post("/signup", response_model=AuthResponse)
async def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    config: MarketplaceConfig = Depends(get_config),
):
    if not public_signup_allowed(config):
        raise ForbiddenError("Public signup is disabled")
    result = await service.signup(body.email, body.password, body.participant_type, config)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result, request)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    # CORS is a browser control and does nothing about scripted credential
    # stuffing, so login carries its own throttle (see core/rate_limit.py).
    ip = audit.client_ip(request)
    retry_after = await rate_limit.check_login_attempt(ip, body.email)
    if retry_after is not None:
        await audit.record(audit.LOGIN_THROTTLED, email=body.email, request=request)
        raise TooManyRequestsError(
            "Too many login attempts. Try again later.", retry_after=retry_after
        )

    try:
        result = await service.login(body.email, body.password)
    except AppError:
        # Recorded before re-raising so failures are visible even though the
        # response deliberately stays vague about which credential was wrong.
        await audit.record(audit.LOGIN_FAILED, email=body.email, request=request)
        raise

    set_session_cookie(response, result["session_token"])
    await audit.record(
        audit.LOGIN_SUCCEEDED,
        user_id=result.get("user_id"),
        email=body.email,
        request=request,
        detail={"bearer_requested": _wants_bearer(request)},
    )
    return _public_auth_response(result, request)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session_token: str = Cookie(None),
    authorization: str = Header(None),
):
    token = extract_bearer_token(authorization) or session_token
    if token:
        await service.logout(token)
    clear_session_cookie(response)
    await audit.record(audit.LOGOUT, request=request)
    return {"detail": "Logged out"}


@router.get("/verify", response_model=UserResponse)
@router.get("/me", response_model=UserResponse)
async def verify(user: dict = Depends(get_current_user)):
    return await service.verify(user)


@router.post("/bootstrap", response_model=AuthResponse)
async def bootstrap(body: BootstrapRequest, request: Request, response: Response):
    result = await service.bootstrap_admin(body.email, body.password)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result, request)


@router.post("/demo-persona", response_model=DemoPersonaResponse)
async def demo_persona(
    body: DemoPersonaRequest,
    request: Request,
    response: Response,
    config: MarketplaceConfig = Depends(get_config),
):
    """Log in as a random synthetic participant of the requested type — never
    available outside demo mode (see assign_demo_persona's docstring for why)."""
    if settings.demo_mode == "off":
        raise ForbiddenError("Persona assignment is only available in demo mode")
    result = await service.assign_demo_persona(body.participant_type, config)
    set_session_cookie(response, result["session_token"])
    return _public_auth_response(result, request)


# ── API keys (GAP-1) ─────────────────────────────────────────────────────
# Credentials for callers with no cookie jar. Managed through `require_session_principal`
# — never by API key — so a stolen key cannot mint further keys and outlive its own
# revocation.

@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    request: Request,
    user: dict = Depends(require_session_principal),
):
    try:
        plaintext, record = await api_keys.create_api_key(
            user["_id"], body.name, scopes=body.scopes, expires_in_days=body.expires_in_days
        )
    except ValueError as exc:
        # Unknown scope is a client mistake, not a server fault.
        raise AppError(str(exc), 422) from exc

    await audit.record(
        audit.API_KEY_CREATED,
        user_id=user["_id"],
        email=user.get("email"),
        request=request,
        detail={
            "api_key_id": str(record["_id"]),
            "name": record["name"],
            "scopes": record["scopes"],
            "expires_at": record["expires_at"].isoformat() if record.get("expires_at") else None,
        },
    )
    return ApiKeyCreatedResponse(
        id=str(record["_id"]),
        name=record["name"],
        api_key=plaintext,
        scopes=record["scopes"],
        expires_at=record.get("expires_at"),
        created_at=record.get("created_at"),
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(user: dict = Depends(require_session_principal)):
    return await api_keys.list_api_keys(user["_id"])


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    user: dict = Depends(require_session_principal),
):
    if not await api_keys.revoke_api_key(user["_id"], key_id):
        raise NotFoundError("API key not found")
    await audit.record(
        audit.API_KEY_REVOKED,
        user_id=user["_id"],
        email=user.get("email"),
        request=request,
        detail={"api_key_id": key_id},
    )
    return {"detail": "API key revoked"}
