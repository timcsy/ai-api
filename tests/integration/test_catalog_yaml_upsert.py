"""US4: YAML CLI load_models — upsert + idempotent + no accidental delete."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from ai_api.db import get_sessionmaker
from ai_api.models import ModelCatalog

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "deploy" / "catalog" / "azure-2026-05.yaml"


async def _load_yaml(path: Path) -> tuple[int, int]:
    import sys

    sys.argv = ["load_models", str(path)]
    from ai_api.cli.load_models import _load

    return await _load(path)


async def _row_count() -> int:
    sm = get_sessionmaker()
    async with sm() as s:
        rows = (await s.execute(select(ModelCatalog))).all()
        return len(rows)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_sample_yaml_inserts_all(app_client) -> None:
    inserted, updated = await _load_yaml(SAMPLE)
    assert inserted == 9
    assert updated == 0
    assert await _row_count() == 9


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_twice_is_idempotent(app_client) -> None:
    await _load_yaml(SAMPLE)
    inserted, updated = await _load_yaml(SAMPLE)
    assert inserted == 0
    assert updated == 9
    assert await _row_count() == 9


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_does_not_delete_unlisted_models(app_client, tmp_path) -> None:
    """Loading a smaller YAML must not remove models already in DB (FR-005)."""
    await _load_yaml(SAMPLE)
    assert await _row_count() == 9

    # Write a minimal YAML with only 1 model; existing 9 must remain
    smaller = tmp_path / "smaller.yaml"
    smaller.write_text(
        """
models:
  - slug: azure/gpt-4o-mini
    provider: azure
    display_name: GPT-4o mini
    family: gpt-4
    description: |
      updated description
    modality_input: [text, image]
    modality_output: [text]
    capabilities: [chat, vision, function-calling]
    context_window: 128000
    cost_tier: low
    recommended_for: [chat]
    tags: [multimodal]
    example_request: {body: {}}
    status: active
"""
    )
    await _load_yaml(smaller)
    assert await _row_count() == 9  # no deletes

    # The one in YAML had its description updated
    sm = get_sessionmaker()
    async with sm() as s:
        m = await s.get(ModelCatalog, "azure/gpt-4o-mini")
        assert m.description.strip().endswith("updated description")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_invalid_cost_tier_aborts(app_client, tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        """
models:
  - slug: azure/bad
    provider: azure
    display_name: Bad
    family: gpt-4
    description: x
    modality_input: [text]
    modality_output: [text]
    capabilities: []
    context_window: 1
    cost_tier: ultra   # invalid
    example_request: {}
"""
    )
    with pytest.raises(SystemExit):
        await _load_yaml(bad)
    assert await _row_count() == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_load_duplicate_slug_aborts(app_client, tmp_path) -> None:
    bad = tmp_path / "dup.yaml"
    bad.write_text(
        """
models:
  - slug: azure/x
    provider: azure
    display_name: X
    family: gpt-4
    description: x
    modality_input: [text]
    modality_output: [text]
    capabilities: []
    context_window: 1
    cost_tier: low
    example_request: {}
  - slug: azure/x
    provider: azure
    display_name: X dup
    family: gpt-4
    description: x
    modality_input: [text]
    modality_output: [text]
    capabilities: []
    context_window: 1
    cost_tier: low
    example_request: {}
"""
    )
    with pytest.raises(SystemExit):
        await _load_yaml(bad)
    assert await _row_count() == 0
