"""Proxy authentication: extract Bearer token → resolve allocation → check status."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from ai_api.models import Allocation, AllocationStatus
from ai_api.services.allocations import AllocationService


@dataclass(frozen=True)
class AllocationLookup:
    allocation: Allocation


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": message}},
    )


def _forbidden_revoked() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "allocation_revoked",
                "message": "allocation has been revoked",
            }
        },
    )


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("empty bearer token")
    return token


async def resolve_allocation(
    token: str, service: AllocationService
) -> Allocation:
    allocation = await service.lookup_by_token(token)
    if allocation is None:
        raise _unauthorized("invalid credential")
    if allocation.status == AllocationStatus.revoked:
        raise _forbidden_revoked()
    return allocation


async def require_allocation_header(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Return the plaintext token; lookup happens later (needs DB session)."""
    return parse_bearer_token(authorization)
