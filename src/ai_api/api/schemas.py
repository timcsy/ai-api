"""Pydantic schemas for admin API request/response."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from ai_api.models import AllocationStatus

ResourceModelStr = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9_\-./]+$", min_length=1, max_length=128),
]
MemberIdStr = Annotated[str, StringConstraints(min_length=26, max_length=26)]
SubjectStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class CreateAllocationRequest(BaseModel):
    member_id: MemberIdStr | None = None
    # NOTE: `subject` is a backward-compat alias from Phase 1 tests. When given,
    # the endpoint auto-creates an external Member. Remove in Phase 7 polish
    # after all tests are migrated.
    subject: SubjectStr | None = None
    resource_model: ResourceModelStr
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_either(self) -> CreateAllocationRequest:
        if self.member_id is None and not self.subject:
            raise ValueError("either member_id or subject must be provided")
        return self


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    member_id: str
    subject_snapshot: str
    resource_model: str
    display_name: str | None = None  # catalog display name of resource_model, if any
    status: AllocationStatus
    created_at: datetime
    revoked_at: datetime | None
    created_by: str
    note: str | None
    token_prefix: str
    # Phase 3a
    quota_tokens_per_month: int | None = None
    is_service_allocation: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subject(self) -> str:
        """Phase 1 compat: subject == subject_snapshot."""
        return self.subject_snapshot


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
