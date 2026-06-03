# Phase 0：研究與技術抉擇

格式：**Decision / Rationale / Alternatives**。

---

## R1：圖表 lib 選型

**Decision**：**recharts**（`recharts@^2.15`，React 19 相容），配一個專案內 `<Chart>` wrapper。

**Rationale**：
- React 19 相容（recharts 2.15+ 正式支援 React 19）；宣告式 component API 與既有 shadcn/React 風格一致
- 涵蓋本階段所需全部圖型：bar（daily spend / top allocations）、pie/donut（model / provider）、
  heatmap 可用 recharts 的 grid + cell 或自繪 SVG（見 R4）
- 社群大、文件足；shadcn 官方 charts 即 recharts 包裝，未來可平滑升級
- bundle：recharts 約 gzip 90–110KB，符合 SC-003 的 <150KB 預算

**Alternatives considered**：
- **shadcn charts（recharts wrapper）**：等於 recharts + 一層；可後續採用，但先用裸 recharts +
  自寫薄 wrapper 控制範圍
- **visx / nivo / chart.js**：visx 太低階（要自己組）、nivo bundle 大、chart.js 非 React-native
- **自繪 SVG**：bar/pie 自繪可行但 tooltip/動畫/RWD 全要自造，不划算

---

## R2：平台級每日時序

**Decision**：把既有 `usage_timeseries(allocation_id, ...)` 的 `allocation_id` 改為 **optional**——
None 時不加 allocation filter，即平台級聚合。新增端點 `GET /admin/usage/timeseries`（無 allocation）。

**Rationale**：
- 既有 `usage_timeseries` 已有 dialect-aware date truncation（PG `date_trunc` / SQLite `strftime`）
  與分桶邏輯——只差一個 allocation filter。改 optional 最省、不重寫。
- 與既有 per-allocation 端點 `GET /admin/allocations/{id}/usage-timeseries` 並存，共用 service。

**Alternatives considered**：
- **另寫 `platform_timeseries`**：重複既有 truncation 邏輯（違反「兩份必 drift」lesson）
- **前端對 model 維度自己加總成時序**：前端重運算 + 拿不到日粒度，違反 FR-002

---

## R3：provider 維度

**Decision**：`aggregate_usage` 加 `group_by="provider"` 分支——`JOIN model_catalog ON
CallRecord.model = model_catalog.slug`，`GROUP BY model_catalog.provider`。

**Rationale**：
- provider 不是 CallRecord 的欄位；model→provider 的對應在 `model_catalog.provider`（已有 index）
- 與既有 model 分支同構，沿用 `base_filters`、回 `UsageItem`（group_key=provider）
- 用獨立變數名 `provider_stmt`/`provider_rows`（多分支型別衝突 lesson）

**邊界**：catalog 沒收錄的 model（理論上不該有，因 catalog gate）→ JOIN 不到 → 該呼叫不計入
provider 聚合。可接受（這類 orphan 呼叫極罕見；若要可加 LEFT JOIN + "(unknown)" 分組，但 YAGNI）。

**Alternatives considered**：
- **CallRecord 加 provider 欄位快照**：schema 變更 + 每 call 寫；過度，catalog JOIN 即可
- **前端用 model→provider mapping 自己分組**：前端要拿 catalog、重運算，違反 FR-002

---

## R4：24 小時 × 7 天 heatmap 聚合

**Decision**：後端新增 `usage_heatmap(from_, to_) -> list[HeatCell]`，回 `(weekday, hour, value)`
格點。SQL 用 dialect-aware 取 weekday + hour（PG `extract(dow/hour)`、SQLite `strftime('%w','%H')`），
`GROUP BY weekday, hour`。前端用 recharts ScatterChart（x=hour, y=weekday, z=value 控制顏色）或
自繪 7×24 grid（cell 顏色按 value）。

**Rationale**：
- 聚合在後端（FR-002）；回 ≤ 168 格點（7×24），資料量小
- 前端 heatmap：recharts 無原生 heatmap，但 7×24 格用 CSS grid + 顏色 ramp 自繪最簡單清楚
  （非用 recharts 硬湊）——這是「選對工具」，heatmap 用 div grid 比硬塞 recharts 更可讀
- 時區：以 UTC 分桶（與既有時序一致）；UI 標注「UTC」或加 +8 偏移（與既有 email 一致用 UTC+8 較友善）
  → 決定用 **UTC+8 分桶**（對台灣 admin 直覺，與通知 email 一致）

**Alternatives considered**：
- **recharts ScatterChart 當 heatmap**：可行但顏色/格線控制較繞；CSS grid 更直觀
- **前端自己分桶**：違反 FR-002

---

## R5：隔離/暫停原因 surface

**Decision**：新增 `GET /admin/allocations/{id}/quarantine-reason`——查該分配**最近一次**
`allocation_quarantined` 稽核事件的 `details`（last_hour_calls / baseline_per_hour / reason），回給前端。
暫停（手動）則回對應 `allocation_paused` 事件或標示「手動暫停」。

**Rationale**：
- 資料**已存在**於稽核 `details`（anomaly detector 寫入）——只差一個查詢端點暴露給前端
- 前端徽章 hover / 解除頁呼叫此端點顯示「1 小時 1100 calls，baseline 100/hr，11×」
- 缺 details（舊資料）→ 回「原因未記錄」（FR-017）

**Alternatives considered**：
- **把 reason 塞進既有 `/admin/allocations` 列表回應**：每筆都查最近稽核事件 → N+1 或複雜 JOIN；
  獨立端點按需查（hover 時才打）更輕
- **前端直接查稽核 API 過濾**：前端要懂稽核 schema + 過濾邏輯，耦合過深

---

## R6：統一時段選擇器

**Decision**：新增 `<TimeRangeSelect>` 元件，輸出 `{from, to}`；預設選項「本週/本月/本季/自訂」
換算成 ISO datetime 區間（本地時區→UTC）。各頁的圖表 query 以此 `{from, to}` 為 queryKey 一部分，
切換即一起 refetch。

**Rationale**：
- 沿用既有 usage 頁的 date input + searchParams 模式；抽成共用元件供首頁與用量頁共用
  （「同一概念兩份必 drift」→ 抽元件）
- 區間驗證沿用既有後端規則（from<to、≤90 天）

**Alternatives considered**：
- **每頁各寫一套時段控制**：必 drift；抽共用
- **全域 context 存時段**：跨頁共享非需求（各頁獨立看不同區間更合理）；用 per-page searchParams

---

## R7：首頁圖表佈局與「不淹沒警示」

**Decision**：首頁順序固定為 (1) 既有 quarantine/paused 警示卡 → (2) 既有系統資訊/設定清單 →
(3) **本階段新增圖表區（≤3 張）** → (4) Top 5 tags 卡。圖表在警示**之下**。

**Rationale**：
- FR-008 硬約束：警示永遠最顯眼。圖表是「日常洞察」，警示是「需立即處理」——位階分明
- ≤3 張圖（FR-007）避免捲動疲勞與視覺超載

**Alternatives considered**：
- **圖表放最上方搶眼**：違反 FR-008，會讓 admin 漏看隔離警示
- **首頁塞滿圖**：違反 FR-007、稀釋差異化（vision 明確排除）

---

## R8：bundle 體積控制

**Decision**：recharts 直接 import（不 lazy-load）；若 build 警告超標再評估 route-level code-split。

**Rationale**：
- recharts gzip ~100KB，符合 SC-003 <150KB 預算；admin 頁面非極致效能敏感
- 既有 build 已有 >500KB 警告（非錯誤）；新增 recharts 不改變「能 build」的事實
- 先不過早 lazy-load（YAGNI）；實測 bundle 若顯著惡化再 split

**Alternatives considered**：
- **lazy-load 所有圖表 route**：增複雜度；先量測再決定
- **改用更小的圖表 lib**：見 R1，recharts 的相容性與完整度勝過省那幾十 KB

---

## 研究結論

所有技術未知收斂，無 NEEDS CLARIFICATION。可進入 Phase 1。
關鍵：3 個後端聚合（平台時序 optional allocation、provider JOIN catalog、heatmap）+ 1 個隔離原因
端點；前端 recharts + 共用 wrapper + 時段選擇器 + heatmap 用 CSS grid（非硬塞 recharts）。
