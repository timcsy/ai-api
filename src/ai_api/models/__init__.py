"""SQLAlchemy ORM models — importing this package registers all tables on Base.metadata."""
from __future__ import annotations

from ai_api.models.access_control import (
    AutoRegisterRule,
    EmailWhitelist,
    RuleType,
    SourceRestriction,
)
from ai_api.models.allocation import Allocation, AllocationStatus
from ai_api.models.auth_audit import ActorType, AuditEventType, AuthAuditLog
from ai_api.models.call_record import CallOutcome, CallRecord
from ai_api.models.credential import Credential
from ai_api.models.invitation import InvitationToken
from ai_api.models.member import Member, MemberProvider, MemberStatus
from ai_api.models.model_catalog import ModelCatalog
from ai_api.models.oidc_state import OidcState
from ai_api.models.password_attempt import AttemptOutcome, PasswordAttempt
from ai_api.models.price_list import PriceList
from ai_api.models.rebalance_log import RebalanceLog
from ai_api.models.session import Session, SessionStatus

__all__ = [
    "ActorType",
    "Allocation",
    "AllocationStatus",
    "AttemptOutcome",
    "AuditEventType",
    "AuthAuditLog",
    "AutoRegisterRule",
    "CallOutcome",
    "CallRecord",
    "Credential",
    "EmailWhitelist",
    "InvitationToken",
    "Member",
    "MemberProvider",
    "MemberStatus",
    "ModelCatalog",
    "OidcState",
    "PasswordAttempt",
    "PriceList",
    "RebalanceLog",
    "RuleType",
    "Session",
    "SessionStatus",
    "SourceRestriction",
]
