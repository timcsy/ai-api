# Model Catalog Operations (Phase 4+)

How to maintain the model catalog and align with PriceList.

## TL;DR

- Catalog lives in `deploy/catalog/*.yaml`, loaded by
  `python -m ai_api.cli.load_models <path>`.
- **Upsert by slug.** Re-running the same YAML is idempotent (only
  `updated_at` refreshes). Models not in the YAML are NEVER deleted —
  mark them `status: deprecated` instead.
- Three API endpoints (any active member can use):
  - `GET /catalog/models` — list + filter
  - `GET /catalog/models/{slug}` — detail + `example_request`
  - `GET /catalog/filters` — faceted counts for UI sidebar

## Adding a new model

1. Edit `deploy/catalog/azure-2026-MM.yaml` — append a new `- slug: ...` entry
2. Run `python -m ai_api.cli.load_models deploy/catalog/azure-2026-MM.yaml`
3. Verify via `GET /catalog/models/<slug>`
4. Commit YAML + PR for review

### Field reference

See `data-model.md` in the Phase 4 spec for full schema. Enum-style fields
(modality_input/output, capabilities, cost_tier, status) are validated by
Pydantic at load time — any unknown value aborts the load.

## Deprecating a model

1. Set `status: deprecated` in YAML
2. Add `deprecation_note` (繁中說明 + 替代 model + 預期下架時間)
3. Re-load via CLI
4. Default `GET /catalog/models` will hide it; detail endpoint still returns
   it for migration reference.

## PriceList alignment

The catalog's `slug` and PriceList's `provider/model` are linked by convention,
not foreign key:

- Catalog `slug: azure/gpt-4o-mini` ↔ PriceList `provider=azure, model=gpt-4o-mini`

When introducing a new model:

- Submit catalog YAML + PriceList YAML in the **same PR**
- Failure to add PriceList means `cost_tier` is the only price hint UI can show
- `cost_tier` is human-curated in catalog (low/medium/high) and is independent
  of absolute USD numbers

## Future hooks (NON-GOAL today)

- Auto-sync from Azure / LiteLLM registry — currently manual YAML only
- Integration into "create allocation" flow as a model picker — left to 3b UI
- Real-time price computation — would join catalog × PriceList in detail endpoint
