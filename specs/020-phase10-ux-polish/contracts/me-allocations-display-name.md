# 契約: `GET /me/allocations` 新增 `display_name`（additive）

成員自己的分配清單。本功能在每筆回應**新增** `display_name` 欄位，其餘不變、向後相容。

## 回應（每筆 allocation，節錄）

```jsonc
{
  "id": "01...",
  "resource_model": "azure/gpt-5.4-mini",   // slug（不變）
  "display_name": "GPT-5.4 mini (Azure deployment)",  // 新增：來自目錄；orphan→null
  "status": "active",
  "quota_tokens_per_month": null,
  "token_prefix": "aiapi_xx",
  "price": { "input_per_1k": "0.00015", "output_per_1k": "0.0006" }  // 既有，或 null
}
```

| 欄位 | 規則 |
|------|------|
| `display_name` | 該 `resource_model`(slug) 在 `model_catalog` 的顯示名稱；slug 不在目錄（orphan）→ `null` |

## 不變式
- 既有欄位（`resource_model`、`price`、`status`、`quota_tokens_per_month`、`token_prefix` 等）型別與語意不變。
- 純 additive；既有前端不受影響（多一個可選欄位）。
- 唯讀；不改動分配資料。

## 前端 UI 契約（呈現）
- 分配卡片：標題以 `display_name` 為主（null 時退回 `resource_model`），slug 為輔（小字）。
- 現價：`price` 經 per-1M 格式化顯示；`price=null` → 「未定價」。
- 可自助領取卡片：整卡可點 → `/catalog/{slug}`；「領取」鈕點擊不導頁。
- 呼叫端點：dashboard 與「如何呼叫」範例皆顯示同一 `apiBaseUrl()`。
