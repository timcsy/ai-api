# Data Model: 管理員成員管理批次化 + 安全刪除

> **無 schema 變更**：不新增表/欄位/migration/enum。本檔記錄（A）安全刪除觸及的既有實體與連帶順序、（B）批次操作的回傳形狀（非持久化）。

## A. 既有實體與安全刪除連帶圖

```
Member (members)
  └─ Allocation (allocations)          member_id FK → members  [DB: ondelete=RESTRICT]
       ├─ CredentialAllocation         allocation_id FK → allocations
       └─ CallRecord (call_records)    allocation_id FK → allocations  [DB: ondelete=SET NULL，但實作走 ORM 顯式]
  └─ Credential (credentials)          member_id FK → members  [DB: ondelete=CASCADE]
       └─ CredentialAllocation         credential_id FK → credentials
```

### 安全刪除（單筆）執行順序（ORM 顯式，單一交易）

| 步驟 | 動作 | 對象 | 稽核 |
|------|------|------|------|
| 1 | 撤回所有 active 分配（狀態機 + 即時撤回） | `Allocation`（該成員、active） | 沿用 revoke 既有稽核 |
| 2 | 將呼叫紀錄的 `allocation_id` 設為 `NULL`（**保留** row） | `CallRecord`（該成員的分配下） | — |
| 3 | 刪除憑證↔分配連結 | `CredentialAllocation`（該成員的憑證或分配側） | — |
| 4 | 刪除憑證 | `Credential`（該成員） | — |
| 5 | 刪除分配 rows | `Allocation`（該成員，含已撤回） | — |
| 6 | 刪除成員 | `Member` | `member_deleted`（操作者、時間、成員 id/email） |

**不變式**：
- 交易結束後，被刪成員的 `CallRecord` rows **仍存在**且 `allocation_id IS NULL`；`subject`（email）保留 → 歸屬可追溯（FR-002、SC-002）。
- 任一步失敗 → 整筆 rollback，成員不停留在半刪狀態（FR-003）。
- 步驟 0（守衛，連帶前）：`cannot_delete_self` / `last_admin` 任一觸發則整筆不執行（FR-014/015）。

### 受影響欄位的既有 FK 行為（僅供對照；實作不依賴）

| 子實體 | FK 欄位 | DB ondelete | 本功能實作 |
|--------|---------|-------------|-----------|
| Allocation | `member_id → members` | RESTRICT | 步驟 5 顯式刪 |
| Credential | `member_id → members` | CASCADE | 步驟 4 顯式刪 |
| CredentialAllocation | `credential_id → credentials`、`allocation_id → allocations` | CASCADE | 步驟 3 顯式刪 |
| CallRecord | `allocation_id → allocations` | SET NULL | 步驟 2 顯式設 NULL |

## B. 批次操作回傳形狀（非持久化）

### 批次刪除結果（每筆）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `member_id` | string | 目標成員 id |
| `status` | enum | `deleted` / `failed` |
| `reason` | string \| null | 失敗原因碼（`cannot_delete_self`、`last_admin`、`not_found`、`internal`） |

整體回應：`{ "results": [ ... ], "deleted": N, "failed": M }`

### 批次新建結果（每筆）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `email` | string | 輸入 email（正規化後） |
| `status` | enum | `created` / `exists` / `invalid` / `duplicate` |
| `invitation_url` | string \| null | 僅 `created` 時提供 |

整體回應：`{ "results": [ ... ], "created": N, "exists": X, "invalid": Y, "duplicate": Z }`

## 驗證規則（來自 spec FR）

- 批次刪除：未選任何成員 → 端點回 400（`bad_request`）；每筆獨立成敗（FR-007/008）。
- 批次新建：空清單 → 400；email 正規化 + 同批去重 + 格式驗證（沿用既有 create 路徑）（FR-010/012、R4）。
- 守衛：刪自己 / 刪最後一位 active 管理員一律拒（單筆 → 對應錯誤；批次 → 該筆 `failed` + 原因）（FR-014/015）。
- 授權：所有端點僅管理員可用（FR-016）。
