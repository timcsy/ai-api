# Research：成員自助用量視覺化

spec 無殘留 NEEDS CLARIFICATION（取向已於 specify 定案）。以下為實作前技術決策。

---

## R1：各 model 占比 donut — 複用既有 `/me/usage?group_by=model`，零新後端

- **Decision**：donut 的資料直接打既有 `GET /me/usage?group_by=model`。
- **Rationale**：該端點已存在、已 member-scoped（`current_member`，範圍取自 session，**無參數可查他人**），
  且回傳含各 model 的 `total_cost_usd`／`total_tokens`——donut 所需資料現成。零新後端、零新洩漏面。
- **Alternatives**：新做一個 member donut 端點 → 重複既有能力，違反 YAGNI。→ 否決。

## R2：每日趨勢 — `usage_timeseries` 加 `member_id` 過濾 + 新 `GET /me/usage/timeseries`

- **Decision**：在 `services/usage.py` 的 `usage_timeseries` 加一個 `member_id: str | None = None` 參數：
  非 None 時 `JOIN Allocation ON Allocation.id == CallRecord.allocation_id` 並過濾 `Allocation.member_id ==
  member_id`（既有 `allocation_id` 與 `None`＝平台級行為不變）。`api/me.py` 新增
  `GET /me/usage/timeseries`，`member_id` 一律取自 `current_member`、`bucket=day`、沿用 `_validate_range`。
- **Rationale**：最小擴充——一個過濾參數即達成 member-scope，不新增第二個時序函式（避免「同一概念兩份必
  drift」）。owner-scoping 與既有 `/me/usage`、`/me/allocations/{id}/calls` 同模式（範圍取自 session）。
- **Alternatives**：
  - 前端逐一打每張憑證的 `/admin/.../usage-timeseries` 再加總 → admin-only 端點不可給成員、且 N 次往返。→ 否決。
  - 新增獨立 `member_usage_timeseries` 函式 → 與既有時序邏輯重複、易 drift。→ 否決。

## R3：Owner-scoping 是硬約束 — 範圍只從 session 取，永不吃 client id

- **Decision**：`/me/usage/timeseries` **沒有** member/allocation 參數；範圍 100% 來自 `current_member`。
  contract/integration 測試明確驗「成員只拿得到自己的」「無參數能查他人」。
- **Rationale**：對應 spec FR-002（鐵律）+ 原則 1 憑證隔離 / 2 可追蹤性。沿用既有經驗教訓「把 admin 操作
  下放給 member：同一 service + 嚴格擁有者檢查」——服務層 actor-agnostic（`member_id` 參數），端點層用
  session 把關身分。
- **Alternatives**：以 query 參數帶 member_id（admin 風格）→ 對成員端是資料外洩風險。→ 嚴格否決。

## R4：前端 — 新 `MemberUsageCharts` 元件，複用既有圖表基建

- **Decision**：新增 `components/member-usage-charts.tsx`：每日趨勢 BarChart（`/me/usage/timeseries`，
  token/花費可切）+ 各 model donut（`/me/usage?group_by=model`）。複用 `<Chart>` wrapper、`CHART_COLORS`、
  `<TimeRangeSelect>`、`rangeToIso`。接進 `routes/dashboard.tsx` 的用量區（usage-summary 旁/併入）。
- **Rationale**：階段 14/16 已備齊圖表基建；複用即可、零新依賴。query key 用獨立命名空間（`["me","viz",...]`）
  避免與 admin（`["admin","viz",...]`）撞——呼應「queryKey 是快取身分證，回傳形狀不同 → key 必須不同」。
- **Alternatives**：把 admin 的 `DashboardCharts` 直接搬給成員 → 它打 admin 端點、含跨成員聚合，絕不可。→ 否決。

## R5：RWD — 沿用階段 16 規範，避免重蹈 grid 溢出

- **Decision**：圖表容器一律 **base `grid-cols-1`**（`grid grid-cols-1 gap-6 md:grid-cols-2`）、`<Chart>`
  已有 `w-full min-w-0`；手機不溢出。
- **Rationale**：直接套用剛 distill 的教訓「Tailwind `grid` 沒給 base `grid-cols-1` → recharts 溢出」，
  一次做對、不重犯。

## R6：測試分工（沿用階段 16 之 jsdom 可測邊界）

- **Decision**：
  - **後端（先 Red）**：contract `/me/usage/timeseries`（成員自己當日和、未認證 401/403、from≥to 400）；
    integration（Postgres）成員 A 的時序**不含** B 的呼叫（隔離）。
  - **前端 vitest**：MemberUsageCharts 資料映射（趨勢/donut）、空狀態。
  - **純視覺**：360px 手機不溢出 → quickstart 手動清單。
- **Rationale**：誠實面對 jsdom 無版面引擎；有資料/隔離行為先測，視覺以手動清單收尾。

---

## 小結

- 零新依賴、無新表/migration、桌機 + admin 既有圖零回歸。
- 唯一新後端：`usage_timeseries` 加 `member_id` 過濾 + `GET /me/usage/timeseries`。
- donut 複用既有 `/me/usage?group_by=model`。
- 隔離（owner-scoping）是先寫的測試重點。
