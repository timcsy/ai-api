"""Phase 5: MemberTag service — per-member add/remove + bulk-apply + distinct list."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.auth.audit import record as audit_record
from ai_api.models import ActorType, AuditEventType, Member, MemberTag

_TAG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def validate_tag(tag: str) -> str:
    if not _TAG_RE.match(tag):
        raise ValueError(
            f"invalid tag {tag!r}: must match ^[a-z][a-z0-9_-]{{0,63}}$"
        )
    return tag


@dataclass(frozen=True)
class TagSummary:
    tag: str
    member_count: int


class MemberTagService:
    BOOTSTRAP_ADMIN = "bootstrap-admin"

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_for_member(self, member_id: str) -> list[str]:
        stmt = (
            select(MemberTag.tag)
            .where(MemberTag.member_id == member_id)
            .order_by(MemberTag.tag)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def add(
        self, member_id: str, tags: list[str], *, added_by: str | None = None
    ) -> list[str]:
        """Add tags to member; idempotent. Returns final tag list."""
        member = await self._s.get(Member, member_id)
        if member is None:
            raise LookupError(f"member {member_id} not found")
        existing = set(await self.list_for_member(member_id))
        now = datetime.now(UTC)
        by = added_by or self.BOOTSTRAP_ADMIN
        added_any = False
        for tag in tags:
            validate_tag(tag)
            if tag in existing:
                continue
            self._s.add(MemberTag(member_id=member_id, tag=tag, added_by=by, added_at=now))
            existing.add(tag)
            added_any = True
        if added_any:
            await self._s.flush()
            await audit_record(
                self._s,
                event_type=AuditEventType.member_tag_added,
                actor_type=ActorType.admin,
                actor_id=added_by,
                target_type="member",
                target_id=member_id,
                details={"tags": sorted(set(tags))},
            )
        return sorted(existing)

    async def remove(self, member_id: str, tags: list[str], *, removed_by: str | None = None) -> None:
        member = await self._s.get(Member, member_id)
        if member is None:
            raise LookupError(f"member {member_id} not found")
        stmt = delete(MemberTag).where(
            MemberTag.member_id == member_id, MemberTag.tag.in_(tags)
        )
        result = await self._s.execute(stmt)
        if (getattr(result, "rowcount", 0) or 0) > 0:
            await audit_record(
                self._s,
                event_type=AuditEventType.member_tag_removed,
                actor_type=ActorType.admin,
                actor_id=removed_by,
                target_type="member",
                target_id=member_id,
                details={"tags": tags},
            )

    async def bulk_apply(
        self, tag: str, member_ids: list[str], *, applied_by: str | None = None
    ) -> tuple[int, int]:
        """Apply `tag` to many members in one operation. Returns (applied_count, skipped_count)."""
        validate_tag(tag)
        # find which members already have this tag → skip them
        existing_stmt = (
            select(MemberTag.member_id)
            .where(MemberTag.tag == tag, MemberTag.member_id.in_(member_ids))
        )
        already = set((await self._s.execute(existing_stmt)).scalars().all())
        to_add = [m for m in member_ids if m not in already]
        # filter to valid members only
        valid_stmt = select(Member.id).where(Member.id.in_(to_add))
        valid_ids = list((await self._s.execute(valid_stmt)).scalars().all())
        now = datetime.now(UTC)
        by = applied_by or self.BOOTSTRAP_ADMIN
        for mid in valid_ids:
            self._s.add(MemberTag(member_id=mid, tag=tag, added_by=by, added_at=now))
        if valid_ids:
            await self._s.flush()
            await audit_record(
                self._s,
                event_type=AuditEventType.member_tag_bulk_added,
                actor_type=ActorType.admin,
                actor_id=applied_by,
                target_type="tag",
                target_id=tag,
                details={"member_ids": valid_ids, "skipped_already_tagged": list(already)},
            )
        return len(valid_ids), len(already)

    async def list_distinct(self) -> list[TagSummary]:
        stmt = (
            select(MemberTag.tag, func.count(MemberTag.member_id).label("cnt"))
            .group_by(MemberTag.tag)
            .order_by(MemberTag.tag)
        )
        return [
            TagSummary(tag=row.tag, member_count=int(row.cnt))
            for row in (await self._s.execute(stmt)).all()
        ]

    async def delete_tag_globally(self, tag: str, *, deleted_by: str | None = None) -> int:
        """Remove `tag` from all members. Returns count removed."""
        stmt = delete(MemberTag).where(MemberTag.tag == tag)
        result = await self._s.execute(stmt)
        cnt = getattr(result, "rowcount", 0) or 0
        if cnt > 0:
            await audit_record(
                self._s,
                event_type=AuditEventType.member_tag_removed,
                actor_type=ActorType.admin,
                actor_id=deleted_by,
                target_type="tag",
                target_id=tag,
                details={"removed_count": cnt, "scope": "global"},
            )
        return cnt
