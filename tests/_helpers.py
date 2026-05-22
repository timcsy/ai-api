"""Shared test helpers across contract/integration suites."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import Member, MemberProvider, MemberStatus


async def create_external_member(
    session: AsyncSession,
    email: str,
    *,
    display_name: str | None = None,
) -> str:
    """Insert an `external` Member directly (bypass admin API) and return id."""
    member = Member(
        id=str(ULID()),
        email=email.lower(),
        provider=MemberProvider.external,
        external_id=email,
        display_name=display_name or email,
        status=MemberStatus.active,
        password_hash=None,
        created_at=datetime.now(UTC),
        disabled_at=None,
        created_by="test-helper",
    )
    session.add(member)
    await session.flush()
    await session.commit()
    return member.id
