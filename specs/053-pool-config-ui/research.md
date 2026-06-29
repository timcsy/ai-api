# Research: 配額池設定移到前端

所有抉擇有既有前例，無遺留 NEEDS CLARIFICATION。

## R1 — 設定存哪：DB 單例 `pool_config`
- **Decision**：新單例表 `pool_config`（`CHECK id=1`），欄 `total_tokens_per_month`、`floor_per_allocation`、`updated_at`、`updated_by`。
- **Rationale**：比照階段 13 `notification_config` 的單例模式（同 repo 既有、已驗）；配額是業務設定該可編輯（experience「配額類可見可編輯都該高」）。
- **Alternatives**：泛用 key-value 設定表——否決（YAGNI，只有兩個值）；留在 env——否決（要重部署、admin 不能自助）。

## R2 — 單一真理讀取入口（追全 sink）
- **Decision**：新增 `get_pool_config(db)`（get-or-create）為**唯一**讀取點；`services/quota_pool.py::apply_rebalance`（現讀 `settings.pool_*`，~line 181-182）與 `api/quota_pool.py::get_pool_status`（~line 36-38）**都改呼叫它**。
- **Rationale**：原則 5 單一真理 + experience「加欄要追到所有讀寫點」——T/保底現有**兩個** sink，漏一個就 drift（顯示≠執法）。
- **Alternatives**：只改 UI 顯示、rebalance 仍讀 env——否決（顯示≠執法，正是要避免的 drift）。

## R3 — 首讀 lazy-seed 自 env（零行為變更）
- **Decision**：`get_pool_config` 在 DB 無列時，用現行 `settings.pool_total_tokens_per_month`/`pool_floor_per_allocation` 建初始列。env 自此僅作 bootstrap，DB 為 live 真理。
- **Rationale**：搬家不改現狀（FR-003/SC-005）；migration 不易讀 env，改在讀取層 lazy-seed 最穩。
- **Alternatives**：migration 內寫死預設——否決（與目前 env 值可能不符）；要求 admin 先設才能用——否決（破壞現狀）。

## R4 — 建議值
- **Decision**：`suggest_pool_config(db)` 用 `services/usage.py::aggregate_usage` 取近月 total_tokens + 池內成員數 N。建議 T = `round(近月用量 × 2)`；建議保底 = 讓零用量成員有可用底的量級（informed default，UI 文字說明取捨）；回約束所需 N。唯讀、每次算。
- **Rationale**：原則 6——admin 不必自己撈數據估算；資料層既有。
- **Alternatives**：固定建議值——否決（與實際用量脫節）。

## R5 — 驗證與生效時機
- **Decision**：PUT 擋 `T < 保底×N`（硬錯）與負數/非法；`T < 近月用量`回 **soft warning** 欄位（不擋、admin 可確認）。設定**於下次再分配生效**（不即時改寫既有配額），UI 標明。
- **Rationale**：配額設錯爆炸半徑大（全池無法再分配/使用者被擋）→ 需護欄；但「比近月低」可能是刻意縮編 → 警告不擋。生效時機沿用既有 rebalance 機制。

## R6 — 稽核
- **Decision**：新增 `AuditEventType.pool_config_updated`（VARCHAR、`native_enum=False`，無 migration），PUT 成功寫一筆（操作者/時間/新值）。
- **Rationale**：原則 2 可追蹤；沿用既有非 native enum 加值不需 migration 的慣例。
