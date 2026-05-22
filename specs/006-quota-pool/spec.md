# Feature Specification: 階段 3c — Adaptive Quota Pool

**Feature Branch**: `006-quota-pool`
**Created**: 2026-05-22
**Status**: Draft
**Input**: User description: "階段 3c adaptive quota pool — 自然月窗、rollback、提供手動 trigger"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 自動每月再分配，用越多拿越多 (Priority: P1)

擁有者設定組織總 token 池 `T`、每位成員保底 `floor`。每月 UTC 月初自動跑
rebalance：上個自然月用越多的 allocation 拿到越多 quota；上個月沒用的仍
拿到 `floor`。完成後**全體 quota 守恆**：`Σq_i = T`。

**Why this priority**：vision 3c 的核心承諾；缺它整個自適應功能無意義。

**Independent Test**：seed 3 個 allocation，上月用量比 5:3:2、T=1000、
floor=100，rebalance 後 quota 應為 450 / 310 / 240，且總和 = 1000。

**Acceptance Scenarios**:

1. **Given** T=1000、floor=100、3 個 active 非服務型 allocation A/B/C
   且上月用量比 5:3:2，**When** rebalance 跑完，**Then**
   `A.quota = 100 + 700 × (5/10) = 450`、`B = 310`、`C = 240`；
   `Σq = 1000`。
2. **Given** 同上設定但其中 1 個 allocation 上月零用量，**When** rebalance，
   **Then** 該 allocation 仍拿到 `floor = 100`；剩餘 `(T - floor × N)`
   按比例分給有用量的。
3. **Given** rebalance 完成，**When** 檢查 audit log，**Then** 有一筆
   `quota_pool_rebalanced` 事件含掃描數、變更數、總量、演算法版本。
4. **Given** 第一次跑（無人有歷史用量），**When** rebalance，**Then**
   均分 `T/N` 給每個 allocation（每人至少 floor）。

---

### User Story 2 - 守恆失敗即整批 rollback (Priority: P1)

任何環節失敗（演算法 bug、DB 卡住、`Σq ≠ T`），rebalance 必須整批 rollback —
**不可以**留下「部分人變了 quota、部分沒」的不一致狀態。

**Why this priority**：vision「能量守恆」的本質；若可部分成功，下個月加總
會偏離 T，馬太效應的「公平性承諾」立刻崩塌。

**Independent Test**：故意讓中段一筆 `Allocation.update` 拋例外 → 觀察
rebalance 全部回滾、quota 維持 rebalance 前的值；audit 紀錄
`rebalance_failed`。

**Acceptance Scenarios**:

1. **Given** rebalance 跑到一半某筆 update 失敗，**When** 觀察 DB，**Then**
   所有 allocation 的 quota 維持 rebalance 前的值。
2. **Given** rebalance 計算完所有新 quota 但 `Σq_new ≠ T`，**When** 守恆
   檢核，**Then** 拋例外、rollback、寫 audit `rebalance_failed` 含原因。
3. **Given** rebalance 失敗，**When** 下個月初再次自動觸發，**Then** 正常
   嘗試（不會被「永久卡住」狀態鎖住）。

---

### User Story 3 - 服務型與鎖定分配不被動 (Priority: P1)

`is_service_allocation=true` 的高額度服務分配與 `quota_locked=true` 的
admin 手動鎖定分配，**不進池、不被 rebalance 覆寫**；但它們占用的 quota
從 T 中扣除，剩下的才是「池內可分配額度」。

**Why this priority**：呼應 vision 既有設計（服務型分配豁免）；rebalance
若動到它們會破壞「給 service 的固定承諾」。

**Independent Test**：服務型 + locked allocation 各設 quota=500，T=2000、
2 個池內 allocation → rebalance 後池內可分配 = `2000 - 500 - 500 = 1000`，
服務型與 locked 的 quota 不變。

**Acceptance Scenarios**:

1. **Given** allocation X `is_service_allocation=true, quota=500`，**When**
   rebalance，**Then** X 的 quota 不變；池內可分配額 = `T - 500`。
2. **Given** allocation Y `quota_locked=true, quota=300`，**When** rebalance，
   **Then** Y 的 quota 不變；池內可分配額再扣 300。
3. **Given** 服務型 + locked 占用合計超過 T，**When** rebalance 開始檢查，
   **Then** 拋例外、rollback、寫 audit `pool_exhausted_by_reserved` 警告
   admin 調整 T 或刪除某些 reserved allocation。

---

### User Story 4 - 新加入的 allocation 拿 floor 直到下個月 (Priority: P2)

月中新建立的 allocation 還沒有「上個月用量」可比；先給 floor，下次月初
（有了完整一個月的觀察）再進入再分配。

**Why this priority**：呼應 vision 3c edge case；避免新加入者吃光池或被
歧視。

**Independent Test**：5/15 建立新 allocation Z（無歷史），rebalance 在
6/1 跑：Z 拿到 `floor`，其他人按 5/1~5/31 用量比例分。

**Acceptance Scenarios**:

1. **Given** 月中（5/15）新建 allocation Z，**When** 月初（6/1）rebalance，
   **Then** Z 拿 `floor`，剩餘 `(T - floor × N)` 給其他人按上月用量比例
   分（Z 不參與比例計算）。
2. **Given** Z 在 6 月有用量，**When** 7/1 rebalance，**Then** Z 與其他人
   一起按 6 月用量比例分。

---

### User Story 5 - admin 可手動觸發 rebalance (Priority: P2)

CronJob 漏跑、admin 想立刻試新的 `floor` 或 `T` 值時，可手動呼叫
`POST /admin/quota-pool/rebalance` 立即執行。

**Why this priority**：vision 已決定提供此能力；避免「rebalance 漏一次要
等下個月」。

**Independent Test**：admin 改 `pool_total_tokens_per_month` 後 `POST
/admin/quota-pool/rebalance`，回 200，看到新 quota 套用。

**Acceptance Scenarios**:

1. **Given** admin 有 admin token，**When** `POST /admin/quota-pool/rebalance`，
   **Then** 200 + 回傳 `{rebalance_log_id, scanned, changed, total_T}`。
2. **Given** rebalance 失敗（如 reserved > T），**When** 手動觸發，**Then**
   回 409 + `error.code=pool_exhausted` 或 `rebalance_failed`，並寫 audit。
3. **Given** 無 admin token，**When** 呼叫，**Then** 401。

---

### User Story 6 - admin 可查池狀態與歷史 (Priority: P2)

「現在池有多大？多少被服務型／locked 占用？池內 N 個 allocation
平均多少？上次 rebalance 是何時、改了誰？」

**Why this priority**：debug、容量規劃；UI（3b）會用，但 API 先就緒
方便手動查。

**Independent Test**：`GET /admin/quota-pool/status` 回目前狀態；
`GET /admin/quota-pool/rebalance-log?limit=10` 回近 10 次 rebalance 摘要。

**Acceptance Scenarios**:

1. **Given** admin token，**When** `GET /admin/quota-pool/status`，**Then**
   回 `{total_T, reserved_by_service, reserved_by_locked, distributable, pool_member_count, floor, last_rebalance_at}`。
2. **Given** rebalance 已跑過數次，**When** `GET /admin/quota-pool/rebalance-log`，
   **Then** 回近 N 筆 RebalanceLog 摘要，每筆含時間、觸發者（cron/admin/user）、
   scanned、changed、total。

### Edge Cases

- **T 改變但人數未變**：admin 把 T 從 1000 改成 2000 → 下次 rebalance
  每人 quota 比例放大 2x（保底也維持 floor）。
- **單一 allocation 但 quota_locked=true**：rebalance 池內 0 人，
  distributable 全部閒置；audit 寫「pool_idle」警告 admin 是否該調 T。
- **rebalance 跑到一半 admin 手動 PATCH 改 quota**：transaction 隔離應該
  讓 PATCH 看到的是 rebalance 完成的結果；rebalance 在交易內整個算完才
  commit。
- **floor × N > T**：rebalance 拒絕執行，寫 audit + 通知 admin。
- **active 但 status=quarantined 的 allocation**：不在池內（rebalance
  視為非 active）；解除 quarantine 後下次月初才回到池。
- **CronJob 重複觸發（如 retry）**：用「同月最多一次 cron rebalance」
  保護 — RebalanceLog 含 `period_yyyymm`，UNIQUE 約束防止重複自動跑。
  手動觸發不受此限。

## Requirements *(mandatory)*

### Functional Requirements

#### 設定
- **FR-001**: `Settings` 新增 `pool_total_tokens_per_month: int`（T）、
  `pool_floor_per_allocation: int`（floor）。預設 T=0（disabled）、
  floor=1000。
- **FR-002**: 系統 MUST 提供方式（環境變數）動態調整 T 與 floor；下次
  rebalance 即生效。

#### Allocation 擴充
- **FR-003**: `Allocation` 新增 `quota_locked: bool`（預設 false）；
  rebalance MUST 不修改 `quota_locked=true` 的 allocation 的 quota。

#### Rebalance 演算法（核心）
- **FR-004**: 月度錨點 MUST 為 UTC 月初；「上月用量」定義為「自然月 1 日
  00:00:00 UTC 到該月最後一日 23:59:59 UTC」的 `total_tokens` 加總
  （outcome=success only）。
- **FR-005**: 池內成員 = active && !is_service_allocation && !quota_locked &&
  status != quarantined。
- **FR-006**: 池內可分配額 `D = T - Σ(reserved_quotas of service/locked)`。
  若 `D < floor × N_pool` 即視為 `pool_exhausted` 並 rollback。
- **FR-007**: 演算法：
  ```
  if Σ usage_last_month == 0:    # cold start / 無歷史
      q_i = D / N_pool            # 均分
  else:
      q_i = floor + (D - floor × N_pool) × (usage_i / Σ usage)
  ```
  四捨五入造成 `Σq_i ≠ D` 的零頭加到用量最高的那個 allocation
  （以確保完美守恆）。
- **FR-008**: rebalance 結束前 MUST 跑守恆檢核：`Σ(all allocations.quota) == T`；
  失敗即整批 rollback（FR-013）。

#### Transaction / Rollback
- **FR-009**: rebalance MUST 在單一 DB transaction 內完成；任何例外或守恆
  檢核失敗 → 整批 rollback、寫 audit `rebalance_failed`。
- **FR-010**: rebalance 過程不 lock 整表（避免阻塞代理呼叫）；採 row-level
  選擇性 update。

#### 歷史 / 觀測
- **FR-011**: 新增 `RebalanceLog` 表，每次成功 rebalance 寫一筆，含
  `id`、`period_yyyymm`、`triggered_by`（`cron|admin|user_id`）、
  `started_at`、`finished_at`、`T_before`、`T_after`、`scanned`、`changed`、
  `algorithm_version`、`details`（JSON：每筆 allocation 的 before/after quota）。
- **FR-012**: cron 觸發的 rebalance MUST 對 `period_yyyymm` UNIQUE — 同月
  cron 重複觸發第二次直接 no-op（不重複算）。手動觸發不受此限。
- **FR-013**: 失敗的 rebalance MUST 寫 audit `rebalance_failed`（不寫
  RebalanceLog，保持後者只記錄成功）。

#### CLI / CronJob
- **FR-014**: 新增 `python -m ai_api.cli.run_rebalance` CLI；K8s CronJob
  排程 `0 0 1 * *`（每月 1 日 UTC 00:00）。

#### API
- **FR-015**: `POST /admin/quota-pool/rebalance`：手動觸發；admin token
  必填；回 200 + RebalanceLog 摘要，或 409 + 結構化錯誤。
- **FR-016**: `GET /admin/quota-pool/status`：回 T、reserved、distributable、
  N_pool、floor、`last_rebalance_at`。
- **FR-017**: `GET /admin/quota-pool/rebalance-log?limit=N`：回近 N 筆
  RebalanceLog 摘要（不展開 `details` 大欄位）。
- **FR-018**: `GET /admin/quota-pool/rebalance-log/{id}`：回單筆完整含
  `details`。

#### 不在本階段範圍
- **FR-019** (NON-GOAL): 即時池容量視覺化（留 3b UI）。
- **FR-020** (NON-GOAL): 多池切分（按 model / Team / 部門）。
- **FR-021** (NON-GOAL): 跨月借貸 / token roll-over。
- **FR-022** (NON-GOAL): EWMA 平滑（首版用單月窗；觀察一段時間再決定是否
  需要時間平滑）。

### Key Entities

- **RebalanceLog**（新表）：
  - `id` (ULID)、`period_yyyymm` (text，例 `202605`)、
    `triggered_by` (text，`cron` / `admin:<token-id>` / `user:<member-id>`)、
    `started_at` / `finished_at` (timestamptz)、
    `T_before` / `T_after` (int)、
    `scanned` (int，掃描的 active allocation 總數)、
    `changed` (int，實際被改 quota 的數)、
    `algorithm_version` (text，例 `v1`)、
    `details` (jsonb：`{"<allocation_id>": {"before": X, "after": Y, "usage": Z, "reason": "..."}}`)
  - UNIQUE on `(period_yyyymm, triggered_by)` WHERE `triggered_by = 'cron'`
    — 防止 cron 同月重複跑

- **Allocation**（擴充）：加 `quota_locked: bool default=false`。

- **AuthAuditLog**（沿用）：新增 event_type 列舉值 `rebalance_failed`、
  `pool_exhausted_by_reserved`、`pool_idle`、`quota_pool_rebalanced`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 守恆驗證：對 T=1000、floor=100、3 個池內 allocation 按 5:3:2
  用量做 rebalance，結果 quota 為 450/310/240 且 `Σ = 1000`。
- **SC-002**: 服務型與 locked 豁免：rebalance 不改動 `is_service_allocation`
  或 `quota_locked` 的 allocation。
- **SC-003**: Rollback：模擬中段 update 失敗，rebalance 後**所有** allocation
  的 quota 維持失敗前的值。
- **SC-004**: 失敗不留痕：失敗時無 `RebalanceLog` 寫入，僅有
  `AuthAuditLog` 一筆 `rebalance_failed`。
- **SC-005**: Cron 去重：手動兩次觸發 cron job 同一個月，第二次 no-op
  並回傳「already done」訊息（cron 觸發；手動 API 不受限）。
- **SC-006**: `POST /admin/quota-pool/rebalance` 手動觸發後立即生效：
  下一次 `/v1/chat/completions` 的 quota 檢查使用新值。
- **SC-007**: 既有 Phase 1+2+2.5+2.6+3a 全部 140 tests 不回歸。
- **SC-008**: 所有 FR 在 git 歷史可見「test commit 早於 impl commit」
  （延續 TDD 紀律）。

## Assumptions

- **池總量 T 由環境變數設定**：未提供管理 T 的 UI / API（admin 改值後重
  起服務或下次 rebalance 才生效）。
- **單一全域池**：所有 active 非服務型非鎖定 allocation 共享同一個 T；
  未來多租戶／多 model 切池為 NON-GOAL。
- **時鐘 / 月份判斷**：用 server UTC 當下時間；上月 = `current_month - 1`
  （rebalance 在 6/1 跑就看 5 月資料）。
- **無歷史用量的 cold start**：均分到每人 `D / N_pool`，每人都 ≥ floor。
- **演算法 version 字串**：第一版 `v1`；未來換 EWMA 或別的就 `v2`；
  RebalanceLog 紀錄方便回溯「為什麼這月跟上月分配方式不同」。
- **手動觸發頻率**：admin 可隨時觸發；不做 rate limit（信任 admin token
  持有者；極端濫用情況下走 audit 追溯）。
