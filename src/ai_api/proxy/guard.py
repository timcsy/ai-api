"""Model binding guard: requested model must equal allocation.resource_model."""
from __future__ import annotations

from fastapi import HTTPException, status

from ai_api.models import Allocation


def enforce_model_binding(allocation: Allocation, requested_model: str) -> None:
    if requested_model != allocation.resource_model:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "model_mismatch",
                    "message": (
                        f"this allocation is bound to '{allocation.resource_model}' "
                        f"but request used '{requested_model}'"
                    ),
                }
            },
        )
