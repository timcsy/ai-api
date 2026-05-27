"""Pricing service: point-in-time lookup + cost calculation + admin maintenance."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from ai_api.auth.audit import record as audit_record
from ai_api.models import ActorType, AuditEventType, ModelCatalog, PriceList


@dataclass(frozen=True)
class Price:
    input_per_1k: Decimal
    output_per_1k: Decimal
    provider: str
    model: str
    effective_from: datetime


async def lookup_price_for_call(
    db: AsyncSession, *, provider: str, model: str, call_time: datetime
) -> Price | None:
    """Return the PriceList row in effect at `call_time`, else None."""
    stmt = (
        select(PriceList)
        .where(
            PriceList.provider == provider,
            PriceList.model == model,
            PriceList.effective_from <= call_time,
        )
        .order_by(PriceList.effective_from.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return Price(
        input_per_1k=row.input_per_1k_tokens_usd,
        output_per_1k=row.output_per_1k_tokens_usd,
        provider=row.provider,
        model=row.model,
        effective_from=row.effective_from,
    )


def calculate_cost(
    *,
    price: Price | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> Decimal | None:
    """Compute USD cost. Returns None when no price is available."""
    if price is None:
        return None
    pt = Decimal(prompt_tokens or 0)
    ct = Decimal(completion_tokens or 0)
    return ((pt / Decimal(1000)) * price.input_per_1k) + (
        (ct / Decimal(1000)) * price.output_per_1k
    )


# ---------------------------------------------------------------------------
# Phase 7: price list admin (view / history / add). Reuses the same
# point-in-time selection as lookup_price_for_call; no schema change.
# ---------------------------------------------------------------------------


class DuplicateVersionError(Exception):
    """(provider, model, effective_from) already exists."""


class InvalidPriceError(ValueError):
    """Unit price negative / non-numeric, or effective_from missing tz."""


def _model_key(slug: str) -> str:
    """Billing key = catalog slug with the '<provider>/' prefix stripped,
    matching proxy/router.py's `requested_model.split('/', 1)[-1]`."""
    return slug.split("/", 1)[-1]


def _aware(dt: datetime) -> datetime:
    """Coerce naive datetimes to UTC. SQLite drops tzinfo on round-trip even for
    DateTime(timezone=True); SQL-side comparisons avoid this, but our Python-side
    selection must not crash on naive-vs-aware. (experience: datetime tz-aware)"""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def select_current_version(versions: Sequence[Any], now: datetime) -> Any | None:
    """The version in effect at `now`: latest effective_from <= now, else None.
    Pure (works on ORM rows or SimpleNamespace)."""
    now = _aware(now)
    eligible = [v for v in versions if _aware(v.effective_from) <= now]
    if not eligible:
        return None
    return max(eligible, key=lambda v: _aware(v.effective_from))


def _price_str(d: Decimal) -> str:
    return str(d)


async def list_catalog_prices(db: AsyncSession, now: datetime) -> list[dict[str, Any]]:
    """One row per catalog model with its current effective price or unpriced."""
    models = (await db.execute(select(ModelCatalog))).scalars().all()
    all_prices = (await db.execute(select(PriceList))).scalars().all()
    by_key: dict[tuple[str, str], list[PriceList]] = {}
    for p in all_prices:
        by_key.setdefault((p.provider, p.model), []).append(p)

    def _current_dict(current: Any) -> dict[str, Any] | None:
        if current is None:
            return None
        return {
            "input_per_1k": _price_str(current.input_per_1k_tokens_usd),
            "output_per_1k": _price_str(current.output_per_1k_tokens_usd),
            "effective_from": current.effective_from.isoformat(),
        }

    rows: list[dict[str, Any]] = []
    catalog_keys: set[tuple[str, str]] = set()
    for m in models:
        key = _model_key(m.slug)
        catalog_keys.add((m.provider, key))
        current = select_current_version(by_key.get((m.provider, key), []), now)
        rows.append({
            "provider": m.provider,
            "model": key,
            "slug": m.slug,
            "display_name": m.display_name,
            "priced": current is not None,
            "current": _current_dict(current),
            "in_catalog": True,
        })
    # Orphan prices: priced (provider, model) keys with no matching catalog model
    # (e.g. freely-added or a model later removed). Surface so they aren't a dead end.
    for (provider, model), versions in by_key.items():
        if (provider, model) in catalog_keys:
            continue
        current = select_current_version(versions, now)
        rows.append({
            "provider": provider,
            "model": model,
            "slug": f"{provider}/{model}",
            "display_name": "",  # frontend shows a "不在 catalog" badge instead
            "priced": current is not None,
            "current": _current_dict(current),
            "in_catalog": False,
        })
    rows.sort(key=lambda r: (not r["in_catalog"], r["slug"]))
    return rows


async def list_history(db: AsyncSession, provider: str, model: str) -> list[dict[str, Any]]:
    """All versions for a (provider, model) key, newest first, with is_current."""
    stmt = (
        select(PriceList)
        .where(PriceList.provider == provider, PriceList.model == model)
        .order_by(PriceList.effective_from.desc())
    )
    versions = list((await db.execute(stmt)).scalars().all())
    current = select_current_version(versions, datetime.now(UTC))
    current_id = current.id if current is not None else None
    return [
        {
            "id": v.id,
            "input_per_1k": _price_str(v.input_per_1k_tokens_usd),
            "output_per_1k": _price_str(v.output_per_1k_tokens_usd),
            "effective_from": v.effective_from.isoformat(),
            "source_note": v.source_note,
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "is_current": v.id == current_id,
        }
        for v in versions
    ]


async def create_version(
    db: AsyncSession,
    *,
    provider: str,
    model: str,
    input_per_1k: str | Decimal,
    output_per_1k: str | Decimal,
    effective_from: datetime,
    source_note: str | None = None,
    created_by: str = "admin",
) -> dict[str, Any]:
    """Append-only price version. Raises InvalidPriceError / DuplicateVersionError."""
    try:
        inp = Decimal(str(input_per_1k))
        outp = Decimal(str(output_per_1k))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPriceError("unit price is not a valid number") from exc
    if inp < 0 or outp < 0:
        raise InvalidPriceError("unit price must be non-negative")
    if effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=UTC)

    row = PriceList(
        id=str(ULID()),
        provider=provider,
        model=model,
        input_per_1k_tokens_usd=inp,
        output_per_1k_tokens_usd=outp,
        effective_from=effective_from,
        created_at=datetime.now(UTC),
        created_by=created_by,
        source_note=source_note,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateVersionError(
            f"price for ({provider}, {model}, {effective_from.isoformat()}) already exists"
        ) from exc

    await audit_record(
        db,
        event_type=AuditEventType.price_version_added,
        actor_type=ActorType.admin,
        actor_id=created_by,
        target_type="model",
        target_id=f"{provider}/{model}",
        details={"provider": provider, "model": model, "effective_from": effective_from.isoformat()},
    )
    current = select_current_version([row], datetime.now(UTC))
    return {
        "id": row.id,
        "input_per_1k": _price_str(row.input_per_1k_tokens_usd),
        "output_per_1k": _price_str(row.output_per_1k_tokens_usd),
        "effective_from": row.effective_from.isoformat(),
        "source_note": row.source_note,
        "created_at": row.created_at.isoformat(),
        "created_by": row.created_by,
        "is_current": current is not None,
    }
