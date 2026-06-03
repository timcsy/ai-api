"""SQLAlchemy ORM models — importing this package registers all tables on Base.metadata."""
from __future__ import annotations

from ai_api.models.access_control import (
    AutoRegisterRule,
    EmailWhitelist,
    RuleType,
    SourceRestriction,
)
from ai_api.models.allocation import Allocation, AllocationOrigin, AllocationStatus
from ai_api.models.auth_audit import ActorType, AuditEventType, AuthAuditLog
from ai_api.models.call_record import CallOutcome, CallRecord
from ai_api.models.credential import Credential
from ai_api.models.invitation import InvitationToken
from ai_api.models.member import Member, MemberProvider, MemberStatus
from ai_api.models.member_tag import MemberTag, TagSource
from ai_api.models.model_catalog import DefaultAccess, ModelCatalog
from ai_api.models.notification import (
    NotificationConfig,
    NotificationConfigStatus,
    NotificationDedupBucket,
    NotificationOutcome,
    NotificationRecord,
)
from ai_api.models.oidc_state import OidcState
from ai_api.models.password_attempt import AttemptOutcome, PasswordAttempt
from ai_api.models.price_list import PriceList
from ai_api.models.provider_credential import ProviderCredential, ProviderCredentialStatus
from ai_api.models.rebalance_log import RebalanceLog
from ai_api.models.self_service_lock import SelfServiceReclaimLock
from ai_api.models.session import Session, SessionStatus
from ai_api.models.stored_response import StoredResponse
from ai_api.models.tag_rule import MatcherType, TagRule

__all__ = [
    "ActorType",
    "Allocation",
    "AllocationOrigin",
    "AllocationStatus",
    "AttemptOutcome",
    "AuditEventType",
    "AuthAuditLog",
    "AutoRegisterRule",
    "CallOutcome",
    "CallRecord",
    "Credential",
    "DefaultAccess",
    "EmailWhitelist",
    "InvitationToken",
    "MatcherType",
    "Member",
    "MemberProvider",
    "MemberStatus",
    "MemberTag",
    "ModelCatalog",
    "NotificationConfig",
    "NotificationConfigStatus",
    "NotificationDedupBucket",
    "NotificationOutcome",
    "NotificationRecord",
    "OidcState",
    "PasswordAttempt",
    "PriceList",
    "ProviderCredential",
    "ProviderCredentialStatus",
    "RebalanceLog",
    "RuleType",
    "SelfServiceReclaimLock",
    "Session",
    "SessionStatus",
    "SourceRestriction",
    "StoredResponse",
    "TagRule",
    "TagSource",
]
