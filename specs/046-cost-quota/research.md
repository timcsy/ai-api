# Phase 0 Research: 成本制配額

spec 無 `[NEEDS CLARIFICATION]`；本檔釘死 5 個實作層設計問題到可實作程度。所有結論都對照既有程式實況（非臆測）。

---

## R1：本月累計花費的計算來源與效能

**Decision**：新增 `current_month_cost(db, allocation_id) -> Decimal`，與既有 `current_month_usage`（token）**對稱**——`sum(call_records.cost_usd)`、`outcome == success`、`started_at >= 月初(UTC)`，`coalesce(…, 0)`。回 `Decimal`（不轉 float）。

**Rationale**：
- `call_records.cost_usd`（`Numeric(10,6)`，0019 既有）每筆呼叫都落（token 與非 token 一致）；以它加總＝以「花費」為跨單位共同分母（vision 階段 29 既定結論）。
- 既有複合索引 `idx_callrecord_allocation_time (allocation_id, started_at)` 正好涵蓋此查詢的 where 條件 → 與既有 token 配額查詢同等效能，無新索引。
- `Decimal` 全程：`cost_usd` 是 `Numeric`、上限欄也用 `Numeric`，比較不經 float（呼應「金額別用浮點」）。

**Alternatives considered**：
- 即時維護一個「本月累計」計數欄（避免每次聚合）→ 否決：YAGNI，多一個要同步的狀態 + 月初歸零的排程；既有 token 配額就是每次聚合、效能已驗可接受。
- 以 `aggregate_usage` 既有彙總服務算 → 否決：那是面向報表的多維彙總，preflight 熱路徑要的是單分配單值，獨立小函式更直接（對稱 `current_month_usage`）。

---

## R2：preflight 整合 + 新拒絕語意

**Decision**：在 `run_preflight` 既有 token 配額檢查**之後、同一段**加一道 cost 檢查：
```
if allocation.quota_cost_usd_per_month is not None:
    spent = await current_month_cost(session, allocation.id)
    if spent >= allocation.quota_cost_usd_per_month:
        return PreflightRejection("cost_quota_exceeded", "...本月花費上限...", 403, allocation)
```
新增 `CallOutcome.rejected_cost_quota_exceeded`（`Enum(native_enum=False)` 存 VARCHAR → **無 migration**，沿用既有列舉擴充慣例）；`proxy/router.py` 的 `_outcome_for_code` 加 `"cost_quota_exceeded": rejected_cost_quota_exceeded`。

**Rationale**：
- token 與 cost 兩道並列、任一超過即擋（FR-004 取較嚴者）；放在同一前置點 → 兩端點（chat/responses）+ registry 引擎共用的 preflight 一次涵蓋所有同步端點。
- 拒絕仍走既有 `record_call`（綁 allocation、可觀測）——沿用「拒絕路徑也要記、要綁 context」教訓。
- 新 outcome 而非複用 `rejected_quota_exceeded`：用量視圖能分辨「token 超額」vs「花費超額」（admin 診斷需要），且 VARCHAR enum 加值零 migration。

**Alternatives considered**：
- 複用 `rejected_quota_exceeded` 一個碼 → 否決：兩種上限的處置與訊息不同，分開可診斷（呼應「新事件優先映既有語意」的反向權衡——此處語意確實不同，值得新值）。
- 在每個端點各自檢查 → 否決：違反「單一前置管線」，必 drift。

---

## R3：realtime 連線中花費把關（連線中 cost re-check）

**Decision**：擴充階段 32 既有的旁路 watcher。目前 `_revocation_watch` 每 N 秒呼叫 `check_active(allocation_id)`（查 active 狀態）。改為週期同時核對 **committed 月花費 + 本連線進行中累計**：
```
over_cost = (await current_month_cost(allocation_id)) + session_running_cost(sess, price) >= cap
```
- `committed`：已落帳的本月花費（不含本連線——本連線尚未 disconnect 落帳）。
- `session_running_cost`：本連線目前累計 = `session_quantity(sess, price.unit) × price.per_unit`（沿用階段 32 既有 `session_quantity` + 落帳同一條 price lookup）。
- 任一原因（非 active **或** over_cost）→ 翻 `close_reason`（cost 用既有 `revoked` 語意或新增 `cost_exceeded`）、停止 relay → 既有「任何 close 路徑都落帳」確保已累計時長落帳。
- 連線建立時的 preflight 也已含 cost 檢查（R2）→ 一開始就超額的連線在建立時即被擋。

**Rationale**：
- 完全沿用既有 watcher 協程與週期/SLO（不另起機制，YAGNI + 原則 3「長連線不只建立時檢查一次」）。
- 容差「上限 + 一個 tick」與既有撤回延遲同語意（spec edge case 已接受）。
- running cost 用既有 `session_quantity`/price——零新計量邏輯。

**Alternatives considered**：
- 每筆 `input_audio_buffer.append` 都檢查花費 → 否決：耦合轉送熱路徑、頻率不可控（同階段 32 撤回的否決理由）。
- 只在連線建立時檢查 → 否決：長連線正是缺口最嚴重處（FR-005、原則 3）。
- cap 用 cost，但 watcher 要先把本連線「部分落帳」才能算 committed → 否決：複雜化落帳語意；改用「committed + in-flight running」兩段相加，落帳仍只在 disconnect 一次。

---

## R4：與自適應配額池（階段 3c）的隔離

**Decision**：**什麼都不用做**——`services/quota_pool.py` 的 `compute_rebalance` / `apply_rebalance` 只讀寫 `quota_tokens_per_month`（已 inspect 確認：`apply_rebalance` 的 `.values(quota_tokens_per_month=...)`、conservation 也只加總 token 欄）。新欄 `quota_cost_usd_per_month` 不在其讀寫範圍內，**天然不被再分配**（SC-005 直接成立）。

**Rationale**：花費上限與 token 池是兩個正交的治理軸（一個硬上限、一個守恆再分配）；不混疊符合「守住軸正交、別 overload」（原則 7）+ spec 明確排除。

**Alternatives considered**：把「花費」也做成可再分配的池（Σcost=T）→ 否決：YAGNI（無此需求）+ 兩套再分配邏輯互撞（spec 風險已標）。以一支整合測試固化「池跑完 cost 上限不變」即可。

---

## R5：未定價呼叫的誠實處置

**Decision**：未定價呼叫 `cost_usd` 為 NULL → `current_month_cost` 的 `coalesce(…,0)` 視為 0 → **不增加累計、不被花費上限擋**。不另做特別處理；在 admin 配額 UI/文件標明「花費上限只治理已定價用量」。

**Rationale**：延續「PriceList 是計費唯一真理」——未定價是 admin 該補價的設定問題，不該由配額層假裝它花了錢或無限。誠實標記（FR-006）。

**Alternatives considered**：未定價呼叫一律擋（保守）→ 否決：會把「admin 還沒設價」誤殺成「超額」，體感差且與計費語意不一致。把未定價當某固定估價擋 → 否決：憑空造價、不可稽核。

---

## 研究結論彙整（給 Phase 1 / tasks）

| 問題 | 結論 | 落地 |
|---|---|---|
| 累計花費來源 | `sum(cost_usd)` 月初起、Decimal、命中既有索引 | `services/quota.py` `current_month_cost` |
| preflight 整合 | token 後並列一道 cost 檢查、新 outcome（無 migration） | `proxy/preflight.py` + `router._outcome_for_code` + `CallOutcome` |
| realtime 連線中把關 | 擴充既有 watcher：committed + in-flight running ≥ cap → close + 落帳 | `proxy/realtime.py` |
| 自適應池隔離 | 無需改碼（池只動 token 欄）；測試固化 | `tests/integration/test_quota_pool_*` |
| 未定價 | NULL→0→不治理，誠實標記 | UI 文案 + 文件 |
| Migration | `0020` 純加 `allocations.quota_cost_usd_per_month`（nullable Numeric） | `alembic/versions/0020_cost_quota.py` |
