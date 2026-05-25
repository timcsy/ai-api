"""CLI: load model_catalog entries from a YAML file (upsert by slug).

Idempotent: re-running with the same YAML updates `updated_at` but no schema
changes. Per spec FR-005, models NOT listed in the YAML are NEVER deleted —
mark them deprecated instead.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from ai_api.config import get_settings
from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.models import DefaultAccess, ModelCatalog
from ai_api.observability.logging import setup_logging
from ai_api.services.model_catalog import CatalogYAML


def _lower_list(items: Sequence[str]) -> list[str]:
    return [s.strip().lower() for s in items]


async def _load(path: Path) -> tuple[int, int]:
    raw = yaml.safe_load(path.read_text())
    try:
        doc = CatalogYAML.model_validate(raw)
    except ValidationError as exc:
        print(f"load_models: YAML validation failed:\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    # Detect duplicate slugs in YAML itself
    seen: set[str] = set()
    for entry in doc.models:
        if entry.slug in seen:
            print(
                f"load_models: duplicate slug in YAML: {entry.slug}", file=sys.stderr
            )
            raise SystemExit(1)
        seen.add(entry.slug)

    # Phase 5: enforce provider allowlist at load-time.
    allowed = set(get_settings().allowed_providers)
    for entry in doc.models:
        if entry.provider not in allowed:
            print(
                f"load_models: provider {entry.provider!r} for slug {entry.slug!r} "
                f"is not in ALLOWED_PROVIDERS={sorted(allowed)}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    sm = get_sessionmaker()
    now = datetime.now(UTC)
    inserted = 0
    updated = 0
    async with sm() as s:
        for entry in doc.models:
            existing = await s.get(ModelCatalog, entry.slug)
            if existing is None:
                s.add(
                    ModelCatalog(
                        slug=entry.slug,
                        provider=entry.provider,
                        display_name=entry.display_name,
                        family=entry.family.lower(),
                        description=entry.description,
                        modality_input=_lower_list(entry.modality_input),
                        modality_output=_lower_list(entry.modality_output),
                        capabilities=_lower_list(entry.capabilities),
                        context_window=entry.context_window,
                        cost_tier=entry.cost_tier.lower(),
                        recommended_for=_lower_list(entry.recommended_for),
                        tags=_lower_list(entry.tags),
                        example_request=entry.example_request,
                        official_doc_url=entry.official_doc_url,
                        status=entry.status.lower(),
                        deprecation_note=entry.deprecation_note,
                        default_access=DefaultAccess(entry.default_access),
                        allowed_tags=list(entry.allowed_tags),
                        denied_tags=list(entry.denied_tags),
                        created_at=now,
                        updated_at=now,
                    )
                )
                inserted += 1
            else:
                existing.provider = entry.provider
                existing.display_name = entry.display_name
                existing.family = entry.family.lower()
                existing.description = entry.description
                existing.modality_input = _lower_list(entry.modality_input)
                existing.modality_output = _lower_list(entry.modality_output)
                existing.capabilities = _lower_list(entry.capabilities)
                existing.context_window = entry.context_window
                existing.cost_tier = entry.cost_tier.lower()
                existing.recommended_for = _lower_list(entry.recommended_for)
                existing.tags = _lower_list(entry.tags)
                existing.example_request = entry.example_request
                existing.official_doc_url = entry.official_doc_url
                existing.status = entry.status.lower()
                existing.deprecation_note = entry.deprecation_note
                existing.default_access = DefaultAccess(entry.default_access)
                existing.allowed_tags = list(entry.allowed_tags)
                existing.denied_tags = list(entry.denied_tags)
                existing.updated_at = now
                updated += 1
        await s.commit()
    return inserted, updated


async def _main() -> int:
    setup_logging()
    if len(sys.argv) != 2:
        print(
            "Usage: python -m ai_api.cli.load_models <yaml-path>", file=sys.stderr
        )
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"load_models: file not found: {path}", file=sys.stderr)
        return 2
    try:
        inserted, updated = await _load(path)
    finally:
        await dispose_engine()
    print(f"loaded: inserted={inserted} updated={updated}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
