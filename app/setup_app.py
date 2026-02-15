"""Standalone onboarding/setup app that does not require marketplace.yaml at startup."""

from __future__ import annotations

from fastapi import FastAPI

from app.modules.setup.router import router as setup_router


def create_setup_app() -> FastAPI:
    application = FastAPI(
        title="Cosolvent Setup",
        description="Onboarding/configuration service",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    @application.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "setup"}

    application.include_router(setup_router, tags=["setup"])
    return application


app = create_setup_app()
