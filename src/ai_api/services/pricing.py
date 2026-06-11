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
    cached_input_per_1k: Decimal | None = None
    # Phase 29 ②: non-token unit price. price_unit NULL ⇒ token billing.
    price_unit: str | None = None
    price_per_unit: Decimal | None = None


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
        cached_input_per_1k=row.cached_input_per_1k_tokens_usd,
        price_unit=row.price_unit,
        price_per_unit=row.price_per_unit_usd,
    )


def calculate_cost(
    *,
    price: Price | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cached_tokens: int | None = None,
) -> Decimal | None:
    """Compute USD cost. Returns None when no price is available.

    `prompt_tokens` includes `cached_tokens`; cached input is billed at the
    discounted `cached_input_per_1k` when defined, else at the full input price.
    `completion_tokens` already includes any reasoning tokens (not added again).
    """
    if price is None:
        return None
    cached = Decimal(cached_tokens or 0)
    pt = Decimal(prompt_tokens or 0)
    full_input = pt - cached
    if full_input < 0:  # defensive: cached can't exceed prompt
        full_input = Decimal(0)
        cached = pt
    ct = Decimal(completion_tokens or 0)
    cached_rate = price.cached_input_per_1k if price.cached_input_per_1k is not None else price.input_per_1k
    return (
        (full_input / Decimal(1000)) * price.input_per_1k
        + (cached / Decimal(1000)) * cached_rate
        + (ct / Decimal(1000)) * price.output_per_1k
    )


def calculate_unit_cost(quantity: int | None, price_per_unit: Decimal | None) -> Decimal:
    """Phase 29 ②: cost for a non-token metered call = quantity x per-unit price.

    Returns Decimal(0) when quantity or price is missing/zero (sustains the
    existing 'unpriced → cost 0' convention for non-token units).
    """
    if not quantity or price_per_unit is None:
        return Decimal(0)
    return Decimal(quantity) * price_per_unit


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
            "cached_input_per_1k": (
                _price_str(current.cached_input_per_1k_tokens_usd)
                if current.cached_input_per_1k_tokens_usd is not None
                else None
            ),
            "price_unit": current.price_unit,
            "price_per_unit": (
                _price_str(current.price_per_unit_usd)
                if current.price_per_unit_usd is not None
                else None
            ),
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


async def current_price_map(
    db: AsyncSession, now: datetime
) -> dict[tuple[str, str], dict[str, str]]:
    """(provider, model_key) → current {input_per_1k, output_per_1k} for catalog
    display. model_key is the prefix-stripped billing key."""
    all_prices = (await db.execute(select(PriceList))).scalars().all()
    by_key: dict[tuple[str, str], list[PriceList]] = {}
    for p in all_prices:
        by_key.setdefault((p.provider, p.model), []).append(p)
    out: dict[tuple[str, str], dict[str, str]] = {}
    for key, versions in by_key.items():
        cur = select_current_version(versions, now)
        if cur is not None:
            entry = {
                "input_per_1k": _price_str(cur.input_per_1k_tokens_usd),
                "output_per_1k": _price_str(cur.output_per_1k_tokens_usd),
            }
            if cur.cached_input_per_1k_tokens_usd is not None:
                entry["cached_input_per_1k"] = _price_str(cur.cached_input_per_1k_tokens_usd)
            out[key] = entry
    return out


def price_for_slug(
    price_map: dict[tuple[str, str], dict[str, str]], provider: str, slug: str
) -> dict[str, str] | None:
    """Look up a catalog model's current price by (provider, prefix-stripped slug)."""
    return price_map.get((provider, _model_key(slug)))


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
            "cached_input_per_1k": (
                _price_str(v.cached_input_per_1k_tokens_usd)
                if v.cached_input_per_1k_tokens_usd is not None
                else None
            ),
            "price_unit": v.price_unit,
            "price_per_unit": (
                _price_str(v.price_per_unit_usd) if v.price_per_unit_usd is not None else None
            ),
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
    cached_input_per_1k: str | Decimal | None = None,
    price_unit: str | None = None,
    price_per_unit: str | Decimal | None = None,
    source_note: str | None = None,
    created_by: str = "admin",
) -> dict[str, Any]:
    """Append-only price version. Raises InvalidPriceError / DuplicateVersionError."""
    try:
        inp = Decimal(str(input_per_1k))
        outp = Decimal(str(output_per_1k))
        cached = (
            Decimal(str(cached_input_per_1k))
            if cached_input_per_1k is not None and str(cached_input_per_1k) != ""
            else None
        )
        per_unit = (
            Decimal(str(price_per_unit))
            if price_per_unit is not None and str(price_per_unit) != ""
            else None
        )
    except (InvalidOperation, ValueError) as exc:
        raise InvalidPriceError("unit price is not a valid number") from exc
    if inp < 0 or outp < 0 or (cached is not None and cached < 0) or (per_unit is not None and per_unit < 0):
        raise InvalidPriceError("unit price must be non-negative")
    if effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=UTC)

    row = PriceList(
        id=str(ULID()),
        provider=provider,
        model=model,
        input_per_1k_tokens_usd=inp,
        output_per_1k_tokens_usd=outp,
        cached_input_per_1k_tokens_usd=cached,
        price_unit=price_unit or None,
        price_per_unit_usd=per_unit,
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
        "cached_input_per_1k": (
            _price_str(row.cached_input_per_1k_tokens_usd)
            if row.cached_input_per_1k_tokens_usd is not None
            else None
        ),
        "price_unit": row.price_unit,
        "price_per_unit": (
            _price_str(row.price_per_unit_usd) if row.price_per_unit_usd is not None else None
        ),
        "effective_from": row.effective_from.isoformat(),
        "source_note": row.source_note,
        "created_at": row.created_at.isoformat(),
        "created_by": row.created_by,
        "is_current": current is not None,
    }
