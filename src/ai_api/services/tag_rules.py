"""Phase 5.2: TagRule service — regex guard, first-match-wins evaluation, CRUD,
and the registration-time hook that auto-tags new members.

Regex matchers run only on the cold path (member first creation), never on the
login hot path, so a standard-``re`` engine with three guards (anchor + length
cap + complexity check) is sufficient — no ``re2`` dependency. See research.md.
"""
from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.models import MatcherType, TagRule, TagSource
from ai_api.services.member_tags import MemberTagService, validate_tag

logger = logging.getLogger(__name__)

# Max local-part length fed to a regex matcher (FR-007): bounds backtracking.
LOCALPART_MAX = 64
# Reject patterns with more than this many quantifiers (defense-in-depth).
MAX_QUANTIFIERS = 10

# Nested quantifier: a group containing a +/* quantifier, itself quantified.
# Catches the textbook ReDoS forms: (a+)+, (.*)*, (a+)* ...
_NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*][^)]*\)[+*?]")
_QUANTIFIER_CHARS = re.compile(r"[+*{]")


class UnsafeRegexError(ValueError):
    """Raised when a localpart regex fails compile / anchor / complexity guards."""


def guard_regex(pattern: str) -> str:
    """Validate a localpart regex and return its anchored form.

    Raises ``UnsafeRegexError`` on uncompilable, nested-quantifier, or
    excessively complex patterns.
    """
    raw = pattern.strip()
    if not raw:
        raise UnsafeRegexError("empty pattern")
    if _NESTED_QUANTIFIER.search(raw):
        raise UnsafeRegexError("nested quantifier (ReDoS risk)")
    if len(_QUANTIFIER_CHARS.findall(raw)) > MAX_QUANTIFIERS:
        raise UnsafeRegexError("too many quantifiers")
    try:
        re.compile(raw)
    except re.error as exc:
        raise UnsafeRegexError(f"uncompilable regex: {exc}") from exc
    if raw.startswith("^") and raw.endswith("$"):
        return raw
    return f"^(?:{raw})$"


class RuleMatch(TypedDict):
    matched: bool
    rule_id: str | None
    tag: str | None
    matcher_type: MatcherType | None


_NO_MATCH: RuleMatch = {"matched": False, "rule_id": None, "tag": None, "matcher_type": None}


def _matches(rule: Any, email: str, local: str, domain: str) -> bool:
    mt = rule.matcher_type
    if mt == MatcherType.always:
        return True
    if mt == MatcherType.email_localpart_regex:
        try:
            return re.fullmatch(rule.pattern, local) is not None
        except re.error:
            logger.warning("tag_rule %s has invalid stored pattern; skipping", getattr(rule, "id", "?"))
            return False
    if mt == MatcherType.email_suffix:
        return bool(email.lower().endswith(rule.pattern.lower()))
    if mt == MatcherType.email_domain:
        return bool(domain.lower() == rule.pattern.lower())
    return False


def evaluate(email: str, rules: list[Any]) -> RuleMatch:
    """First-match-wins over enabled rules sorted by order_index ascending."""
    local, _, domain = email.partition("@")
    local = local[:LOCALPART_MAX]
    for rule in sorted(rules, key=lambda r: r.order_index):
        if not rule.enabled:
            continue
        if _matches(rule, email, local, domain):
            return {
                "matched": True,
                "rule_id": rule.id,
                "tag": rule.tag,
                "matcher_type": rule.matcher_type,
            }
    return dict(_NO_MATCH)  # type: ignore[return-value]


class TagRuleService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_rules(self) -> list[TagRule]:
        stmt = select(TagRule).order_by(TagRule.order_index)
        return list((await self._s.execute(stmt)).scalars().all())

    async def _enabled_sorted(self) -> list[TagRule]:
        stmt = (
            select(TagRule)
            .where(TagRule.enabled.is_(True))
            .order_by(TagRule.order_index)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    @staticmethod
    def _normalize(matcher_type: MatcherType, pattern: str) -> str:
        """Validate/normalize pattern for the matcher; returns stored pattern."""
        if matcher_type == MatcherType.email_localpart_regex:
            return guard_regex(pattern)
        if matcher_type == MatcherType.always:
            return ""
        # suffix / domain: plain strings, just trim
        return pattern.strip()

    async def create(
        self,
        *,
        matcher_type: MatcherType,
        tag: str,
        pattern: str = "",
        enabled: bool = True,
        created_by: str = "bootstrap-admin",
    ) -> TagRule:
        from datetime import UTC, datetime

        validate_tag(tag)  # raises ValueError → mapped to invalid_tag
        stored_pattern = self._normalize(matcher_type, pattern)
        # append last
        existing = await self.list_rules()
        next_order = (max((r.order_index for r in existing), default=-1)) + 1
        rule = TagRule(
            id=str(ULID()),
            order_index=next_order,
            matcher_type=matcher_type,
            pattern=stored_pattern,
            tag=tag,
            enabled=enabled,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
        self._s.add(rule)
        await self._s.flush()
        return rule

    async def update(
        self,
        rule_id: str,
        *,
        matcher_type: MatcherType | None = None,
        pattern: str | None = None,
        tag: str | None = None,
        enabled: bool | None = None,
    ) -> TagRule | None:
        rule = await self._s.get(TagRule, rule_id)
        if rule is None:
            return None
        if tag is not None:
            validate_tag(tag)
            rule.tag = tag
        # determine effective matcher + pattern for normalization
        eff_matcher = matcher_type if matcher_type is not None else rule.matcher_type
        if matcher_type is not None:
            rule.matcher_type = matcher_type
        if pattern is not None or matcher_type is not None:
            eff_pattern = pattern if pattern is not None else rule.pattern
            rule.pattern = self._normalize(eff_matcher, eff_pattern)
        if enabled is not None:
            rule.enabled = enabled
        await self._s.flush()
        return rule

    async def delete(self, rule_id: str) -> bool:
        rule = await self._s.get(TagRule, rule_id)
        if rule is None:
            return False
        await self._s.delete(rule)
        await self._s.flush()
        return True

    async def reorder(self, order: list[str]) -> list[TagRule] | None:
        """Rewrite all order_index in one shot. Returns None if id-set mismatch."""
        rules = await self.list_rules()
        if {r.id for r in rules} != set(order) or len(order) != len(rules):
            return None
        by_id = {r.id: r for r in rules}
        for idx, rid in enumerate(order):
            by_id[rid].order_index = idx
        await self._s.flush()
        return await self.list_rules()

    async def test_email(self, email: str) -> RuleMatch:
        """Dry-run: no DB write, no member created (FR-015)."""
        return evaluate(email, await self._enabled_sorted())

    async def apply_to_new_member(self, member_id: str, email: str, *, applied_by: str = "auto_register") -> str | None:
        """Run rules at member first creation and auto-tag on first match.

        Never raises into the registration flow: on any failure it logs and
        returns None so member creation always succeeds.
        """
        try:
            match = evaluate(email, await self._enabled_sorted())
            if not match["matched"] or match["tag"] is None:
                return None
            await MemberTagService(self._s).add(
                member_id,
                [match["tag"]],
                added_by=applied_by,
                source=TagSource.auto,
                rule_id=match["rule_id"],
            )
            return match["tag"]
        except Exception:  # pragma: no cover - defensive: never break registration
            logger.exception("auto-tag failed for member %s; continuing", member_id)
            return None
