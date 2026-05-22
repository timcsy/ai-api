"""Access control service: whitelist / rule / source restriction CRUD."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import AutoRegisterRule, EmailWhitelist, RuleType, SourceRestriction


class WhitelistService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list(self) -> list[EmailWhitelist]:
        return list(
            (await self._db.execute(select(EmailWhitelist).order_by(EmailWhitelist.email))).scalars()
        )

    async def add(self, email: str, *, added_by: str, note: str | None = None) -> EmailWhitelist:
        email_n = email.strip().lower()
        entry = EmailWhitelist(
            email=email_n,
            added_at=datetime.now(UTC),
            added_by=added_by,
            note=note,
        )
        existing = await self._db.get(EmailWhitelist, email_n)
        if existing is not None:
            existing.note = note
            existing.added_by = added_by
            entry = existing
        else:
            self._db.add(entry)
        await self._db.flush()
        return entry

    async def remove(self, email: str) -> bool:
        email_n = email.strip().lower()
        existing = await self._db.get(EmailWhitelist, email_n)
        if existing is None:
            return False
        await self._db.delete(existing)
        await self._db.flush()
        return True


class RuleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list(self) -> list[AutoRegisterRule]:
        return list(
            (await self._db.execute(select(AutoRegisterRule).order_by(AutoRegisterRule.created_at))).scalars()
        )

    async def create(
        self,
        *,
        rule_type: RuleType,
        pattern: str,
        enabled: bool = True,
        created_by: str,
        note: str | None = None,
    ) -> AutoRegisterRule:
        rule = AutoRegisterRule(
            id=str(ULID()),
            rule_type=rule_type,
            pattern=pattern.strip().lower(),
            enabled=enabled,
            created_at=datetime.now(UTC),
            created_by=created_by,
            note=note,
        )
        self._db.add(rule)
        await self._db.flush()
        return rule

    async def delete(self, rule_id: str) -> bool:
        rule = await self._db.get(AutoRegisterRule, rule_id)
        if rule is None:
            return False
        await self._db.delete(rule)
        await self._db.flush()
        return True


class SourceRestrictionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list(self) -> list[SourceRestriction]:
        return list(
            (await self._db.execute(select(SourceRestriction).order_by(SourceRestriction.created_at))).scalars()
        )

    async def create(
        self, *, cidr: str, enabled: bool = True, created_by: str, note: str | None = None
    ) -> SourceRestriction:
        item = SourceRestriction(
            id=str(ULID()),
            cidr=cidr,
            enabled=enabled,
            created_at=datetime.now(UTC),
            created_by=created_by,
            note=note,
        )
        self._db.add(item)
        await self._db.flush()
        return item

    async def delete(self, item_id: str) -> bool:
        item = await self._db.get(SourceRestriction, item_id)
        if item is None:
            return False
        await self._db.delete(item)
        await self._db.flush()
        return True
