# Phase 0 Research: 成員自助用量總覽

## R1: 如何把 admin 聚合 scope 到單一成員

**Decision**: 在 `aggregate_usage` 加一個可選參數 `member_id: str | None = None`；非空時於 `base_filters` 加入 `Allocation.member_id == member_id`。

**Rationale**:
- `aggregate_usage` 三個分支（`member` / `allocation` / `model`）**都已 join `Allocation`**（`Allocation.id == CallRecord.allocation_id`），故在 base_filters 加 `Allocation.member_id` 對三分支皆生效，零結構改動。
- `group_by="member" + member_id=X` 會回**唯一一列**＝該成員的整體摘要，直接當 summary 用，無需另寫聚合（YAGNI、避免「同概念兩份」drift）。
- 不需 schema 變更、不需新表。

**Alternatives considered**:
- 另寫 `aggregate_member_usage()` 平行函式 — 否決，違反 YAGNI 且會與 admin 聚合 drift（experience 教訓）。
- 在 Python 端把 admin 結果過濾出該成員 — 否決，需把全體資料拉回再篩，效能與隔離都差。

## R2: summary 與 breakdown 的端點形狀

**Decision**: `GET /me/usage?from=&to=&group_by=`（`group_by` 可選，值 `model` | `allocation`）回：

```jsonc
{
  "from": "...", "to": "...",
  "summary": { total_tokens, prompt_tokens, completion_tokens, total_cost_usd, call_count, has_unpriced },
  "breakdown": [ { group_key, display_name, total_tokens, prompt_tokens, completion_tokens, total_cost_usd, call_count } ]  // 僅當帶 group_by
}
```

- `summary` 由 `aggregate_usage(group_by="member", member_id=me)` 的單列產生（無呼叫 → 全 0）。
- `breakdown` 由 `aggregate_usage(group_by=<model|allocation>, member_id=me)`。
- **不開放 `group_by="member"` 給此端點**（member-scope 下對自己分組無意義）。

**Rationale**: 一個端點同時服務 P1（只要 summary）與 P2（帶 group_by 取 breakdown），前端按需取用；形狀對齊既有 admin `/admin/usage` 的 `{from,to,items}` 風格但聚焦單人。

**Alternatives considered**: 拆成 `/me/usage/summary` + `/me/usage/breakdown` 兩端點 — 否決，徒增端點數，summary 幾乎總是要、breakdown 選配，合一更簡。

## R3: 嚴格資料隔離（最高風險）

**Decision**: `member_id` **一律取自 `current_member`（session）**，端點**不暴露**任何可指定他人 member 的 query 參數。

**Rationale**: 對齊 FR-002 / SC-003 與原則「可追蹤性」不等於可越權。範圍由身份決定。
**測試**：建立成員 A、B 各自的呼叫，斷言 A 的 `/me/usage` 完全不含 B 的數字（且無任何參數能讓 A 取得 B）。

## R4: 「未定價低估」提示（FR-006）

**Decision**: summary 加布林 `has_unpriced`：該成員、該區間內存在「成功、`total_tokens > 0` 但 `cost_usd` 為 NULL 或 0」的呼叫即為 `true`。以一支輕量 count 查詢（同 member + 區間 filter）取得，不污染主聚合。

**Rationale**: `cost_usd` 是呼叫當時記錄的成本；當時 model 無價目則為 0/NULL。直接顯示加總會讓成員以為免費。`has_unpriced=true` 時 UI 標「含未定價項目，花費為低估」（SC-004）。
**Alternatives considered**: 在主聚合多拉一個 `SUM(CASE WHEN ...)` 欄位 — 可行但讓 `UsageItem` 變胖且只 summary 需要；獨立 count 更乾淨。

## R5: 時間區間預設與驗證

**Decision**: `from` / `to` 可選；未給時預設 `from = 本月 UTC 月初`、`to = now(UTC)`。沿用 admin 的範圍驗證（`from < to`、最大跨度上限）。前端提供「本月」「近 7 天」「近 30 天」快捷。

**Rationale**: 月度以 UTC 月初錨點與 3c 配額池一致；快捷涵蓋常見需求。
**借鏡 experience**：
- 「datetime 一律 tz-aware」→ 全程 `datetime.now(UTC)`。
- 「httpx 測試 URL 帶 ISO datetime 必須先 quote」→ 測試走 `client.get(..., params=...)`。

## R6: 配額視角（P3）

**Decision**: 「本月已用 / 配額」沿用既有資料——分配的 `quota_tokens_per_month`（含 3c 池 rebalance 後的當期值）+ 本月該分配 token 用量（`aggregate_usage(group_by="allocation", member_id=me)` 的對應列）。無限額分配（quota 為 NULL）顯示為無上限。

**Rationale**: 不引入新概念，純組合既有欄位；與分配詳情頁既有「配額與價格」卡口徑一致。

## R7: 多分支 select 型別（實作護欄）

**Decision**: 在 `aggregate_usage` 加 `member_id` 時，沿用既有「各分支獨立變數名」慣例，不硬共用 `stmt`/`rows`。

**Rationale**: experience 教訓「SQLAlchemy 多分支 select 的型別衝突」正出自本檔（`usage.py`）；加 filter 時保持同樣紀律，避免 mypy 衝突。

## 測試策略（TDD）

| 測試 | 類型 | 對應 |
|------|------|------|
| `aggregate_usage(member_id=A)` 只含 A 的呼叫；A/B 互不污染 | integration | FR-002, SC-003 |
| 三種 group_by + member_id 各分支正確過濾 | integration | FR-003 |
| 只計成功呼叫（失敗不計） | integration | Edge, FR-005 |
| `/me/usage` 回 summary，數字 = 該成員所有呼叫加總 | integration | FR-001, SC-002 |
| `/me/usage?group_by=model` breakdown 各列加總 = summary | integration | FR-003, SC-002 |
| 未給區間 → 預設本月；給區間 → 依區間重算 | integration | FR-004 |
| 有未定價呼叫 → `has_unpriced=true` | integration | FR-006, SC-004 |
| 成員 A 無法取得 B 的用量（無參數可越權） | integration | FR-002, SC-003 |
| 未登入 → 401 | integration | 授權 |
| 既有 `/admin/usage` 與分配明細零退化 | integration | FR-008, SC-005 |
| 儀表板渲染摘要（總 token / 花費 / 次數）+ 未定價提示 | frontend RTL | FR-001/006, SC-001 |

無 NEEDS CLARIFICATION 待解。
