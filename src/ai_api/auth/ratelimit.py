"""Rate limit service: per-email login attempt counting + lockout."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import AttemptOutcome, PasswordAttempt

WINDOW = timedelta(seconds=60)
THRESHOLD = 5
LOCK_DURATION = timedelta(minutes=15)


async def record_attempt(
    db: AsyncSession,
    email: str,
    outcome: AttemptOutcome,
    *,
    source_ip: str | None = None,
) -> None:
    db.add(
        PasswordAttempt(
            id=str(ULID()),
            email=email.lower(),
            attempted_at=datetime.now(UTC),
            source_ip=source_ip,
            outcome=outcome,
        )
    )
    await db.flush()


async def is_ip_locked(db: AsyncSession, source_ip: str | None) -> bool:
    """Return True if the source IP is currently locked (per-IP rate limit, FR-013)."""
    if not source_ip:
        return False
    from ai_api.config import get_settings

    settings = get_settings()
    threshold = settings.perip_lockout_threshold
    now = datetime.now(UTC)

    lock_since = now - LOCK_DURATION
    locked_stmt = (
        select(PasswordAttempt)
        .where(
            PasswordAttempt.source_ip == source_ip,
            PasswordAttempt.outcome == AttemptOutcome.locked,
            PasswordAttempt.attempted_at >= lock_since,
        )
        .limit(1)
    )
    if (await db.execute(locked_stmt)).scalar_one_or_none() is not None:
        return True

    window_since = now - WINDOW
    fail_stmt = select(PasswordAttempt).where(
        PasswordAttempt.source_ip == source_ip,
        PasswordAttempt.attempted_at >= window_since,
        PasswordAttempt.outcome.in_(
            (AttemptOutcome.bad_password, AttemptOutcome.unknown_email)
        ),
    )
    fails = (await db.execute(fail_stmt)).scalars().all()
    if len(fails) >= threshold:
        db.add(
            PasswordAttempt(
                id=str(ULID()),
                email="(ip-lock)",  # synthetic; per-IP locks aren't per-email
                attempted_at=now,
                source_ip=source_ip,
                outcome=AttemptOutcome.locked,
            )
        )
        await db.flush()
        return True
    return False


async def is_locked(db: AsyncSession, email: str) -> bool:
    """Return True if the email is currently locked due to recent failures."""
    email_n = email.lower()
    now = datetime.now(UTC)

    # If a recent `locked` row exists within LOCK_DURATION, still locked.
    lock_since = now - LOCK_DURATION
    locked_stmt = (
        select(PasswordAttempt)
        .where(
            PasswordAttempt.email == email_n,
            PasswordAttempt.outcome == AttemptOutcome.locked,
            PasswordAttempt.attempted_at >= lock_since,
        )
        .limit(1)
    )
    if (await db.execute(locked_stmt)).scalar_one_or_none() is not None:
        return True

    # Otherwise count failures in WINDOW
    window_since = now - WINDOW
    fail_stmt = (
        select(PasswordAttempt)
        .where(
            PasswordAttempt.email == email_n,
            PasswordAttempt.attempted_at >= window_since,
            PasswordAttempt.outcome.in_(
                (AttemptOutcome.bad_password, AttemptOutcome.unknown_email)
            ),
        )
    )
    fails = (await db.execute(fail_stmt)).scalars().all()
    if len(fails) >= THRESHOLD:
        # Write a lock marker so future checks short-circuit.
        await record_attempt(db, email, AttemptOutcome.locked)
        return True
    return False
