---
description: "Tasks for Phase 14 — admin visualization enhancement"
---

# 任務清單：Admin 視覺化強化

**輸入文件**：`/specs/024-admin-visualization/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/](./contracts/) / [quickstart.md](./quickstart.md)

**測試**：憲章 TDD 不可妥協 → **每個 US 後端先寫失敗測試（Red）才實作（Green）**；前端以 vitest
驗資料映射 + 空狀態。

**組織原則**：依使用者故事分組。後端聚合（US1/US2/US4 需要）集中在 Foundational 之後各 US 內。

## 格式

`- [ ] TaskID [P?] [Story?] 描述 (含絕對檔案路徑)`
- **[P]**：可並行（不同檔案、無未完成依賴）
- **[Story]**：US1–US5；Setup / Foundational / Polish 不加 Story 標

## 路徑慣例

- 後端：`src/ai_api/`；前端：`frontend/src/`；測試：`tests/`、`frontend/src/__tests__/`

---

## Phase 1：Setup（共享基礎）

- [X] T001 在 `frontend/package.json` 新增依賴 `recharts@^2.15`（React 19 相容），跑 `npm --prefix frontend install`，確認 lockfile 更新且 `npm --prefix frontend run build` 仍通過
- [X] T002 [P] 確認後端不需新依賴 / migration（核對 `pyproject.toml` 與 `alembic/versions/` 無新增）——純查詢層

---

## Phase 2：Foundational（阻斷性前置）

**⚠️ 沒做完任何 US 都不能開始。**

- [X] T003 在 `src/ai_api/services/usage.py` 將 `GroupBy = Literal["member", "allocation", "model", "tag"]` 擴充加入 `"provider"`（型別擴充，分支實作於 US2）
- [X] T004 [P] 新增 `frontend/src/components/ui/chart.tsx`：共用 `<Chart>` wrapper（封裝 recharts `ResponsiveContainer` + 統一主題色 + tooltip + 空狀態 placeholder），供所有圖表共用（避免「同一概念兩份必 drift」）
- [X] T005 [P] 新增 `frontend/src/components/time-range-select.tsx`：時段選擇器（本週/本月/本季/自訂），輸出 `{from, to}` ISO 區間（本地時區→UTC）；沿用既有 usage 頁的 date input + searchParams 模式

**Checkpoint**：型別 + 共用元件就緒，可平行進入 US1-US5。

---

## Phase 3：US1 — 首頁三圖（P1）🎯 MVP

**目標**：首頁加 daily spend bar / model donut / top allocations bar，警示維持最上方、≤3 圖。

**獨立驗收**：quickstart 情境 1、7。

### Tests First (Red)

- [X] T006 [US1] 新增 `tests/contract/test_usage_viz.py::test_platform_timeseries_sums_all_allocations`：seed 跨多分配多天呼叫，`GET /admin/usage/timeseries?bucket=day&from=&to=` 回每日 point = 該日**所有分配**之和
- [X] T007 [P] [US1] 同檔加 `test_platform_timeseries_admin_only`：未認證回 401/403
- [X] T008 [P] [US1] 同檔加 `test_platform_timeseries_invalid_range`：from≥to 回 400
- [X] T009 [US1] 跑 T006–T008 確認 **全 Red**

### Implementation (Green) — 後端

- [X] T010 [US1] 在 `src/ai_api/services/usage.py` 把 `usage_timeseries` 的 `allocation_id: str` 改為 `allocation_id: str | None = None`：None 時不加 allocation filter（平台級）；既有 per-allocation 呼叫不受影響
- [X] T011 [US1] 在 `src/ai_api/api/usage.py` 新增 `GET /usage/timeseries`（bucket/from/to）：`_validate_range`、呼叫平台級 `usage_timeseries`、回 `{from,to,bucket,points}`，schema 對齊 contract
- [X] T012 [US1] 跑 T006–T008 確認 **全 Green**

### Implementation (Green) — 前端

- [X] T013 [US1] 在 `frontend/src/routes/admin/home.tsx` 加 daily spend 長條圖（用 `<Chart>` + recharts BarChart）：query `/admin/usage/timeseries?bucket=day`；可切 token / 花費；hover 顯示當日明細
- [X] T014 [P] [US1] 同檔加 Spend by Model 環圈圖：query `/admin/usage?group_by=model`（既有），取 top 5 + 「其他」，點 slice 跳 `/admin/model/{slug}`
- [X] T015 [P] [US1] 同檔加 Top 5 allocations 長條圖：query `/admin/usage?group_by=allocation`（既有），top 5，點列跳 `/admin/observability/allocations`（或分配詳情）
- [X] T016 [US1] 在 `frontend/src/routes/admin/home.tsx` 確保佈局順序：quarantine/paused 警示卡 → 系統資訊/設定清單 → **圖表區（≤3 張）**；圖表在警示**之下**（FR-008）
- [X] T017 [P] [US1] 新增 `frontend/src/__tests__/home-charts.test.tsx`：vitest 驗 (a) 圖表數量 ≤3；(b) 警示卡 DOM 順序在圖表之前；(c) 空資料時圖表顯示空狀態
- [X] T018 [US1] 跑 `npm --prefix frontend run lint && typecheck && build` + T017 確認綠

---

## Phase 4：US2 — 用量頁 provider donut + heatmap（P2）

**目標**：用量頁加 provider 占比 donut + 24×7 heatmap。

**獨立驗收**：quickstart 情境 2、3、8。

### Tests First (Red)

- [X] T019 [US2] 在 `tests/contract/test_usage_viz.py` 加 `test_group_by_provider`：seed 跨 provider 的 model 呼叫（catalog 已標 provider），`GET /admin/usage?group_by=provider` 回每 provider 一列 = 該 provider 旗下 model 之和（JOIN model_catalog 正確）
- [X] T020 [P] [US2] 新增 `tests/integration/test_usage_viz_agg.py::test_heatmap_buckets_by_weekday_hour_utc8`：seed 集中在特定 weekday+hour（UTC+8）的呼叫，`GET /admin/usage/heatmap` 回對應格 value 高、分桶 UTC+8、≤168 格
- [X] T021 [P] [US2] 同檔加 `test_heatmap_admin_only`：未認證 401/403
- [X] T022 [US2] 跑 T019–T021 確認 **全 Red**

### Implementation (Green) — 後端

- [X] T023 [US2] 在 `src/ai_api/services/usage.py` 加 `group_by == "provider"` 分支：`JOIN model_catalog ON model_catalog.slug == CallRecord.model`、`GROUP BY model_catalog.provider`；獨立變數名 `provider_stmt`/`provider_rows`；回 `UsageItem`（group_key=provider）
- [X] T024 [US2] 在 `src/ai_api/services/usage.py` 新增 `HeatCell` dataclass + `usage_heatmap(db, *, from_, to_) -> list[HeatCell]`：dialect-aware 取 weekday+hour（以 UTC+8，呼叫 started_at + 8h）、`GROUP BY weekday, hour`
- [X] T025 [US2] 在 `src/ai_api/api/usage.py` 新增 `GET /usage/heatmap`：`_validate_range`、回 `{from,to,timezone:"UTC+8",cells}`，schema 對齊 contract；`group_by=provider` 隨既有 `/usage` 端點自動支援
- [X] T026 [US2] 跑 T019–T021 確認 **全 Green**

### Implementation (Green) — 前端

- [X] T027 [P] [US2] 在 `frontend/src/routes/admin/usage.tsx` 加 Provider 占比環圈圖（`<Chart>` + recharts PieChart）：query `/admin/usage?group_by=provider`
- [X] T028 [US2] 在 `frontend/src/routes/admin/usage.tsx` 加 24×7 heatmap：用 **CSS grid 7×24**（非 recharts），cell 顏色按 value ramp；軸標清楚（星期幾 × 小時，標注 UTC+8）；query `/admin/usage/heatmap`
- [X] T029 [US2] 跑前端 lint/typecheck/build 確認綠

---

## Phase 5：US3 — 統一時段選擇器（P2）

**目標**：首頁 + 用量頁掛上 `<TimeRangeSelect>`，切換一起更新所有圖表。

**獨立驗收**：quickstart 情境 9。

### Implementation

- [X] T030 [US3] 在 `frontend/src/routes/admin/home.tsx` 掛上 `<TimeRangeSelect>`（Phase 2 T005 建的），其 `{from,to}` 進各圖 query 的 queryKey；切換一起 refetch
- [X] T031 [P] [US3] 在 `frontend/src/routes/admin/usage.tsx` 同樣掛 `<TimeRangeSelect>`（與既有 date input 整合或取代）；切「本季」全頁圖表更新
- [X] T032 [P] [US3] 確保切換時段時各圖有載入指示（query.isLoading → spinner / skeleton），非空白閃爍
- [X] T033 [US3] 新增 `frontend/src/__tests__/time-range-select.test.tsx`：vitest 驗「本週/本月/本季」換算出正確 `{from,to}` 區間
- [X] T034 [US3] 跑前端 lint/typecheck/build + T033 確認綠

---

## Phase 6：US4 — 暫停/隔離原因顯眼化（P2）

**目標**：分配列徽章 hover + 解除頁顯示觸發原因（沿用既有稽核 details）。

**獨立驗收**：quickstart 情境 4、10。

### Tests First (Red)

- [X] T035 [US4] 在 `tests/contract/test_usage_viz.py` 加 `test_quarantine_reason_from_audit_details`：觸發 `allocation_quarantined`（details 含 last_hour_calls=1100/baseline=100/reason=ratio），`GET /admin/allocations/{id}/quarantine-reason` 回該 details + message 含「1100」「100」
- [X] T036 [P] [US4] 同檔加 `test_quarantine_reason_absent_details`：無 details 的舊事件 → message=「原因未記錄」、不報錯（FR-017）
- [X] T037 [P] [US4] 同檔加 `test_quarantine_reason_admin_only` + `test_quarantine_reason_404`（不存在 allocation）
- [X] T038 [US4] 跑 T035–T037 確認 **全 Red**

### Implementation (Green) — 後端

- [X] T039 [US4] 在 `src/ai_api/api/usage.py`（或 `api/allocations.py`）新增 `GET /allocations/{id}/quarantine-reason`：查該分配最近一次 `allocation_quarantined`/`allocation_paused` 稽核事件，從 `details` 取 reason/last_hour_calls/baseline_per_hour，回 `QuarantineReason`（缺 details → message「原因未記錄」）；404 if allocation 不存在
- [X] T040 [US4] 跑 T035–T037 確認 **全 Green**

### Implementation (Green) — 前端

- [X] T041 [US4] 在 `frontend/src/routes/admin/allocations.tsx` 隔離/暫停徽章加 hover（tooltip 或 popover）：按需 query `/admin/allocations/{id}/quarantine-reason`，顯示「過去 1 小時 N calls，baseline X/hr，超出 M×」；暫停 vs 隔離區分文案
- [X] T042 [US4] 在解除隔離流程/頁面顯示同觸發數據（不必查稽核紀錄）
- [X] T043 [US4] 跑前端 lint/typecheck/build 確認綠

---

## Phase 7：US5 — Top 5 tags by spend 卡（P3）

**目標**：首頁加 Top 5 tags 卡（延伸階段 15 tag 聚合）。

**獨立驗收**：quickstart 情境 11。

### Implementation

- [X] T044 [US5] 在 `frontend/src/routes/admin/home.tsx` 加 Top 5 tags by spend 卡：query `/admin/usage?group_by=tag`（階段 15 既有），取 top 5 by cost；點 tag 跳 `/admin/usage?group_by=tag`（用量頁 tag 視圖）
- [X] T045 [US5] 確認此卡與首頁 ≤3 圖約束不衝突（卡片非「圖表」、放圖表區之後）；跑前端 lint/build 確認綠

---

## Phase 8：Polish 與跨領域

- [X] T046 [P] 新增 `tests/contract/test_usage_viz.py::test_viz_endpoints_admin_only`（彙整 timeseries/heatmap/quarantine-reason 的非 admin → 401/403，若各 US 已覆蓋則此為彙整確認）
- [X] T047 跑 `uv run pytest tests/` 全套件確認既有 usage 測試零退化（SC-007）
- [X] T048 跑 `uv run ruff check . && uv run mypy src/` 零警告（**`ruff check .` 全 repo**）
- [X] T049 跑 `npm --prefix frontend run lint && typecheck && build`；確認 recharts 為唯一新圖表依賴、bundle gzip 增量 < 150KB（比對 build 輸出）
- [X] T050 [P] 新增 `knowledge/design/admin-visualization.md`：摘要 research 8 條決策（recharts 選型、heatmap 用 grid、平台時序、provider JOIN、隔離原因 surface、佈局不淹警示）；連結回 spec/plan
- [X] T051 [P] 更新 `knowledge/vision.md` 階段 14 條目：完成日期填入後改 ✅、列實際交付、連結 history；roadmap 全部完成的狀態更新
- [X] T052 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 14：Admin 視覺化強化」詳情
- [X] T053 端到端煙霧（本機）：跑 quickstart 情境 7–13（首頁三圖 + 警示優先 + provider/heatmap + 時段切換 + 隔離原因 + tag 卡 + 空狀態 + bundle）
- [X] T054 commit + push + 等 CI（**push 前先 `ruff check .` + 前端 lint/build**）；CI 綠後 helm upgrade 至 ai-ccsh；live 跑 quickstart 情境 7 + 10 真機驗證
- [X] T055 收尾：vision 階段 14 改 ✅、history 補上、確認 roadmap **全部承諾階段完成**狀態一致

---

## 依賴與順序

```text
Phase 1 (Setup: recharts + 確認無後端依賴)
   ↓
Phase 2 (Foundational: GroupBy 加 provider 型別 + <Chart> wrapper + <TimeRangeSelect>)
   ↓
Phase 3 (US1: 首頁三圖) ─── MVP，最大價值
   │
Phase 4 (US2: provider donut + heatmap) ─── 依賴 <Chart>；後端聚合獨立
   │
Phase 5 (US3: 時段選擇器) ─── 依賴 US1/US2 的圖存在；可在圖完成後接上
   │
Phase 6 (US4: 隔離原因) ─── 後端端點獨立、前端依 allocations 頁；可與 US1-US3 平行
   │
Phase 7 (US5: tag 卡) ─── 依賴階段 15（已完成）+ <Chart>
   ↓
Phase 8 (Polish: 隔離測試彙整 + 文件 + 部署)
```

**MVP 建議**：US1（首頁三圖 + 平台時序）即可上線首個價值——admin 一眼看用量節奏。US2-US5 陸續增益。

**[P] 並行機會**：
- Phase 2：T004/T005 [P]
- Phase 3：T007/T008、T014/T015、T017 [P]
- Phase 4：T020/T021、T027 [P]
- Phase 6：T036/T037 [P]
- Phase 8：T050/T051/T052 [P]

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 2 | 0 |
| 2 Foundational | 3 | 0 |
| 3 US1（P1，MVP） | 13 | 4 |
| 4 US2（P2） | 11 | 3 |
| 5 US3（P2） | 5 | 1 |
| 6 US4（P2） | 9 | 4 |
| 7 US5（P3） | 2 | 0 |
| 8 Polish | 10 | 1 |
| **總計** | **55** | **13** |

---

## 格式檢核

- ✅ 所有任務 `- [ ] T###` 開頭、含 ID、描述、絕對檔案路徑
- ✅ Setup / Foundational / Polish 無 Story 標；US1–US5 任務含 `[US#]` 標
- ✅ 可並行任務標 `[P]`
- ✅ 後端 US 階段：Tests First → Red → Implementation → Green；前端以 vitest + 煙霧驗

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
