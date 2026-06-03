# 實作計畫：Admin 視覺化強化

**Branch**: `024-admin-visualization` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/024-admin-visualization/spec.md`

## 摘要

前端為主的視覺化強化：導入 **recharts**（平台第一個圖表 lib）+ 一個共用 `<Chart>` wrapper；
首頁加 3 張決策圖（daily spend bar / model donut / top allocations bar）+ Top 5 tags 卡；
用量頁加 provider donut + 24×7 heatmap；全頁統一時段選擇器；分配列/解除頁 surface 隔離/暫停
觸發原因。後端新增 3 個聚合（平台級 daily 時序、provider 維度、hour×weekday heatmap）+ 既有
隔離 `details` 經端點暴露給前端。**無新表、無 migration。**

## 技術脈絡

**Language/Version**: TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端少量聚合）
**Primary Dependencies**:
- 前端既有：TanStack Query、shadcn/ui、react-router
- 前端**新增**：`recharts`（React 19 相容；唯一新 runtime 依賴，FR-001/SC-003）
- 後端既有：FastAPI、SQLAlchemy 2.x async（無新增）
**Storage**: PostgreSQL / SQLite；**不新增表、不新增 migration**——全部查詢層聚合
**Testing**: pytest（後端聚合 contract）+ vitest（前端，既有）
**Target Platform**: 既有 K8s 部署，無新元件
**Project Type**: Web application（frontend + backend，既有）
**Performance Goals**:
- 聚合在後端、前端只收聚合結果（FR-002）；圖表查詢 ≤ 既有用量查詢延遲量級
- 前端 bundle gzip 增量 < 150KB（SC-003）
**Constraints**:
- 首頁 ≤ 3 張圖；隔離/暫停警示永遠在圖表之上（FR-007/008）
- 每張圖驅動一個決策；無資料時友善空狀態（FR-019/021）
- 既有頁面零退化（FR-022/SC-007）
- 只導一個圖表 lib（FR-001）
**Scale/Scope**: 數十 model/provider/tag、數百分配、數萬呼叫；聚合 row 數小

## 憲章檢核（Constitution Check）

*GATE：必須在 Phase 0 research 前通過。Phase 1 design 後重核。*

### I. Test-First（不可妥協）
- ✅ 後端 3 個新聚合先寫 contract/integration test（Red）才實作；前端圖表以 vitest 驗資料 → 渲染
- ✅ 缺陷修復以可重現失敗測試起手

### II. API 契約優先
- ✅ 新增端點（平台時序 / provider 維度 / heatmap / 隔離原因）以 OpenAPI 定義後實作
- ✅ 既有 `/admin/usage` 擴充 `group_by=provider`（非破壞）；其餘為新增端點

### III. 整合測試覆蓋外部依賴
- ✅ 後端聚合的 DB 正確性（含 dialect-aware date truncation、provider JOIN catalog）以整合測試驗

### IV. 可觀測性
- ✅ 沿用既有 usage 端點 log；無新外部依賴

### V. 簡潔優先（YAGNI）
- ✅ **無新表 / migration**；聚合複用既有 `aggregate_usage` / `usage_timeseries` 模式
- ✅ 隔離原因 surface **沿用既有稽核 `details`**（last_hour_calls/baseline/reason），不新增欄位
- ✅ **單一**圖表 lib + 共用 wrapper（呼應「同一概念兩份必 drift」lesson）
- ✅ 不做詳情頁圖、不做花俏圖型（spec 明確排除）

### 語言與文件規範
- ✅ spec/plan/tasks/checklists 繁中；code 識別字英文；commit 英文；圖表 UI 文案繁中

**Gate 結果（Phase 0 前）**：通過。無偏離項。

**重核（Phase 1 後）**：
- I. TDD：4 個後端端點 contracts 已定義；tasks 將生成「先寫聚合正確性測試 → 才實作」。✅
- II. 契約優先：`contracts/admin-viz.openapi.yaml` 完整（provider enum 擴充 + 3 新端點，標 NON-BREAKING）。✅
- III. 整合測試：平台時序、provider JOIN catalog、heatmap UTC+8 分桶、隔離原因皆有整合情境（quickstart 1–6）。✅
- IV. 可觀測性：沿用既有 usage log，無新外部依賴。✅
- V. YAGNI：無新表/migration；隔離原因沿用既有稽核 details；單一圖表 lib + 共用 wrapper；heatmap 用 CSS grid 不硬塞 recharts。✅

**Phase 1 後 Gate 結果**：通過。設計穩定，可進入 `/speckit.tasks`。

## 專案結構

### 文件（本 feature）

```text
specs/024-admin-visualization/
├── plan.md / spec.md / research.md / data-model.md / quickstart.md
├── contracts/admin-viz.openapi.yaml
├── checklists/requirements.md（已完成）
└── tasks.md（/speckit.tasks 產生）
```

### 原始碼（既有結構，標 NEW / 改）

```text
backend (src/ai_api/)
├── services/usage.py        # 改：平台級時序（allocation_id optional）；group_by="provider" 分支（JOIN model_catalog）；hour×weekday heatmap 聚合函式
└── api/usage.py             # 改：group_by enum 加 provider；新增 GET /admin/usage/timeseries（平台級）、GET /admin/usage/heatmap、GET /admin/allocations/{id}/quarantine-reason

frontend (frontend/src/)
├── components/ui/chart.tsx          # NEW: 共用 <Chart> wrapper（recharts 主題 / tooltip / 空狀態）
├── components/time-range-select.tsx # NEW: 統一時段選擇器（週/月/季/自訂）
├── routes/admin/home.tsx            # 改：加 3 張圖 + Top 5 tags 卡（隔離警示維持最上方）
├── routes/admin/usage.tsx           # 改：provider donut + 24×7 heatmap + 時段選擇器
└── routes/admin/allocations.tsx     # 改：隔離/暫停徽章 hover 顯示原因 + 解除頁顯示觸發數據

tests/
├── contract/test_usage_viz.py       # NEW: 平台時序 / provider 維度 / heatmap / quarantine-reason 端點
└── integration/test_usage_viz_agg.py# NEW: 聚合正確性（時序、provider JOIN、heatmap 分桶）

frontend tests: vitest 對 chart wrapper 資料映射 + 空狀態
```

**Structure Decision**: 沿用既有 web application 結構。**零新表、零 migration、一個新前端依賴
（recharts）**。後端改動集中在 `services/usage.py`（3 聚合）+ `api/usage.py`（enum + 3 端點）；
前端新增 2 個共用元件 + 改 3 個既有 route。

## Complexity Tracking

> 無憲章違反項，本節空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| —         | —          | —                                   |

## 下一步

- Phase 0 / Phase 1 artifacts 由本 `/speckit.plan` 後續產生
- Phase 1 後重核憲章
- `/speckit.tasks` 以 plan + research + data-model + contracts 產出 tasks.md
