"""Session management: token generation, fingerprint, validation, revocation."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai_api.models import Member, MemberStatus, Session, SessionStatus

SESSION_COOKIE_NAME = "aiapi_session"
SESSION_TOKEN_PREFIX = "sess_"
DEFAULT_LIFETIME = timedelta(hours=24)
DEFAULT_IDLE = timedelta(hours=2)


@dataclass(frozen=True)
class IssuedSession:
    plaintext: str
    fingerprint: str
    expires_at: datetime
    member_id: str


def _fingerprint(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def create_session(
    db: AsyncSession,
    member_id: str,
    *,
    source_ip: str | None = None,
    user_agent: str | None = None,
    lifetime: timedelta = DEFAULT_LIFETIME,
    idle_timeout: timedelta = DEFAULT_IDLE,
) -> IssuedSession:
    plaintext = SESSION_TOKEN_PREFIX + secrets.token_urlsafe(32)
    fp = _fingerprint(plaintext)
    now = datetime.now(UTC)
    record = Session(
        id=fp,
        member_id=member_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + lifetime,
        idle_timeout_at=now + idle_timeout,
        source_ip=source_ip,
        user_agent=user_agent[:512] if user_agent else None,
        status=SessionStatus.active,
    )
    db.add(record)
    await db.flush()
    return IssuedSession(
        plaintext=plaintext,
        fingerprint=fp,
        expires_at=record.expires_at,
        member_id=member_id,
    )


async def lookup_session(db: AsyncSession, plaintext: str) -> Session | None:
    if not plaintext:
        return None
    fp = _fingerprint(plaintext)
    stmt = (
        select(Session)
        .options(selectinload(Session.member))
        .where(Session.id == fp)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def validate_session(db: AsyncSession, plaintext: str) -> Member | None:
    """Return Member if session valid & active & member active; else None.

    Updates last_seen_at on success. Spec FR-006/FR-007 implication: check
    Member.status every call so disabled members lose access within seconds.
    """
    record = await lookup_session(db, plaintext)
    if record is None:
        return None
    now = datetime.now(UTC)
    if record.status != SessionStatus.active:
        return None
    if _ensure_utc(record.expires_at) <= now or _ensure_utc(record.idle_timeout_at) <= now:
        return None
    if record.member.status != MemberStatus.active:
        # Lazily revoke
        record.status = SessionStatus.revoked
        record.revoked_at = now
        record.revoked_reason = "member_disabled"
        await db.flush()
        return None
    record.last_seen_at = now
    record.idle_timeout_at = now + DEFAULT_IDLE
    await db.flush()
    return record.member


async def revoke_session(db: AsyncSession, plaintext: str, reason: str = "logout") -> None:
    fp = _fingerprint(plaintext)
    await db.execute(
        update(Session)
        .where(Session.id == fp, Session.status == SessionStatus.active)
        .values(status=SessionStatus.revoked, revoked_at=datetime.now(UTC), revoked_reason=reason)
    )


async def revoke_all_for_member(db: AsyncSession, member_id: str, reason: str = "manual") -> int:
    result = await db.execute(
        update(Session)
        .where(Session.member_id == member_id, Session.status == SessionStatus.active)
        .values(status=SessionStatus.revoked, revoked_at=datetime.now(UTC), revoked_reason=reason)
    )
    return int(getattr(result, "rowcount", 0) or 0)
