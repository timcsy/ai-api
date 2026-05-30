"""Access policy: source restriction + whitelist + auto-register rule evaluation."""
from __future__ import annotations

import ipaddress

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import (
    AutoRegisterRule,
    EmailWhitelist,
    Member,
    MemberStatus,
    RuleType,
    SourceRestriction,
)


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


async def is_source_allowed(session: AsyncSession, source_ip: str | None) -> bool:
    """Return True if source_ip passes restrictions.

    Behaviour:
    - No restrictions enabled → allow all.
    - Any enabled restriction → source must match at least one.
    - source_ip None → treated as not matching (deny if any restriction).
    """
    restrictions = (
        await session.execute(
            select(SourceRestriction).where(SourceRestriction.enabled.is_(True))
        )
    ).scalars().all()
    if not restrictions:
        return True
    if not source_ip:
        return False
    try:
        ip = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    for r in restrictions:
        try:
            if ip in ipaddress.ip_network(r.cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


async def is_email_allowed(session: AsyncSession, email: str) -> bool:
    """Return True if this email is allowed to log in.

    Two regimes:

    1. **Bootstrap mode** (no active admin yet): allowed if the email is in
       `email_whitelist` OR matches an enabled `auto_register_rule`. The
       whitelist exists *only* to let the very first admin land — once an
       admin is set up they take over access management and the whitelist
       becomes inert (see regime 2).
    2. **Admin-managed mode** (≥1 active admin exists): the whitelist is
       **bypassed entirely**. Allowed if the email matches:
         a. an enabled `auto_register_rule` (admin's bulk authorization), OR
         b. an active `members` row (admin pre-created the member).
       This makes admin the single source of access truth and matches the
       intuition that "admin already manages who's a member, so a separate
       whitelist is redundant."
    """
    email_n = normalize_email(email)

    # Rule match always wins (the admin-friendly bulk mechanism, also valid
    # during bootstrap).
    rules = (
        await session.execute(
            select(AutoRegisterRule).where(AutoRegisterRule.enabled.is_(True))
        )
    ).scalars().all()
    domain = email_n.rsplit("@", 1)[-1] if "@" in email_n else ""
    if any(
        r.rule_type == RuleType.email_domain and r.pattern.lower() == domain for r in rules
    ):
        return True

    # Has an admin been bootstrapped yet?
    admin_count = await session.scalar(
        select(func.count())
        .select_from(Member)
        .where(Member.is_admin.is_(True), Member.status == MemberStatus.active)
    )
    if (admin_count or 0) > 0:
        # Admin-managed mode: the email must belong to an active member.
        member = (
            await session.execute(
                select(Member).where(
                    Member.email == email_n, Member.status == MemberStatus.active
                )
            )
        ).scalar_one_or_none()
        return member is not None

    # Bootstrap mode: fall back to the whitelist.
    whitelisted = (
        await session.execute(
            select(EmailWhitelist).where(EmailWhitelist.email == email_n)
        )
    ).scalar_one_or_none()
    return whitelisted is not None
