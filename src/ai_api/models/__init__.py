"""SQLAlchemy ORM models — importing this module registers all tables on Base.metadata."""
from __future__ import annotations

from ai_api.models.allocation import Allocation, AllocationStatus
from ai_api.models.call_record import CallOutcome, CallRecord
from ai_api.models.credential import Credential

__all__ = ["Allocation", "AllocationStatus", "CallOutcome", "CallRecord", "Credential"]
