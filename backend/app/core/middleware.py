"""CORS and request logging middleware."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("cosolvent")

# Methods that mutate state — blocked when the instance is in read-only Demo (showcase) mode.
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Write paths that must stay allowed even in showcase mode: auth (persona assignment)
# and the admin-triggered precompute refresh — showcase mode blocks *participant*
# writes, not the operator's ability to update pre-computed content (demo-mode-spec:
# "Admin access ... remains accessible ... for updating pre-computed content").
# `run_showcase_precompute` is itself gated by require_admin, so this doesn't open
# the path to unauthenticated writes.
_SHOWCASE_WRITE_ALLOWLIST = (
    "/api/auth/login", "/api/auth/logout", "/api/auth/signup",
    "/api/admin/showcase/run",
)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Without this every cross-origin call pays an extra OPTIONS round trip.
        # 10 minutes is the effective ceiling in Chromium; Firefox caps at 24h.
        max_age=600,
    )

    @app.middleware("http")
    async def enforce_origin_on_cookie_writes(request: Request, call_next):
        """Restore CSRF protection when cross-site cookies are enabled (GAP-1).

        `SameSite=lax` is what currently stops a cross-site form POST from carrying
        the session cookie. Setting it to `none` — which a sponsor frontend on its
        own origin requires — removes that protection, and CORS does not replace
        it: a simple form POST is never preflighted, so the request executes and
        only the *response* is withheld from the attacker.

        So while cross-site cookies are enabled, a state-changing request relying
        on the ambient cookie must carry an allowlisted Origin. Bearer and API-key
        callers are exempt: those credentials are attached deliberately by the
        client, never automatically by the browser, so they cannot be ridden.
        """
        if (
            settings.session_cookie_samesite == "none"
            and request.method in _WRITE_METHODS
            and request.cookies.get("session_token")
            and not request.headers.get("authorization")
            and not request.headers.get("x-api-key")
        ):
            origin = request.headers.get("origin")
            if origin is None or origin not in settings.cors_origins:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Cross-site request rejected: a cookie-authenticated write "
                            "must come from an allowlisted origin."
                        )
                    },
                )
        return await call_next(request)

    @app.middleware("http")
    async def demo_mode_readonly(request: Request, call_next):
        # Mode 1 (showcase): the whole instance is read-only — block DB writes so a public
        # demo cannot be mutated or run up costs (story-progression §11 / demo-mode-spec).
        if (
            settings.demo_mode == "showcase"
            and request.method in _WRITE_METHODS
            and not request.url.path.startswith(_SHOWCASE_WRITE_ALLOWLIST)
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Demo showcase mode is read-only — writes are disabled."},
            )
        return await call_next(request)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response
