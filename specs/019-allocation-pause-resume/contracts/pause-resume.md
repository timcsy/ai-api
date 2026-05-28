# 契約: 憑證暫停 / 恢復端點

管理員操作，比照既有 `POST /admin/allocations/{id}/unquarantine`。需 admin 認證（`require_admin_token`：X-Admin-Token 或 admin session）。

## `POST /admin/allocations/{allocation_id}/pause`

把一把 active 憑證暫停。

| 情境 | 狀態碼 | 回應 |
|------|--------|------|
| allocation 為 active | 200 | 更新後 allocation（status=`paused`） |
| allocation 不存在 | 404 | `{detail:{error:{code:"not_found", ...}}}` |
| allocation 非 active（paused / revoked / quarantined） | 409 | `{detail:{error:{code:"invalid_state", message:"allocation is <status>, cannot pause"}}}` |
| 未授權 | 401 | admin auth 要求 |

副作用：`status active→paused`；寫稽核 `allocation_paused`。**不**動 token / 配額 / reclaim lock。

## `POST /admin/allocations/{allocation_id}/resume`

把一把 paused 憑證恢復。

| 情境 | 狀態碼 | 回應 |
|------|--------|------|
| allocation 為 paused | 200 | 更新後 allocation（status=`active`） |
| allocation 不存在 | 404 | not_found |
| allocation 非 paused（active / revoked / quarantined） | 409 | `{detail:{error:{code:"invalid_state", message:"allocation is <status>, cannot resume"}}}` |
| 未授權 | 401 | admin auth 要求 |

副作用：`status paused→active`；寫稽核 `allocation_resumed`。token 不變。

## Proxy 行為（`POST /v1/*`）

| 情境 | 結果 |
|------|------|
| 憑證 status=`paused` 的呼叫 | 403，error code `allocation_paused`，message「allocation is paused」；記為 `CallOutcome.rejected_paused`（不計費） |
| 恢復後同一 token 的呼叫 | 正常處理（與暫停前無異） |

## 不變式
- pause/resume 為冪等之外的**狀態守衛**：對非目標狀態一律 409、目標憑證零改動。
- `allocation_paused` 拒絕原因可與 `allocation_revoked`、`quota_exceeded`、`allocation_quarantined` 區分。
- 既有 revoke（DELETE）/ unquarantine 行為不變。
