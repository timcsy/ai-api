# Phase 1 Data Model: responses 支援判斷

**無 schema 變更、無新表、無 migration。** responses 支援狀態以既有 `model_catalog.capabilities`（JSON list of str）的標記約定承載。

## 既有實體：`ModelCatalog`（不改欄位）

相關既有欄：
- `capabilities: list[str]`（JSON）——承載 responses 標記 + 既有能力詞彙（hyphenated：`function-calling`/`vision`/…）。
- `litellm_sync: dict | None`（JSON）——**不**含任何 responses 狀態（三軸解耦，FR-006）。

## 概念子狀態：responses 支援（軸③）

封裝於 `src/ai_api/services/responses_support.py`，由 `capabilities` 中的標記推導：

### 標記詞彙（互斥維護）

| 標記 | 角色 |
|---|---|
| `responses` | 可用旗（既有值，徽章 + 舊閘門所讀） |
| `responses:blocked` | 手動不可用（唯一事前封鎖） |
| `responses:tested` | 來源＝實測 |
| `responses:manual` | 來源＝手動 |

> `responses:*`（含冒號）為內部標記，成員 facet 序列化時過濾，不對外顯示為能力。

### 狀態（讀取）

```text
Support = { state: "available" | "unavailable" | "unknown",
            source: "tested" | "manual" | None }
```

推導順序（保證手動優先）：
1. `responses:blocked` ∈ caps → `available=unavailable, source=manual`
2. 否則 `responses` ∈ caps → `state=available`；source＝`tested`（若 `responses:tested`）否則 `manual`（若 `responses:manual`）否則 `None`
3. 否則 → `state=unknown, source=None`

### 狀態轉移（寫入；每次先移除所有 `responses*` 再設新值）

| 觸發 | 結果標記集 | state / source |
|---|---|---|
| 測試通過（US2） | `responses`, `responses:tested` | available / tested |
| 測試失敗（US2） | （無 responses 標記） | unknown / None |
| 手動設可用（US3） | `responses`, `responses:manual` | available / manual |
| 手動設不可用（US3） | `responses:blocked`, `responses:manual` | unavailable / manual |
| LiteLLM 同步採納能力（FR-006） | **保留**既有 `responses*` 原樣 | 不變（merge-preserve） |

### 不變式

- 任一時刻 `responses` 與 `responses:blocked` **不**同時存在（互斥）。
- `responses:tested` 與 `responses:manual` **不**同時存在。
- LiteLLM 同步（採納/衍生）**MUST NOT** 增刪任何 `responses*` 標記。
- `_capabilities`（litellm_registry）**MUST NOT** 產生任何 `responses*`。

## runtime 判斷（軸③ 唯一事前封鎖）

| state | `/v1/responses` 行為 |
|---|---|
| `unavailable` | 事前擋（`model_responses_disabled`，400，清楚訊息） |
| `available` / `unknown` | 先試（走既有上游 aresponses）；打不通回帶上游原因的 `upstream_error` |
