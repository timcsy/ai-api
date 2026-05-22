"""Invitation token service: single-use 48h tokens for first-time password set."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import InvitationToken, Member

INVITATION_PREFIX = "invite_"
DEFAULT_LIFETIME = timedelta(hours=48)


@dataclass(frozen=True)
class IssuedInvitation:
    plaintext: str
    fingerprint: str
    prefix: str
    member_id: str
    expires_at: datetime


def _fingerprint(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


async def issue(
    db: AsyncSession, member_id: str, *, created_by: str
) -> IssuedInvitation:
    plaintext = INVITATION_PREFIX + secrets.token_urlsafe(32)
    fp = _fingerprint(plaintext)
    now = datetime.now(UTC)
    token = InvitationToken(
        token_fingerprint=fp,
        token_prefix=plaintext[:12],
        member_id=member_id,
        created_at=now,
        expires_at=now + DEFAULT_LIFETIME,
        used_at=None,
        created_by=created_by,
    )
    db.add(token)
    await db.flush()
    return IssuedInvitation(
        plaintext=plaintext,
        fingerprint=fp,
        prefix=plaintext[:12],
        member_id=member_id,
        expires_at=token.expires_at,
    )


async def lookup(db: AsyncSession, plaintext: str) -> InvitationToken | None:
    fp = _fingerprint(plaintext)
    stmt = select(InvitationToken).where(InvitationToken.token_fingerprint == fp)
    return (await db.execute(stmt)).scalar_one_or_none()


async def consume(db: AsyncSession, plaintext: str) -> Member | None:
    """Mark token as used; return associated Member if valid (active, unused, unexpired)."""
    token = await lookup(db, plaintext)
    if token is None or token.used_at is not None:
        return None
    exp = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=UTC)
    if exp <= datetime.now(UTC):
        return None
    member_stmt = select(Member).where(Member.id == token.member_id)
    member = (await db.execute(member_stmt)).scalar_one_or_none()
    if member is None:
        return None
    token.used_at = datetime.now(UTC)
    await db.flush()
    return member
