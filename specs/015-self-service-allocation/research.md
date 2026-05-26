# Phase 0 — Research

## R1：領取資格判定 — 複用 evaluate_visibility

**Decision**：成員能否領取某 model = `evaluate_visibility(model, member_tags, active_providers)["visible"]` 為 true **且** `model.self_service_enabled`。不另寫資格邏輯。

**Rationale**：spec 明確「被 access policy 允許」就是既有可見性判定（credential gate ∩ default_access ∩ deny/allow tags）。重寫會產生兩套會 drift 的邏輯。`self_service_enabled` 是獨立的第三道閘（看得到 ≠ 可自助領）。

**Alternatives**：另寫資格函式（否決：重複、會與 catalog 可見性 drift）。

## R2：origin 放在 Allocation 上

**Decision**：`Allocation` 加 `origin` 欄（enum `admin` / `self_service`，default `admin`）。

**Rationale**：
- 「每 model 最多一張有效自助」「撤回觸發鎖定」都只作用於自助路徑 → 需要在 allocation 上分辨來源
- 它是 allocation 的固有屬性，不該另立表
- default `admin` 讓既有資料與既有 `AllocationService.create` 呼叫零變動（backfill `admin`）

**Alternatives**：用 `created_by` 字串判斷（否決：脆弱，created_by 是自由字串）。

## R3：撤回鎖定的儲存 — 獨立 join 表

**Decision**：新表 `self_service_reclaim_locks`，PK `(member_id, model_slug)`。撤回一張 `origin=self_service` 的 allocation 時 upsert 一筆；admin 解鎖 = 刪該 row；領取時檢查該 row 不存在。

**Rationale**：
- 鎖是 `(member, model)` 維度，與「哪一張 allocation」解耦（同一 pair 歷史上可能多張）
- 比「在 revoked allocation 上加 unlocked 旗標」清楚：admin 可直接列出「目前有哪些鎖」、解鎖語意 = 刪 row
- 極簡：兩個 FK 欄 + 時間，無狀態機

**Alternatives**：
- revoked allocation 上加 `reclaim_unlocked` 旗標（否決：要掃所有 revoked 自助 allocation 才知是否鎖定，查詢繞）
- 完全用「存在 revoked 自助 allocation」推導（否決：無法表達「已解鎖」）

## R4：自助領取的配額來源

**Decision**：領取時 `quota_tokens_per_month = model.self_service_default_quota`。allocation 比照一般**非服務型**（`is_service_allocation=false`、`quota_locked=false`）進既有 quota pool，月初 rebalance。per-model 預設值是**初始/種子配額**。

**Rationale**：呼應 spec「走既有 quota pool」；admin 每 model 設的預設值是領取當下的起始額度，之後交給 3c 池子動態調整（與手動建立的 allocation 一致 → SC-005 零回歸）。

**約束**：`self_service_enabled=true` 時 `self_service_default_quota` 必填（FR-002）；開放但不設配額會被拒。

## R5：成員領取端點

**Decision**：`POST /me/allocations`，body `{model}`；deps `current_member` + `require_csrf`（同 me.py 既有 mutation）。回 `201 {token, allocation}`（token 一次性）或 4xx：
- `model_not_self_service`（422/403）：model 未開放
- `model_forbidden`（403）：access policy 不允許
- `already_claimed`（409）：已有有效自助 allocation（回既有摘要，不重發）
- `reclaim_locked`（403）：被鎖定，需 admin 解鎖
- `member_inactive`（403）

**Rationale**：放 `me` 命名空間（成員自己的資源）；複用既有認證/CSRF；錯誤碼明確讓前端給對應提示。

## R6：撤回鎖定的掛載點

**Decision**：在 `AllocationService.revoke()` 內，撤回成功後若 `allocation.origin == self_service`，upsert `self_service_reclaim_locks(member_id, resource_model)`。

**Rationale**：`revoke()` 是唯一撤回路徑（admin DELETE 端點、成員詳情頁、跨成員總覽都走它）→ 一處掛載全覆蓋。手動建立（`origin=admin`）的撤回不建鎖（FR-010 只針對自助）。

## R7：admin 開放設定端點

**Decision**：新端點 `PATCH /admin/catalog/models/{slug}/self-service`，body `{enabled: bool, default_quota: int|null}`。`enabled=true` 但 `default_quota` 缺 → 422。寫 audit `model_access_policy_updated`（複用，details 標 self_service）或新事件（見 R8）。

**Rationale**：與既有 `/access` 端點平行、職責單一；不把自助設定塞進 `/access`（avoid 把「配額」混進「access」語意）。

## R8：解鎖端點與 audit 事件

**Decision**：
- 解鎖：`POST /admin/self-service-locks/unlock` body `{member_id, model_slug}`（slug 含 `/` 故走 body 不走 path）；`GET /admin/self-service-locks` 列目前所有鎖。
- audit：`auth_audit` 既有 enum **無 allocation_created/revoked**，故新增 3 個值：`self_service_claimed`、`self_service_reclaim_locked`、`self_service_unlocked`（migration 0012 一併擴 enum）；model 開放設定變更複用 `model_access_policy_updated`（details 標 `self_service`）。

**Rationale**：FR-013 要求領取/鎖定/解鎖可稽核；既有 enum 沒有可複用的領取/撤回事件，故新增最小集合（3 個）。比照 Phase 5 以 migration 擴 enum 的做法。
