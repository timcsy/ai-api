---
description: "Tasks for 階段 17 — 成員自助用量視覺化（成員端圖表）"
---

# 任務清單：成員自助用量視覺化（成員端圖表）

**輸入文件**：`/specs/026-member-usage-charts/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/me-usage-timeseries.openapi.yaml](./contracts/me-usage-timeseries.openapi.yaml) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：後端 **owner-isolation + 時序正確性**先寫失敗 contract/integration（Red）再實作（Green）；
前端圖表資料映射 / 空狀態以 vitest；純視覺（360px 不溢出）以 [quickstart.md](./quickstart.md) 手動清單。

**鐵律**：資料隔離（FR-002）——成員只看自己，範圍取自 session，**端點無參數可查他人**，**永不含跨成員聚合**。

**組織原則**：依 US 分組（US1 每日趨勢〔含唯一新後端〕→ US2 model donut〔複用既有端點〕→ US3 時段選擇器）。
**零新依賴、無新表、無 migration。**

## 路徑慣例

- 後端：`src/ai_api/`；前端：`frontend/src/`；測試：`tests/`、`frontend/src/__tests__/`

---

## Phase 1：Setup

- [X] T001 確認基準綠（實作前對照）：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、
      `npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**不新增任何依賴**

---

## Phase 2：Foundational

> 本功能無跨 US 的阻斷性前置（donut 複用既有端點、時序服務 US1 內擴充、前端元件於 US1 建殼）。直接進 US1。

---

## Phase 3：US1 — 每日用量趨勢（P1）🎯 MVP

**目標**：成員 dashboard 出現「每日用量/花費」bar（自己跨所有憑證加總），含 token/花費切換；嚴格只看自己。

**獨立驗收**：quickstart 後端「時序正確 / 隔離」+ 前端 vitest；契約 `contracts/me-usage-timeseries.openapi.yaml`。

### Tests First (Red)

- [X] T002 [US1] 在 `tests/contract/test_me_usage.py` 加 `test_my_timeseries_sums_own_allocations`：以成員登入，seed 該成員跨多憑證多天呼叫，`GET /me/usage/timeseries?from=&to=` 回每日 point = 該成員**所有自己憑證**當日和
- [X] T003 [P] [US1] 同檔加 `test_my_timeseries_unauthenticated_401` 與 `test_my_timeseries_invalid_range_400`（from≥to）
- [X] T004 [US1] 新增 `tests/integration/test_me_usage_isolation.py::test_my_timeseries_excludes_other_member`（Postgres）：seed 成員 A 與 B 的呼叫；以 A 登入打 `/me/usage/timeseries` → 結果**不含** B 的任何呼叫；確認端點**無參數**可指定他人
- [X] T005 [US1] 跑 T002–T004 確認 **全 Red**

### Implementation (Green) — 後端

- [X] T006 [US1] 在 `src/ai_api/services/usage.py` 的 `usage_timeseries` 加 `member_id: str | None = None`：非 None 時 `JOIN Allocation ON Allocation.id == CallRecord.allocation_id` 並過濾 `Allocation.member_id == member_id`；既有 `allocation_id` 與 `None`（平台級）行為不變
- [X] T007 [US1] 在 `src/ai_api/api/me.py` 新增 `GET /me/usage/timeseries`（`current_member`、`_validate_range`、bucket=day、from 預設當月初／to 預設 now）：呼叫 `usage_timeseries(member_id=member.id, bucket="day", ...)`，回 `{from,to,bucket,points}`，schema 對齊 contract；**範圍只取自 session，無 member/allocation 參數**
- [X] T008 [US1] 跑 T002–T004 確認 **全 Green**

### Implementation (Green) — 前端

- [X] T009 [US1] 新增 `frontend/src/components/member-usage-charts.tsx`：`MemberUsageCharts({range})`，每日趨勢 BarChart（query `/me/usage/timeseries`，複用 `<Chart>`/`CHART_COLORS`，token/花費可切）；query key 用 `["me","viz",...]` 命名空間；容器 base `grid-cols-1`（沿用階段 16 RWD）
- [X] T010 [US1] 在 `frontend/src/routes/dashboard.tsx` 用量區（`<UsageSummary/>` 旁）接上 `<MemberUsageCharts>`（先給預設區間，US3 再掛時段選擇器）
- [X] T011 [P] [US1] 新增 `frontend/src/__tests__/member-usage-charts.test.tsx`：vitest 驗每日 bar 資料映射 + 空資料（新成員）顯示空狀態
- [X] T012 [US1] 跑 `npm --prefix frontend run lint && typecheck && build` + T011 確認綠

---

## Phase 4：US2 — 各 model 花費占比 donut（P2）

**目標**：成員看到自己各 model 花費 donut（複用既有 `/me/usage?group_by=model`，零新後端）。

**獨立驗收**：quickstart 一致性 + 前端 vitest。

- [X] T013 [US2] 在 `frontend/src/components/member-usage-charts.tsx` 加各 model 花費 donut（query `/me/usage?group_by=model`，PieChart + `CHART_COLORS`，top N + 其他）；與趨勢圖並排（手機 `grid-cols-1`，桌機 `md:grid-cols-2`）
- [X] T014 [P] [US2] 在 `frontend/src/__tests__/member-usage-charts.test.tsx` 加 donut 資料映射 + 空狀態（無計費用量）斷言
- [X] T015 [US2] 跑前端 lint/typecheck/build + 測試確認綠；確認 donut 各 model 和與 `/me/usage` 數字一致（手動核對一次）

---

## Phase 5：US3 — 時段選擇器（P3）

**目標**：dashboard 用量區掛 `<TimeRangeSelect>`，切換時兩圖一起更新、有載入指示。

**獨立驗收**：quickstart 切時段更新 + 載入指示。

- [X] T016 [US3] 在 `frontend/src/routes/dashboard.tsx` 用量區掛 `<TimeRangeSelect>`（沿用既有元件），其 `{from,to}` 經 `rangeToIso` 進 `<MemberUsageCharts>` 各 query 的 queryKey；切換一起 refetch
- [X] T017 [US3] 在 `frontend/src/components/member-usage-charts.tsx` 確保切換時段時兩圖有載入指示（`<Chart isLoading>` / skeleton），非空白閃爍
- [X] T018 [US3] 跑前端 lint/typecheck/build + 既有測試確認綠

---

## Phase 6：Polish 與跨領域

- [X] T019 跑 `uv run pytest tests/` 全套件確認零回歸（既有 usage / me 測試不退步，SC-006）
- [X] T020 跑 `uv run ruff check . && uv run mypy src/` 零警告（`ruff check .` 全 repo）
- [X] T021 跑 `npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**無新依賴**、bundle 無新增第三方
- [~] T022 （待你手機親驗）[P] 360px 手機手動驗收（一般成員身分）：dashboard 用量區兩圖不溢出、切時段一起更新、桌機目視正常（quickstart 手機段，SC-005）
- [X] T023 [P] admin 零回歸抽查：admin 首頁/用量頁既有圖表與行為不變（SC-006）；確認成員端**未出現**任何跨成員聚合（provider/heatmap/Top 榜）
- [X] T024 [P] 更新 `knowledge/vision.md`：新增階段 17 條目（成員端用量視覺化）標 ✅、列實際交付、連結 history；roadmap/狀態同步
- [X] T025 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 17：成員自助用量視覺化」詳情（含 owner-scoping 與複用既有端點）
- [ ] T026 commit + push + 開 PR；push 前先 `ruff check .` + 前端 lint/build；等 CI（test/frontend/image build）全綠後 squash merge 到 main
- [ ] T027 main image build 綠後 `helm upgrade ai-api deploy/helm/ai-api -n ai-ccsh --reuse-values --set image.tag=sha-<main> --set frontend.image.tag=sha-<main> --set storedResponseCleanup.enabled=true --set storedResponseCleanup.schedule="0 3 * * *"`；rollout 後以**一般成員**在 live（ai-ccsh.tew.tw）手機抽查兩圖
- [ ] T028 收尾：vision 階段 17 ✅、history 補上、roadmap 狀態一致；標記 tasks 全完成

---

## 依賴與順序

```text
Phase 1 (Setup: 基準綠)
   ↓
Phase 3 (US1: 每日趨勢) ─── MVP；含唯一新後端（usage_timeseries +member_id、/me/usage/timeseries）+ TDD 隔離
   │
Phase 4 (US2: model donut) ─── 複用既有 /me/usage?group_by=model，零新後端；依 US1 的 MemberUsageCharts 殼
   │
Phase 5 (US3: 時段選擇器) ─── 依 US1/US2 兩圖存在
   ↓
Phase 6 (Polish: 全測/lint/mypy/build + 360px 手動 + admin 零回歸 + 文件 + 部署)
```

**US 獨立性**：US1 可獨立交付（單張趨勢即有價值）；US2 加 donut；US3 加時段。US1 是唯一含後端者。

**MVP 建議**：US1（每日趨勢 + member-scoped 端點 + 隔離測試）即可上線首個價值。

**[P] 並行機會**：
- US1：T003、T011 [P]
- US2：T014 [P]
- Polish：T022/T023/T024/T025 [P]

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 3 US1（P1，MVP） | 11 | 4 |
| 4 US2（P2） | 3 | 1 |
| 5 US3（P3） | 3 | 0 |
| 6 Polish | 10 | 0 |
| **總計** | **28** | **5** |

---

## 格式檢核

- ✅ 所有任務 `- [ ] T###` 開頭、含 ID、描述、檔案路徑
- ✅ Setup / Polish 無 Story 標；US1–US3 含 `[US#]` 標
- ✅ 可並行任務標 `[P]`
- ✅ TDD：US1 後端 Tests First → Red（含 owner-isolation）→ 實作 → Green；前端 vitest + 360px 手動

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
