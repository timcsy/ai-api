# Phase 1 資料模型：模型目錄 ↔ LiteLLM 登錄表對接

**1 個 additive 欄位（migration `0018`）**，其餘沿用既有 `model_catalog` / `price_list`。

## 變更：`model_catalog` 加 `litellm_sync`（nullable JSON）

```python
litellm_sync: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
```

結構：

```jsonc
{
  "base_model_key": "azure/gpt-4o",   // litellm 對照 key；同名匯入時 = slug；純手填模型為 null
  "imported_version": "1.85.1",        // 匯入/上次採納時的 litellm 套件版本
  "field_sources": {                   // 每個「可同步欄位」的來源
    "context_window":  "litellm",      // "litellm" | "borrowed" | "manual"
    "modality_input":  "litellm",
    "modality_output": "litellm",
    "capabilities":    "manual"        // 被 admin 手改 → manual
  },
  "snapshot": {                        // 匯入/上次採納當下的 litellm 值（供 diff 比對）
    "context_window": 128000,
    "modality_input": ["text","image"],
    "modality_output": ["text"],
    "capabilities": ["vision","function_calling"]
  }
}
```

**規則**：
- 可同步欄位 = `{context_window, modality_input, modality_output, capabilities}`（價格獨立走 `price_list`）。
- 純手填模型 `litellm_sync = null`（與既有目錄零回歸）。
- admin 手改某可同步欄 → 該欄 `field_sources` 轉 `"manual"`。
- migration **additive、nullable**——既有列維持 `null`，不改主鍵、不重建表。

## 既有：`price_list`（不改 schema）

採納/帶入建議價 = `INSERT` 一筆：
- `input_per_1k_tokens_usd` = `litellm.input_cost_per_token × 1000`
- `output_per_1k_tokens_usd` = `× 1000`
- `cached_input_per_1k_tokens_usd` = `cache_read_input_token_cost × 1000`（缺則 null）
- `effective_from` = now、`created_by` = admin、**`source_note` = `"litellm@1.85.1"`**
- 舊版本保留（append-only）。

## 外部（唯讀，非本系統資料）：LiteLLM 登錄表

- bundled：`litellm.model_cost`（dict，~2776 筆）。
- live：`litellm.get_model_cost_map(litellm.model_cost_map_url)`。
- 單筆：`litellm.get_model_info(slug)`。
- 欄位對應見 research.md Decision 2。

## 狀態轉移（field source）

```
新增帶入 ─→ litellm（同名）/ borrowed（對照基礎模型）
admin 手改該欄 ─→ manual
檢查更新採納該欄 ─→ litellm（並更新 snapshot + imported_version）
檢查更新「未勾選」或「manual」欄 ─→ 不變
```
