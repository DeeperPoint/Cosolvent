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
    )

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
