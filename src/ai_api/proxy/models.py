"""Phase 36 (spec 050): OpenAI-compatible model discovery — GET /v1/models[/{id}].

Any OpenAI-compatible client (Copilot, Continue, OpenWebUI, the official SDK's
`models.list()`, curl) lists models before calling. We expose the calling KEY's
scope — the active allocations it's been granted — in OpenAI's list/model shape.
The id is the canonical provider-prefixed slug (the same value preflight routes
on), so a listed id round-trips as `model` verbatim.

Read-only: no upstream call, no new tables. See contracts/v1-models.md.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.models import Allocation, Credential, ModelCatalog
from ai_api.proxy.allowlist import parse_provider
from ai_api.proxy.auth import parse_bearer_token
from ai_api.services.allocations import AllocationService

router = APIRouter()


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _model_obj(alloc: Allocation, created_ts: int) -> dict[str, Any]:
    provider, _ = parse_provider(alloc.resource_model)
    return {
        "id": alloc.resource_model,
        "object": "model",
        "created": created_ts,
        "owned_by": provider,
    }


async def _created_map(session: AsyncSession, slugs: list[str]) -> dict[str, int]:
    """slug → catalog created_at epoch (for OpenAI's `created`); absent slugs omitted."""
    if not slugs:
        return {}
    rows = (
        await session.execute(
            select(ModelCatalog.slug, ModelCatalog.created_at).where(ModelCatalog.slug.in_(slugs))
        )
    ).all()
    return {slug: int(created.timestamp()) for slug, created in rows}


async def _resolve_credential(
    authorization: str | None, session: AsyncSession
) -> tuple[Credential, AllocationService]:
    """Bearer token → application key, or raise a 401 JSONResponse-bearing error.

    Returns (credential, service). Raises HTTPException only for the bearer parse;
    callers translate it to the platform `{"error":...}` shape.
    """
    token = parse_bearer_token(authorization)  # 401 on missing/empty
    service = AllocationService(session)
    credential = await service.lookup_credential_by_token(token)
    if credential is None:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "invalid credential"}})
    return credential, service


@router.get("/models")
async def list_models(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    try:
        credential, service = await _resolve_credential(authorization, session)
    except HTTPException as exc:
        d: Any = exc.detail["error"]  # type: ignore[index]
        return _error(d["code"], d["message"], exc.status_code)

    allocs = await service.list_active_scope_allocations(credential)
    created = await _created_map(session, [a.resource_model for a in allocs])
    fallback = {a.resource_model: int(a.created_at.timestamp()) for a in allocs}
    data = [_model_obj(a, created.get(a.resource_model, fallback[a.resource_model])) for a in allocs]
    return {"object": "list", "data": data}


@router.get("/models/{model_id:path}")
async def retrieve_model(
    model_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    try:
        credential, service = await _resolve_credential(authorization, session)
    except HTTPException as exc:
        d: Any = exc.detail["error"]  # type: ignore[index]
        return _error(d["code"], d["message"], exc.status_code)

    # Same scope/identifier logic as a real call (exact + unique bare-slug alias).
    alloc = await service.resolve_scope_allocation(credential, model_id)
    if alloc is None or alloc.status.value != "active":
        return _error("not_found", f"model {model_id} not found", 404)
    created = await _created_map(session, [alloc.resource_model])
    ts = created.get(alloc.resource_model, int(alloc.created_at.timestamp()))
    return _model_obj(alloc, ts)
