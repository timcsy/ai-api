# Phase 0 Research: 憑證暫停 / 恢復

## R1: 用新狀態值還是新欄位表達「暫停」

**Decision**: 在既有 `AllocationStatus` 加列舉值 `paused`（不新增 boolean 欄位）。

**Rationale**:
- allocation 的生命週期已用單一 `status` 表達（active / revoked / quarantined），proxy 也只認 status；暫停是同一條生命週期上的另一個狀態，加值最自然、執法點統一。
- `status` 欄位為 `Enum(AllocationStatus, native_enum=False, length=16)` → 存 VARCHAR(16)，加 `paused`（6 字元）**不需 migration**。
- 新增 boolean `is_paused` 會與 status 形成兩個事實來源、proxy 要多查一處，違反 YAGNI 與單一事實來源。

**Alternatives considered**: 加 `is_paused` boolean — 否決（雙事實來源）。重用 `quarantined` 當暫停 — 否決（語意污染：quarantined 是異常偵測器的自動結果，混用會讓「為何被擋」難追，且 unquarantine 路徑會誤解除）。

## R2: 三個 enum 是否需要 migration

**Decision**: 都不需要。三者皆 `native_enum=False`（存字串）：
- `AllocationStatus`：`Enum(..., native_enum=False, length=16)` → 加 `paused`
- `CallOutcome`：`Enum(..., native_enum=False, length=32)` → 加 `rejected_paused`（15 字元）
- `AuditEventType`：`Enum(..., native_enum=False, length=64)` → 加 `allocation_paused` / `allocation_resumed`

**Rationale**: `native_enum=False` 讓 SQLAlchemy 以 VARCHAR + CHECK-free 方式存字串，新增 Python 列舉值即可，DB 無 enum type 需 `ALTER TYPE`。願景先前標的 migration 疑慮就此解除。

## R3: pause/resume 服務方法的形狀（與 revoke 的差異）

**Decision**: `AllocationService` 加 `pause(allocation_id)` / `resume(allocation_id)`，比照 `revoke` 的查找 + 稽核結構，但：
- **只切 status**（active→paused / paused→active），**不**設 `revoked_at`、**不**呼叫 `_lock_reclaim`、**不**動 token / 配額。
- 狀態機守衛：`pause` 僅當 `status==active`，否則回可辨識錯誤；`resume` 僅當 `status==paused`。
- 各寫稽核：`allocation_paused` / `allocation_resumed`（actor=admin）。

**Rationale**: FR-003/004——可逆、保留 token、不建鎖定是本功能與 revoke 的本質區別。狀態機守衛滿足 FR-007、保護 revoked/quarantined 既有語意。

**Alternatives considered**: 讓 resume 一併解除 reclaim lock — 否決（暫停本就不建 lock，無需解；混入會牽動自助領取語意）。

## R4: proxy 如何擋暫停中的呼叫

**Decision**: 在 `proxy/router.py` 既有狀態檢查段（已對 `revoked` / `quarantined` 各回拒絕）加一條 `status == "paused"` → 回 `allocation_paused`（403）；error map 加 `"allocation_paused": CallOutcome.rejected_paused`，使被擋呼叫記為 `rejected_paused`。

**Rationale**: 沿用「逐次呼叫檢查當前狀態」執法點 → 暫停即時生效（FR-005）。`rejected_paused` 讓用量/稽核可與 revoked / quota 區分（FR-008）。
**借鏡 experience**「拒絕路徑必須在 raise 前綁定上下文」：router.py 已「先 lookup allocation 再檢查狀態」，新增 paused 分支沿用此順序，紀錄帶得到 allocation_id。

## R5: admin 端點形狀

**Decision**: 比照 `POST /allocations/{id}/unquarantine`，在 `api/allocations.py`（`require_admin_token` router，prefix `/admin`）加：
- `POST /allocations/{id}/pause` → 200 回更新後 allocation；404 不存在；409 狀態衝突（非 active）。
- `POST /allocations/{id}/resume` → 200；404；409（非 paused）。

**Rationale**: 與既有 revoke（DELETE）/ unquarantine（POST 子資源）一致；動詞型子資源端點符合既有慣例。

## R6: 前端

**Decision**: `admin/allocations.tsx`（與 `member-detail.tsx`）的分配列／詳情，在「撤回」旁加「暫停／恢復」：active → 顯示「暫停」；paused → 顯示「恢復」+ 狀態徽章。文案明確區分暫停（可恢復、保留 token）與撤回（終局）。

**Rationale**: FR-001/002 的操作入口；Edge「與撤回的區別」要求 UI 可區分。複用既有列/詳情，不另開頁（experience「同概念別做兩份」）。

## 測試策略（TDD）

| 測試 | 類型 | 對應 |
|------|------|------|
| `pause()` active→paused；`resume()` paused→active；各寫稽核 | contract/service | FR-001/002/006 |
| `pause` 非 active（revoked/quarantined/已 paused）→ 拒絕、不改動 | contract | FR-007, US3 |
| `resume` 非 paused → 拒絕 | contract | FR-007, US3 |
| pause 後 token / 配額 / 無 reclaim lock 不變 | contract | FR-003/004, US1-AS3 |
| 端點 pause/resume：200 / 404 / 409 | contract | 契約 |
| 暫停中以原 token 呼叫 proxy → 403 `allocation_paused`、計 `rejected_paused` | integration | FR-005/008, US1-AS2 |
| 恢復後**原 token** 呼叫 proxy → 成功 | integration | FR-003, US2-AS2 |
| 前端：active 顯「暫停」、paused 顯「恢復」、文案區分撤回 | frontend RTL | US1/US2, Edge |
| 既有 revoke / unquarantine / quota / usage 零退化 | 全套 | FR-009, SC-005 |

無 NEEDS CLARIFICATION 待解。
