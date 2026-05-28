# Phase 1 Data Model: Responses API / Agent 工具相容

**Branch**: `021-responses-api` | **Date**: 2026-05-28

對應 spec 的 Key Entities 與 research R3/R4/R5。Alembic migration：`0013_responses_api`。

---

## 1. `call_records`（擴充既有表）

新增兩個 nullable 整數欄位，記錄 Responses 呼叫的 token 分項。**不改既有欄位、
不影響 `/chat/completions` 路徑（新欄位留 NULL）。**

| 欄位 | 型別 | 可空 | 說明 |
|------|------|------|------|
| `reasoning_tokens` | Integer | ✅ | 輸出中屬推理的 token 數（`output_tokens` 的子集，供分析；計費不重複加） |
| `cached_tokens` | Integer | ✅ | 輸入中命中快取的 token 數（`prompt_tokens` 的子集；計費套折扣價） |

**對應規則**（自 Responses usage）：
- `input_tokens` → 既有 `prompt_tokens`
- `output_tokens` → 既有 `completion_tokens`（已含 reasoning）
- `total_tokens` → 既有 `total_tokens`
- `output_tokens_details.reasoning_tokens` → `reasoning_tokens`
- `input_tokens_details.cached_tokens` → `cached_tokens`

**驗證/不變式**：
- `cached_tokens ≤ prompt_tokens`、`reasoning_tokens ≤ completion_tokens`（若兩者皆非空）。
- 缺某類別時填 0 或 NULL，整筆仍須記錄（FR-010，斷線也記 FR-017）。

**用量彙總影響**：`services/usage.py` 的 `aggregate_usage` 可選擇性加總新欄位
（供 `/me/usage` 與 admin 顯示分項）；既有三欄行為不變、零退化。

---

## 2. `price_list`（擴充既有表）

新增一個 nullable 欄位支援快取輸入折扣價；沿用 append-only point-in-time 版本機制。

| 欄位 | 型別 | 可空 | 說明 |
|------|------|------|------|
| `cached_input_per_1k_tokens_usd` | Numeric(12,8) | ✅ | 快取輸入 token 每 1k 折扣價；NULL 表示無折扣（cached 部分以 input 全價計） |

**驗證**：非負；缺值（NULL）時計費 fallback 用 `input_per_1k_tokens_usd`。

---

## 3. `stored_responses`（新表）

支援 `store=true` 與 `previous_response_id` 接續，並強制歸屬隔離（FR-013~016）。
僅存歸屬與 id 映射，不存完整對話內容（research R4）。

| 欄位 | 型別 | 可空 | 說明 |
|------|------|------|------|
| `response_id` | String(64) | ❌ | PK，平台對外回傳的回應識別碼 |
| `allocation_id` | String(26) | ❌ | 產生此回應的分配；歸屬隔離的依據（FK→allocations） |
| `provider` | String(64) | ❌ | 該回應的 provider（接續時須一致） |
| `upstream_response_id` | String(128) | ✅ | 上游（provider）原始回應 id，接續時翻譯用 |
| `created_at` | DateTime(tz=True) | ❌ | 建立時間（`datetime.now(UTC)`） |
| `expires_at` | DateTime(tz=True) | ❌ | 保存期限（預設 created_at + 30 天） |

**索引**：`response_id`（PK）；`(allocation_id)`（稽核查詢）；`(expires_at)`（清理掃描）。

**狀態 / 生命週期**：
- 建立：`store=true` 且呼叫成功 → INSERT 一筆。
- 接續：收到 `previous_response_id` → 以 `response_id` 查表：
  1. 不存在 / `expires_at ≤ now` → 回「找不到/已過期」（FR-016）。
  2. `allocation_id` ≠ 當前分配 → 拒絕（FR-015 歸屬隔離）。
  3. `provider` 與當前請求模型的 provider 不符 → 拒絕（跨 provider 接續無意義）。
  4. 通過 → 以 `upstream_response_id` 轉發上游。
- 清理：背景作業刪除 `expires_at ≤ now`（沿用既有 cronjob 模式）。

**不變式**：一個 `response_id` 永遠歸屬單一 `allocation_id`，不可轉移
（對應原則「轉分配需顯式允許」——預設不可跨分配共用）。

---

## 4. `model_catalog.capabilities`（沿用既有欄位，無 schema 變更）

於既有 JSON list 欄位的值集合中新增 `"responses"` 標記。

- 判定：模型 `capabilities` 含 `"responses"` → 可經 `/v1/responses` 呼叫；否則回不支援（FR-005）。
- 載入：catalog YAML（`deploy/catalog/*.yaml`）對支援的模型補 `responses` capability；
  CLI 載入 idempotent（沿用既有行為）。

---

## Migration 摘要（`0013_responses_api`）

```
op.add_column("call_records", reasoning_tokens INTEGER NULL)
op.add_column("call_records", cached_tokens INTEGER NULL)
op.add_column("price_list", cached_input_per_1k_tokens_usd NUMERIC(12,8) NULL)
op.create_table("stored_responses", ...)  # 見上
```

- 全部欄位 nullable / 新表 → 對既有資料零影響、可安全前滾。
- 須在 Postgres 上跑（CI 已涵蓋）；downgrade 對稱 drop。
- 經驗：Postgres-safe（drop index 在 drop column 之前）、datetime 一律 tz-aware。
