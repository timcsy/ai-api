# 契約：admin LiteLLM 對接端點

全部在 `/admin` 下、admin-only（沿用既有 admin 認證）。錯誤封包沿用既有 `{error:{code,message}}`。

## 1. `GET /admin/catalog/litellm/search?q=<query>&limit=20`

搜尋 LiteLLM 登錄表 key（給新增頁的 picker）。讀 **bundled** `litellm.model_cost`（不線上抓）。

**200**：
```json
{ "results": [
  { "key": "azure/gpt-4o", "provider": "azure", "mode": "chat",
    "context_window": 128000, "supports_vision": true,
    "suggested_price": { "input_per_1k": "0.0025", "output_per_1k": "0.01", "cached_input_per_1k": "0.00125" } }
] }
```
- 契約測試：`q=gpt-4o` 命中含 `azure/gpt-4o`；空 `q` 回空或熱門；`limit` 生效。

## 2. `GET /admin/catalog/litellm/suggest/{key:path}`

取單一 key 的帶入建議（新增帶入 / 對照基礎模型借用）。讀 bundled。

**200**：帶入草稿（slug 預設 = key；查無回 404 `litellm_model_not_found`）：
```json
{ "key": "azure/gpt-4o", "slug_default": "azure/gpt-4o",
  "metadata": { "context_window": 128000, "modality_input": ["text","image"],
                "modality_output": ["text"], "capabilities": ["vision","function_calling"] },
  "suggested_price": { "input_per_1k": "0.0025", "output_per_1k": "0.01", "cached_input_per_1k": "0.00125" },
  "imported_version": "1.85.1" }
```
- 契約測試：`azure/gpt-4o` 回完整 metadata + 建議價；查無 key → 404。

## 3. 建立模型（既有 `POST /admin/catalog/models` 擴充）

`ModelCatalogCreate` 加選填欄位：
- `base_model_key: str | null` —— 對照基礎模型 key（自訂 slug 借用時）。
- `litellm_sync: {field_sources, snapshot, imported_version} | null` —— 由前端帶入草稿產生；後端驗證後落 `model_catalog.litellm_sync`。
- 若帶建議價：沿用既有建立價目流程 append 一筆 `PriceList`，`source_note="litellm@<ver>"`。

- 契約測試：帶 litellm_sync 建立 → 模型 `litellm_sync` 落地、欄位來源正確；附建議價 → 產生一筆 `PriceList` 帶 litellm source_note；手改某欄 → 該欄 source=manual。

## 4. `POST /admin/catalog/models/{slug:path}/litellm-check`

檢查更新：**線上抓最新**（timeout，失敗回退 bundled），與目前值 + `litellm_sync.snapshot` 逐欄比對。

**200**：
```json
{ "source": "live",                          // 或 "bundled-fallback"
  "litellm_version": "1.85.1",
  "base_model_key": "azure/gpt-4o",
  "diffs": [
    { "field": "context_window", "current": 128000, "latest": 200000, "source": "litellm", "changed": true },
    { "field": "capabilities", "current": ["vision"], "latest": ["vision","function_calling"], "source": "manual", "changed": true },
    { "field": "price.input_per_1k", "current": "0.0025", "latest": "0.0030", "source": "litellm", "changed": true }
  ] }
```
- 規則：`source="manual"` 的欄 `changed` 仍可為 true（提示）但**不可被自動採納**；前端應禁勾或明示。
- 契約測試：mock live 回新值 → diffs 正確標 changed + source；mock live 丟例外/逾時 → `source:"bundled-fallback"`、仍回 diffs（對 bundled）。

## 5. `POST /admin/catalog/models/{slug:path}/litellm-apply`

採納選定欄位。Body：
```json
{ "fields": ["context_window", "price.input_per_1k"], "litellm_version": "1.85.1" }
```
- 規則：只套用 `fields` 中、且**非 manual** 的欄；metadata 欄寫回 `model_catalog` 並更新 `litellm_sync.snapshot`/`imported_version`、該欄 source=litellm；`price.*` 欄 → **append 一筆 `PriceList`** 帶 `source_note="litellm@<ver>"`（不覆寫舊版）。留稽核。
- **422**：若 `fields` 含 manual 欄 → 拒絕該欄（或忽略 + 回報），不靜默覆寫。
- 契約測試：採納 context_window → model 更新 + snapshot 更新；採納 price → 新增 `PriceList`、舊版本仍在、計費取最新版；採納清單含 manual 欄 → 不套用該欄。

## 零回歸契約

- 既有 `GET /admin/catalog/models`、建立/更新/刪除、價目 API、`current_price_map`、proxy 計費 **行為不變**；`litellm_sync` 為 null 的既有模型一切照舊。
