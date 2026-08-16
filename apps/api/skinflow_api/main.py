from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from skinflow_api.bootstrap.container import build_container
from skinflow_api.routes.errors import install_error_handlers
from skinflow_api.routes.health import create_health_router
from skinflow_api.routes.ledger import create_ledger_router
from skinflow_api.routes.listing import create_listing_router
from skinflow_api.routes.local_auth import (
    LocalSecurityMiddleware,
    create_auth_router,
)
from skinflow_api.routes.preferences import create_preferences_router
from skinflow_api.routes.scan import create_scan_router
from skinflow_api.routes.steam_session import create_steam_session_router
from skinflow_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    effective_settings = settings or get_settings()
    container = build_container(effective_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        container.listing_reconciliation.start()
        yield
        await container.scan_runner.shutdown()
        await container.listing_reconciliation.shutdown()
        container.close()

    app = FastAPI(
        title=effective_settings.app_name,
        version=effective_settings.api_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(LocalSecurityMiddleware, settings=effective_settings)
    app.include_router(create_auth_router(effective_settings))
    app.include_router(create_health_router(container.health_service))
    app.include_router(create_scan_router(container.scan_service, container.scan_runner))
    app.include_router(
        create_ledger_router(
            container.ledger_service,
            container.inventory_service,
            container.listing_reconciliation,
        )
    )
    app.include_router(
        create_listing_router(container.listing_service, container.listing_reconciliation)
    )
    app.include_router(create_steam_session_router(container.steam_login))
    app.include_router(create_preferences_router(container.preferences_store))
    install_error_handlers(app)
    _mount_web(app, effective_settings)
    return app


def _mount_web(app: FastAPI, settings: Settings) -> None:
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if not settings.serve_web or not (web_dist / "index.html").exists():
        return
    assets = web_dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        candidate = (web_dist / path).resolve()
        if candidate.is_relative_to(web_dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(web_dist / "index.html")


app = create_app()
