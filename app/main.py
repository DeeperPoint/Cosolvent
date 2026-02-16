"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.core.config import settings
from app.core.database import close_db, connect_db
from app.core.exceptions import register_exception_handlers
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config
from app.core.middleware import register_middleware
from app.core.redis import close_redis, connect_redis

logger = logging.getLogger("cosolvent")


def _runtime_config_path() -> Path:
    requested = Path(settings.marketplace_config_path)
    return requested.resolve() if requested.is_absolute() else (Path.cwd() / requested).resolve()


def _example_config_path(runtime_path: Path) -> Path:
    if runtime_path.suffix.lower() in {".yaml", ".yml"}:
        return runtime_path.with_name(f"{runtime_path.stem}.example{runtime_path.suffix}")
    return runtime_path.with_name("marketplace.example.yaml")


def _load_startup_marketplace_config():
    runtime_path = _runtime_config_path()
    try:
        return load_marketplace_config(runtime_path)
    except FileNotFoundError:
        example_path = _example_config_path(runtime_path)
        if not example_path.exists():
            raise
        logger.warning(
            "Marketplace config missing at %s; falling back to example config at %s",
            runtime_path,
            example_path,
        )
        return load_marketplace_config(example_path)


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Load marketplace config early — fail fast on bad config
    mc = _load_startup_marketplace_config()
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
        try:
            await connect_redis()
            logger.info("Database and Redis connected")
        except Exception:
            # Redis is optional for non-queue request paths; keep API available.
            logger.exception("Redis connection failed at startup; continuing without queue backend")

    @application.on_event("shutdown")
    async def on_shutdown() -> None:
        try:
            await close_redis()
        except Exception:
            logger.exception("Redis close failed during shutdown")
        finally:
            try:
                await close_db()
            except Exception:
                logger.exception("Database close failed during shutdown")
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
    from app.modules.setup.router import router as setup_router

    application.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    application.include_router(profiles_router, prefix="/api/profiles", tags=["profiles"])
    application.include_router(files_router, prefix="/api/files", tags=["files"])
    application.include_router(comms_router, prefix="/api", tags=["communication"])
    application.include_router(discovery_router, prefix="/api/search", tags=["discovery"])
    application.include_router(notif_router, prefix="/api/notifications", tags=["notifications"])
    application.include_router(ai_router, prefix="/api/ai", tags=["ai"])
    application.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    application.include_router(setup_router, tags=["setup"])

    generated_alias_path = Path(__file__).parent / "generated" / "role_alias_router.py"
    if generated_alias_path.exists():
        from app.generated.role_alias_router import router as generated_role_router

        application.include_router(generated_role_router)
        _hide_generic_profile_routes_from_docs(application)
        logger.info("Loaded generated role aliases from %s", generated_alias_path)


def _hide_generic_profile_routes_from_docs(application: FastAPI) -> None:
    for route in application.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/profiles/{type_slug}"):
            route.include_in_schema = False
    application.openapi_schema = None


app = create_app()
