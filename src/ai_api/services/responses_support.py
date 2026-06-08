"""Phase 25: responses support state machine (axis ③ — gateway endpoint availability).

Whether a model can be driven via /v1/responses (the Codex/Agent entry point) is
decided by *real call result* or *admin override* — NOT by a static litellm-derived
flag. This module is the single source of truth for that state, carried in the
existing ``ModelCatalog.capabilities`` JSON list via internal markers so no new
column / migration is needed.

Three axes, kept decoupled:
  ① model native API type   → litellm ``mode`` (snapshot only)
  ② model capabilities      → litellm flags (vision/reasoning/...)
  ③ gateway responses       → THIS module (tested / manual), never touched by litellm

Markers (mutually-exclusive invariants enforced by every transition):
  ``responses``           — available (bare value; the catalog badge + member facet read this)
  ``responses:blocked``   — admin manually disabled (the ONLY pre-block at runtime)
  ``responses:tested``    — source = tested
  ``responses:manual``    — source = manual

``responses:*`` (colon) markers are internal; member-facing serialization strips
them via :func:`strip_internal`, leaving only the bare ``responses`` badge.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.models import ModelCatalog

RESPONSES = "responses"
RESPONSES_BLOCKED = "responses:blocked"
RESPONSES_TESTED = "responses:tested"
RESPONSES_MANUAL = "responses:manual"

_ALL_MARKERS = (RESPONSES, RESPONSES_BLOCKED, RESPONSES_TESTED, RESPONSES_MANUAL)

State = Literal["available", "unavailable", "unknown"]
Source = Literal["tested", "manual"]


class Support(TypedDict):
    state: State
    source: Source | None


def get_support(caps: Iterable[str]) -> Support:
    """Derive responses support state + source from a capabilities list.

    Precedence guarantees *manual wins*: blocked > available; manual source > tested.
    """
    s = set(caps)
    if RESPONSES_BLOCKED in s:
        return {"state": "unavailable", "source": "manual"}
    if RESPONSES in s:
        source: Source | None = (
            "tested" if RESPONSES_TESTED in s else "manual" if RESPONSES_MANUAL in s else None
        )
        return {"state": "available", "source": source}
    return {"state": "unknown", "source": None}


def _without_markers(caps: Iterable[str]) -> list[str]:
    """Drop every responses* marker, preserving order and dropping duplicates."""
    out: list[str] = []
    for c in caps:
        if c in _ALL_MARKERS or c in out:
            continue
        out.append(c)
    return out


def _set(caps: Iterable[str], markers: tuple[str, ...]) -> list[str]:
    return _without_markers(caps) + list(markers)


def mark_tested_ok(caps: Iterable[str]) -> list[str]:
    return _set(caps, (RESPONSES, RESPONSES_TESTED))


def mark_tested_failed(caps: Iterable[str]) -> list[str]:
    # A failed test does not mark the model available; reset to unknown.
    return _set(caps, ())


def mark_manual_on(caps: Iterable[str]) -> list[str]:
    return _set(caps, (RESPONSES, RESPONSES_MANUAL))


def mark_manual_off(caps: Iterable[str]) -> list[str]:
    return _set(caps, (RESPONSES_BLOCKED, RESPONSES_MANUAL))


def strip_internal(caps: Iterable[str]) -> list[str]:
    """Member-facing view: keep the bare ``responses`` badge, drop colon markers."""
    return [c for c in caps if c == RESPONSES or not c.startswith("responses:")]


def preserve_into(new_caps: Iterable[str], old_caps: Iterable[str]) -> list[str]:
    """Merge-preserve: take ``new_caps`` (e.g. from a litellm adopt) but carry over
    every responses* marker that already existed in ``old_caps``. litellm MUST NOT
    add/remove responses state (FR-006)."""
    kept = [c for c in new_caps if c not in _ALL_MARKERS]
    carried = [c for c in _ALL_MARKERS if c in set(old_caps)]
    return kept + carried


async def lookup(session: AsyncSession, slug: str) -> Support:
    """Read responses support for a catalog slug. Missing row → unknown."""
    row = (
        await session.execute(select(ModelCatalog).where(ModelCatalog.slug == slug))
    ).scalar_one_or_none()
    if row is None:
        return {"state": "unknown", "source": None}
    return get_support(row.capabilities or [])
