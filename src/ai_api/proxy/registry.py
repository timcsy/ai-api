"""Phase 31 (042): the endpoint registry — one EndpointSpec per non-streaming
member inference endpoint. Adding a same-shape endpoint = adding one row here.

build_router() turns the registry into a FastAPI APIRouter; the shared engine
(engine.py) executes each spec. Streaming endpoints (/chat/completions,
/responses) are NOT here — they keep their own handlers.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.api.deps import get_db_session
from ai_api.proxy import upstream
from ai_api.proxy.endpoint_spec import (
    EndpointSpec,
    InputShape,
    OutputShape,
    TokenMeter,
    UnitMeter,
    creds,
)
from ai_api.proxy.engine import run_endpoint


def _ocr_pages(payload: dict[str, Any]) -> int | None:
    usage = payload.get("usage_info")
    if isinstance(usage, dict) and isinstance(usage.get("pages_processed"), int):
        return int(usage["pages_processed"])
    pages = payload.get("pages")
    return len(pages) if isinstance(pages, list) else None


def _image_count(payload: dict[str, Any]) -> int | None:
    data = payload.get("data")
    return len(data) if isinstance(data, list) else None


# --- the registry: each endpoint is one row of data --------------------------
SPECS: list[EndpointSpec] = [
    EndpointSpec(
        path="/embeddings", required=("input",), meter=TokenMeter(),
        call=lambda f, r, m: upstream.aembedding(model=m, input=f["input"], **creds(r)),
    ),
    EndpointSpec(
        path="/ocr", required=("document",), meter=UnitMeter("page", lambda f, p: _ocr_pages(p)),
        call=lambda f, r, m: upstream.aocr(model=m, document=f["document"], **creds(r)),
    ),
    EndpointSpec(
        path="/images/generations", required=("prompt",), meter=TokenMeter(),
        call=lambda f, r, m: upstream.aimage_generation(model=m, prompt=f["prompt"], **creds(r)),
    ),
    EndpointSpec(
        path="/rerank", required=("query", "documents"), meter=UnitMeter("query", lambda f, p: 1),
        call=lambda f, r, m: upstream.arerank(
            model=m, query=f["query"], documents=f["documents"], **creds(r)
        ),
    ),
    EndpointSpec(
        path="/audio/speech", required=("input",), output_shape=OutputShape.binary,
        meter=UnitMeter("character", lambda f, p: len(f["input"])),
        call=lambda f, r, m: upstream.aspeech(
            model=m, input=f["input"], voice=f.get("voice") or "alloy", **creds(r)
        ),
    ),
    EndpointSpec(
        path="/audio/transcriptions", input_shape=InputShape.multipart, required=("file",),
        meter=TokenMeter(),
        call=lambda f, r, m: upstream.atranscription(model=m, file=f["file"], **creds(r)),
    ),
    # --- Phase 31 new endpoints ---
    EndpointSpec(
        path="/moderations", required=("input",), meter=TokenMeter(),
        call=lambda f, r, m: upstream.amoderation(model=m, input=f["input"], **creds(r)),
    ),
    EndpointSpec(
        path="/search", required=("query",), meter=UnitMeter("query", lambda f, p: 1),
        call=lambda f, r, m: upstream.asearch(search_provider=m, query=f["query"], **creds(r)),
    ),
    EndpointSpec(
        path="/images/edits", input_shape=InputShape.multipart, required=("image",),
        meter=UnitMeter("image", lambda f, p: _image_count(p)),
        call=lambda f, r, m: upstream.aimage_edit(
            model=m, image=f["image"], prompt=f.get("prompt"), **creds(r)
        ),
    ),
]


def build_router(specs: list[EndpointSpec] = SPECS) -> APIRouter:
    router = APIRouter()
    for spec in specs:
        def _make(spec: EndpointSpec) -> Any:
            async def handler(
                request: Request,
                authorization: str | None = Header(default=None, alias="Authorization"),
                session: AsyncSession = Depends(get_db_session),
            ) -> Any:
                return await run_endpoint(spec, request, authorization, session)

            handler.__name__ = "proxy_" + spec.path.strip("/").replace("/", "_")
            return handler

        router.add_api_route(spec.path, _make(spec), methods=["POST"], tags=["proxy"])
    return router
