"""FastAPI application entrypoint."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_api.api import admin_access, admin_members, allocations, auth, health, me, records
from ai_api.config import get_settings
from ai_api.db import dispose_engine
from ai_api.observability.logging import setup_logging
from ai_api.observability.request_id import RequestIdMiddleware
from ai_api.proxy.router import router as proxy_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI API Manager — Gateway Core",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router, tags=[])
    app.include_router(auth.router, tags=["auth"])
    app.include_router(me.router, tags=["me"])
    app.include_router(allocations.router, prefix="/admin", tags=["admin"])
    app.include_router(records.router, prefix="/admin", tags=["admin"])
    app.include_router(admin_members.router, prefix="/admin", tags=["admin-members"])
    app.include_router(admin_access.router, prefix="/admin", tags=["admin-access"])
    app.include_router(proxy_router, prefix="/v1", tags=["proxy"])

    # touch settings to fail-fast on misconfiguration
    _ = settings.admin_bootstrap_token
    return app


app = create_app()
