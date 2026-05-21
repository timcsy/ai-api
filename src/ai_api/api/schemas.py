"""Pydantic schemas for admin API request/response."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ai_api.models import AllocationStatus

ResourceModelStr = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_\-.]+$", min_length=1, max_length=128),
]
SubjectStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class CreateAllocationRequest(BaseModel):
    subject: SubjectStr
    resource_model: ResourceModelStr
    note: str | None = Field(default=None, max_length=500)


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject: str
    resource_model: str
    status: AllocationStatus
    created_at: datetime
    revoked_at: datetime | None
    created_by: str
    note: str | None
    token_prefix: str


class AllocationCreatedOut(AllocationOut):
    token: str


class CallRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    allocation_id: str | None
    subject: str | None
    model: str | None
    started_at: datetime
    finished_at: datetime
    status_code: int
    outcome: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    error_message: str | None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
