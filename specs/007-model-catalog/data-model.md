# Phase 1 Data Model: 階段 4 — Model Catalog

## 概覽

```
ModelCatalog (new)
  - slug (PK)
  - provider, display_name, family, description
  - modality_input, modality_output, capabilities (JSON lists)
  - context_window, cost_tier
  - recommended_for, tags (JSON lists)
  - example_request (JSON)
  - official_doc_url, status, deprecation_note
  - created_at, updated_at
```

無外鍵；無關聯到 Allocation 或 PriceList（FR-022 NON-GOAL）。

---

## ModelCatalog（新表）

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `slug` | text(128) | ✓ | PK；pattern `provider/model_name` |
| `provider` | text(64) | ✓ | 例 `azure` |
| `display_name` | text(128) | ✓ | 人類可讀名稱（保留大小寫） |
| `family` | text(64) | ✓ | 例 `gpt-4`、`o-series`、`whisper`、`dall-e` |
| `description` | text | ✓ | 繁中描述（保留大小寫） |
| `modality_input` | JSON | ✓ | list of enum: text/image/audio/video/embedding |
| `modality_output` | JSON | ✓ | 同上 |
| `capabilities` | JSON | ✓ | list of enum: chat/vision/function-calling/json-mode/tool-use/streaming/reasoning/embedding/fine-tuning |
| `context_window` | int | ✓ | tokens |
| `cost_tier` | text(8) | ✓ | enum: low/medium/high |
| `recommended_for` | JSON | ✓ | list of free-form strings（常見值見 spec） |
| `tags` | JSON | ✓ | list of free-form strings（如 `multimodal`、`open-source`） |
| `example_request` | JSON | ✓ | 描述性 dict（含 `curl` + `body` 等欄位） |
| `official_doc_url` | text | ✗ | 連結 |
| `status` | text(16) | ✓ | enum: active/preview/deprecated；預設 active |
| `deprecation_note` | text | ✗ | 棄用備註 |
| `created_at` | timestamptz | ✓ | 首次 INSERT 時間 |
| `updated_at` | timestamptz | ✓ | 每次 upsert 更新 |

**Constraints**：
- PK on `slug`
- Index on `status`（list endpoint 預設過濾 active）
- 列舉值驗證在 application 層（Pydantic）— DB 不加 CHECK constraint，方便
  未來擴增列舉不需 migration

---

## YAML schema（CLI 載入用）

```yaml
# deploy/catalog/azure-2026-05.yaml
models:
  - slug: azure/gpt-4o-mini
    provider: azure
    display_name: GPT-4o mini
    family: gpt-4
    description: |
      高 CP 值多模態小模型；支援文字 + 視覺 + function-calling。
    modality_input: [text, image]
    modality_output: [text]
    capabilities: [chat, vision, function-calling, json-mode, tool-use, streaming]
    context_window: 128000
    cost_tier: low
    recommended_for: [chat, agent, summarization, translation, code]
    tags: [multimodal]
    example_request:
      curl: |
        curl -X POST $BASE/v1/chat/completions \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          -d @body.json
      body:
        model: gpt-4o-mini
        messages:
          - {role: user, content: "Hello"}
    official_doc_url: https://learn.microsoft.com/azure/ai-services/openai/...
    status: active

  - slug: azure/dall-e-3
    ...
```

**驗證規則**（Pydantic）：
- `slug` 符合 `^[a-z0-9-]+/[a-z0-9.-]+$`
- list 欄位的元素須在列舉值集合內
- `cost_tier` 必為 low/medium/high
- `status` 必為 active/preview/deprecated
- `recommended_for` 與 `tags` 為 free-form（不驗值）
- `example_request` 必為 dict（內容不驗）

---

## Query Patterns

### Q1: 取得所有 active models（list endpoint 預設）

```sql
SELECT * FROM model_catalog
WHERE status = 'active'
ORDER BY slug;
```

### Q2: facet 計算

DB 端只負責「篩 active models」；facet 在 Python 端聚合（資料量小、跨方言
一致）。

### Q3: detail by slug

```sql
SELECT * FROM model_catalog WHERE slug = :slug;
```

---

## Migration 0006 概要

1. CREATE TABLE `model_catalog`
2. CREATE INDEX `idx_model_catalog_status`
3. 不擴 enum（catalog 列舉用 Pydantic 應用層驗）
4. 不動既有表
