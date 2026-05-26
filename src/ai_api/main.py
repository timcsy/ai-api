"""FastAPI application entrypoint."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_api.api import (
    admin_access,
    admin_audit,
    admin_catalog,
    admin_diagnose,
    admin_members,
    admin_model_access,
    admin_providers,
    admin_self_service,
    admin_tag_rules,
    admin_tags,
    allocations,
    auth,
    catalog,
    health,
    me,
    quota_pool,
    records,
    usage,
)
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

    # Phase 3a: CORS for upcoming 3b SPA. Allowlist driven by Settings.cors_origins.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router, tags=[])
    app.include_router(auth.router, tags=["auth"])
    app.include_router(me.router, tags=["me"])
    app.include_router(allocations.router, prefix="/admin", tags=["admin"])
    app.include_router(records.router, prefix="/admin", tags=["admin"])
    app.include_router(admin_members.router, prefix="/admin", tags=["admin-members"])
    app.include_router(admin_providers.router, prefix="/admin", tags=["admin-providers"])
    app.include_router(admin_tags.router, prefix="/admin", tags=["admin-tags"])
    app.include_router(admin_tag_rules.router, prefix="/admin", tags=["admin-tag-rules"])
    app.include_router(admin_self_service.router, prefix="/admin", tags=["admin-self-service"])
    # model_access (PATCH .../access) MUST register BEFORE admin_catalog (PATCH
    # .../{slug}) so the more-specific /access route wins via order.
    app.include_router(admin_model_access.router, prefix="/admin", tags=["admin-model-access"])
    app.include_router(admin_catalog.router, prefix="/admin", tags=["admin-catalog"])
    app.include_router(admin_audit.router, prefix="/admin", tags=["admin-audit"])
    app.include_router(admin_diagnose.router, prefix="/admin", tags=["admin-diagnose"])
    app.include_router(admin_access.router, prefix="/admin", tags=["admin-access"])
    app.include_router(usage.router, prefix="/admin", tags=["admin-usage"])
    app.include_router(quota_pool.router, prefix="/admin", tags=["admin-quota-pool"])
    app.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
    app.include_router(proxy_router, prefix="/v1", tags=["proxy"])

    # touch settings to fail-fast on misconfiguration
    _ = settings.admin_bootstrap_token
    # Phase 5 FR-011 / SC-006: validate Fernet key at app construction so a
    # missing/malformed PROVIDER_KEY_ENC_KEY causes pod to refuse to start
    # (CrashLoopBackOff) rather than failing at first credential operation.
    from ai_api.services.crypto import get_fernet

    get_fernet()
    # Phase 2.5 FR-003: empty provider allowlist is a config error.
    if not settings.allowed_providers:
        raise RuntimeError(
            "ALLOWED_PROVIDERS is empty — refusing to start. "
            "Set at least one provider (e.g. ['azure'])."
        )
    return app


app = create_app()
