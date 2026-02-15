"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import close_db, connect_db
from app.core.exceptions import register_exception_handlers
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.middleware import register_middleware
from app.core.redis import close_redis, connect_redis

logger = logging.getLogger("cosolvent")


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Load marketplace config early — fail fast on bad config
    mc = load_marketplace_config(settings.marketplace_config_path)
    set_marketplace_config(mc)
    logger.info("Loaded marketplace config: %s", mc.marketplace.name)

    application = FastAPI(
        title=mc.marketplace.name,
        description=mc.marketplace.description,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    register_exception_handlers(application)
    register_middleware(application)

    # ── lifecycle events ─────────────────────────────────────────
    @application.on_event("startup")
    async def on_startup() -> None:
        await connect_db()
        await connect_redis()
        logger.info("Database and Redis connected")

    @application.on_event("shutdown")
    async def on_shutdown() -> None:
        await close_redis()
        await close_db()
        logger.info("Connections closed")

    # ── health check ─────────────────────────────────────────────
    @application.get("/api/health")
    async def health():
        return {"status": "ok", "marketplace": mc.marketplace.name}

    # ── register routers (added in later phases) ─────────────────
    _register_routers(application)

    return application


def _register_routers(application: FastAPI) -> None:
    """Import and include module routers."""
    from app.modules.admin.router import router as admin_router
    from app.modules.ai.router import router as ai_router
    from app.modules.auth.router import router as auth_router
    from app.modules.communication.router import router as comms_router
    from app.modules.discovery.router import router as discovery_router
    from app.modules.files.router import router as files_router
    from app.modules.notifications.router import router as notif_router
    from app.modules.profiles.router import router as profiles_router

    application.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    application.include_router(profiles_router, prefix="/api/profiles", tags=["profiles"])
    application.include_router(files_router, prefix="/api/files", tags=["files"])
    application.include_router(comms_router, prefix="/api", tags=["communication"])
    application.include_router(discovery_router, prefix="/api/search", tags=["discovery"])
    application.include_router(notif_router, prefix="/api/notifications", tags=["notifications"])
    application.include_router(ai_router, prefix="/api/ai", tags=["ai"])
    application.include_router(admin_router, prefix="/api/admin", tags=["admin"])


app = create_app()
