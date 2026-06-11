# Data Model: 計費一般化（非 token 單位）+ OCR 端點

> **Migration `0019`：純加欄**（token 欄不動、不改 nullability）。維持單一 head。

## 變更總覽

| 表 | 新增欄 | 型別 | 說明 |
|----|--------|------|------|
| `price_list` | `price_unit` | varchar(16) nullable | 計價單位；NULL ⇒ token（沿用既有 per-1k 欄）。非 token 模型設如 `"page"` |
| `price_list` | `price_per_unit_usd` | Numeric(12,8) nullable | 每單位價（如每頁價）。`price_unit` 非 NULL 時必填 |
| `call_records` | `quantity` | Integer nullable | 計量數量（如頁數）。token 呼叫留 NULL |
| `call_records` | `unit` | varchar(16) nullable | 計量單位；NULL ⇒ token（用既有 token 欄） |

## PriceList（一般化後）

- token 價列（chat / embedding，**不變**）：`input_per_1k_tokens_usd` / `output_per_1k_tokens_usd` / `cached_input_per_1k_tokens_usd` 照填；`price_unit` = NULL、`price_per_unit_usd` = NULL。
- 非 token 價列（OCR）：`price_unit = "page"`、`price_per_unit_usd = <每頁價>`；既有兩個 NOT NULL token 欄填 `0`（對 page-billed 無意義；見 research R1）。
- 不變式維持：append-only、`(provider, model, effective_from)` 唯一、point-in-time（`lookup_price_for_call` 取 `effective_from <= call_time` 的最新一筆）。

**`Price` dataclass（pricing.py）**：加 `price_unit: str | None`、`price_per_unit: Decimal | None`，由 `lookup_price_for_call` 一併帶出。

## CallRecord（一般化後）

- token 呼叫（chat / embedding，**不變**）：`prompt_tokens` / `completion_tokens` / `total_tokens` / `cost_usd` 照填；`quantity` = NULL、`unit` = NULL。
- 非 token 呼叫（OCR）：`unit = "page"`、`quantity = 頁數`、`cost_usd = quantity × 每頁價`；token 欄 NULL。`subject` / `allocation_id` / `outcome` / `model` 與既有一致（歸戶、稽核不變）。

**`record_call`（records.py）**：加參數 `quantity: int | None = None`、`unit: str | None = None`（nullable、預設 None ⇒ token 呼叫端不受影響）。

## 計費計算（pricing.py）

- `calculate_cost(prompt_tokens, completion_tokens, price, ...)`：**完全不動**（token 零回歸）。
- 新增 `calculate_unit_cost(quantity: int | None, price_per_unit: Decimal | None) -> Decimal`：
  - `quantity` 或 `price_per_unit` 為 None / 0 → 回 `Decimal(0)`（沿用「未定價→成本 0」慣例，FR-003 邊界）。
  - 否則回 `Decimal(quantity) * price_per_unit`。

## OCR 計量流（proxy/ocr.py）

```
請求 {model, document} → run_preflight（auth/alloc/access/credential）
  → upstream.aocr(model, document, api_key, api_base, api_version) → OCRResponse
  → pages = usage_info.pages_processed if present else len(response.pages)
  → price = lookup_price_for_call(provider, model, now)
  → cost = calculate_unit_cost(pages, price.price_per_unit if price and price.price_unit=="page" else None)
  → record_call(quantity=pages, unit="page", cost_usd=cost, outcome=success, 歸戶 allocation)
  → 回 OCRResponse（model_dump）
拒絕/上游錯誤 → record_and_respond（沿用 embeddings 的 _outcome_for_code / _error_payload）
```

## 模型類型（model_kind.py）

- `Kind` 加 `"ocr"`；`mode == "ocr"`（讀 `litellm_sync.raw.mode`）→ `"ocr"`。
- 成員目錄 `_to_summary` / `_to_detail` 已輸出 `kind`（Phase 38）→ OCR 模型自動回 `kind="ocr"`，無新序列化。

## 驗證規則（來自 FR）

- 非 token 價列：`price_unit` 非 NULL 時 `price_per_unit_usd` 必填（API 層驗）。
- OCR 計費：`cost = pages × 每頁價`；無每頁價 → cost 0、仍記 pages（FR-003）。
- 改價 point-in-time：新價列 `effective_from` 之後的呼叫用新價，先前 CallRecord 的 `cost_usd` 不追溯（FR-002）。
- 零回歸：token 模型的 PriceList / CallRecord / `calculate_cost` 路徑不變（SC-002）。
- 授權：`/v1/ocr` 走成員金鑰（同 chat/embedding）；admin 每頁價端點僅 admin。
