"""Access policy: source restriction + whitelist + auto-register rule evaluation."""
from __future__ import annotations

import ipaddress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import AutoRegisterRule, EmailWhitelist, RuleType, SourceRestriction


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
    """Return True if email is whitelisted OR matches an enabled auto-register rule."""
    email_n = normalize_email(email)
    whitelisted = (
        await session.execute(select(EmailWhitelist).where(EmailWhitelist.email == email_n))
    ).scalar_one_or_none()
    if whitelisted is not None:
        return True

    rules = (
        await session.execute(
            select(AutoRegisterRule).where(AutoRegisterRule.enabled.is_(True))
        )
    ).scalars().all()
    domain = email_n.rsplit("@", 1)[-1] if "@" in email_n else ""
    return any(
        r.rule_type == RuleType.email_domain and r.pattern.lower() == domain for r in rules
    )
