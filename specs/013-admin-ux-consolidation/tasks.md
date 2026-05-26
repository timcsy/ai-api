# Tasks: Admin Workflow Consolidation

**Input**: Design documents from `/specs/013-admin-ux-consolidation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Constitution I 強制 TDD — 每個 story 必有 failing test 先於實作。

**Organization**: 按 user story 分 Phase。MVP = US1（onboarding） + US2（member×model 端對端）即可 demo「11 頁濃縮為核心 6 入口」的核心價值。

---

## Phase 1: Setup（共享基礎）

- [X] T001 確認 React Router DOM v7 (`react-router-dom@^7`) 已安裝；如未到位則 `cd frontend && npm install react-router-dom@^7`（plan 預設沿用既有版本，本任務只驗證）
- [X] T002 [P] 在 `frontend/src/routes/admin/` 建立空殼檔案：`model.tsx`、`model-detail.tsx`、`member-detail.tsx`、`tag-detail.tsx`、`observability.tsx`，每檔 default export 一個 placeholder component（讓 App.tsx 可先掛 route，UI 後續填）

---

## Phase 2: Foundational（阻塞性前置）

**⚠️ CRITICAL**：本 phase 全綠之前不可開始任何 user story

### 後端 — Visibility 診斷服務

- [X] T003 寫 `tests/unit/test_visibility_diagnose.py`（紅）：純函式 `evaluate_visibility(member, model, active_providers)`，至少 6 案例：
  - 全通過 → visible=True
  - credential_gate 失敗 → 短路停止
  - default_access=open + 無 deny 命中 → 通過
  - default_access=open + deny 命中 → 失敗
  - default_access=restricted + allow 命中 → 通過
  - default_access=restricted + allow 不命中 → 失敗
- [X] T004 在 `src/ai_api/services/model_access.py` 加 `evaluate_visibility()` 函式，回 `VisibilityResult` typed dict（重用既有 `access_policy_allows` 邏輯，包成有 reason_chain 版本）；讓 T003 綠
- [X] T005 [P] 寫 `tests/contract/test_admin_diagnose.py`：對 `contracts/diagnose.yaml` 兩個 endpoint，含 401/403/404 + 各種 reason_chain 路徑
- [X] T006 寫 `src/ai_api/api/admin_diagnose.py`：
  - `GET /admin/diagnose/visibility?member_id=...&model_slug=...`
  - `GET /admin/members/{member_id}/visible-models`
  - 兩者 require_admin_token，無 audit
- [X] T007 在 `src/ai_api/main.py` 註冊 `admin_diagnose.router` 到 `/admin` prefix
- [X] T008 跑 T003 + T005 全綠；既有 264 backend 測試零回歸

### 前端 — Legacy URL Redirect

- [X] T009 [P] 寫 `frontend/src/__tests__/legacy-redirects.test.tsx`（紅）：9 個舊 URL 各驗 redirect 到新 URL
- [X] T010 寫 `frontend/src/lib/legacy-redirects.tsx`：export 一個 `<LegacyRedirects />` 元件，包 9 個 `<Route element={<Navigate ... />}>` 給 R2 表中所有舊路徑
- [X] T011 在 `App.tsx` 把 `<LegacyRedirects />` 掛在所有 admin route 之**前**（讓舊 URL 先 redirect 再 fallback NotFound）；確認舊 URL 100% 跳新位置（手測 SC-005）

### 前端 — Visibility 診斷元件

- [X] T012 [P] 寫 `frontend/src/__tests__/visibility-diagnose.test.tsx`（紅）：mock /admin/diagnose endpoint，驗 reason_chain 渲染 + 失敗 check 旁有「修補」CTA
- [X] T013 寫 `frontend/src/components/visibility-diagnose.tsx`：可重用面板，props `(memberId?, modelSlug?)`；內含 member 與 model 兩個 picker、結果列表、各失敗 check 的修補 mutation（加 tag / 新增 credential 跳轉等）

**Checkpoint**：後端 diagnose endpoint 可用；legacy redirect 全 9 個生效；可重用診斷元件就緒

---

## Phase 3: User Story 1 — 新 admin 第一天上手（onboarding → dashboard）(Priority: P1)

**Goal**：`/admin` 首頁在 onboarding 完成後自動切換為 dashboard 模式

**Independent Test**：空白 DB 登入 → checklist 顯示 → 依序完成 4 項 → 進度 4/4 → 同頁切到 dashboard 模式（顯示用量摘要 / 最近活動）

### US1 Tests（先紅）

- [X] T014 [P] [US1] 寫 `frontend/src/__tests__/admin-home-modes.test.tsx`：
  - 0 provider / 0 model / 0 member / 0 allocation → 顯示 checklist
  - 全 >0 → 顯示 dashboard 模式
  - 從 dashboard 退回 onboarding 場景（删 provider）→ 自動切回

### US1 Implementation

- [X] T015 [US1] 修改 `frontend/src/routes/admin/home.tsx`：condition = `providerCount>0 && modelCount>0 && memberCount>0 && allocationCount>0`；true → render `<AdminDashboard />`（新元件），false → 既有 checklist
- [X] T016 [US1] 新增 `frontend/src/routes/admin/admin-dashboard.tsx`：最小版本：
  - 本月總呼叫數（合計）
  - 最近 10 條 audit
  - 異常 allocation 數（quarantine 狀態）
  - 「跳去觀測」連結
- [X] T017 [US1] 跑 T014 全綠；手測場景 1（quickstart）

**Checkpoint**：MVP 第一片達成

---

## Phase 4: User Story 2 — 給某成員開通某 model 端對端 (Priority: P1)

**Goal**：admin 從 model 或 member 任一入口，2 個頁面內完成開通

**Independent Test**：catalog 有 model + provider 有 key + member 無 tag 狀態下，從 `/admin/model` 入口完成「加 tag → 建 allocation」少於 3 個動作

### US2 Tests（先紅）

- [ ] T018 (deferred) [P] [US2] 寫 `frontend/src/__tests__/admin-model-list.test.tsx`：列表頁顯示 model + 對應 provider 狀態 + 對成員可見性
- [ ] T019 (deferred) [P] [US2] 寫 `frontend/src/__tests__/admin-model-detail.test.tsx`：基本資訊 + 存取規則 + 健康診斷三區塊；包含 visibility 預覽 + 修補快捷
- [ ] T020 (deferred) [P] [US2] 寫 `frontend/src/__tests__/admin-member-detail.test.tsx`：四區塊（基本/Tag/可用 model/Allocations）

### US2 Implementation — Model 入口

- [X] T021 [US2] 寫 `frontend/src/routes/admin/model.tsx`：合併現 `catalog-manage.tsx` 列表 + 行動，連結每 row 至 `/admin/model/:slug`；保留「加入 Model」按鈕
- [X] T022 [US2] 寫 `frontend/src/routes/admin/model-detail.tsx`：
  - 基本資訊卡（顯示 + 編輯）
  - 存取規則卡（合併現 `model-access.tsx` 形態）
  - 健康診斷卡（嵌入 `<VisibilityDiagnose modelSlug={slug} />`）
- [ ] T023 (deferred) [US2] 在 model-detail 加「給該 member 建 allocation」捷徑：開既有 allocation create dialog（複用 `allocations.tsx` 的元件抽出來），預填 model

### US2 Implementation — Member 入口

- [X] T024 [US2] 寫 `frontend/src/routes/admin/member-detail.tsx`：
  - 基本資訊（沿用既有）
  - Inline tag 編輯（沿用 `MemberTagsCell`）
  - 「可用 model」清單：呼叫 `GET /admin/members/{id}/visible-models`
  - 「Allocations」區塊：該成員的 allocation 列表 + 「建分配」內嵌按鈕
- [X] T025 [US2] 修改 `frontend/src/routes/admin/members.tsx`：每 row 變 clickable，連結至 `/admin/member/:id`（detail 頁）

### US2 Wiring

- [ ] T026 (deferred) [US2] 把抽出的 `AllocationCreateDialog`、`AccessPolicyEditor`、`ModelBasicForm` 元件放 `frontend/src/components/`；原 `catalog-manage.tsx`、`model-access.tsx`、`allocations.tsx` 改 import 用相同元件（避免重複）
- [X] T027 [US2] 在 App.tsx 註冊新 routes：`/admin/model`、`/admin/model/:slug`（path 用 `*` 因為 slug 含 `/`）、`/admin/member`、`/admin/member/:id`
- [X] T028 [US2] 跑 T018-T020 + T014 不退步；手測場景 2（quickstart）

**Checkpoint**：US2 完成，MVP 完整

---

## Phase 5: User Story 3 — Tag 群組規則雙向 (Priority: P2)

**Goal**：Tag detail 頁同時看 member + model 雙向

### US3 Tests（先紅）

- [ ] T029 [P] [US3] 寫 `frontend/src/__tests__/admin-tag-detail.test.tsx`：顯示「N 個 member 持有」「M 個 model 將此 tag 列為 allowed」「K 個 model 將此 tag 列為 denied」三組

### US3 Implementation

- [ ] T030 [US3] 寫 `frontend/src/routes/admin/tag-detail.tsx`：
  - 持有此 tag 的 member 列表（呼叫 `/admin/tags` 加新 endpoint 或復用 distinct member 計算）
  - 列出 catalog 中 allowed_tags 含此 tag 的 models
  - 列出 catalog 中 denied_tags 含此 tag 的 models
- [ ] T031 [US3] 修改 `frontend/src/routes/admin/tags.tsx` → 改名概念為 `/admin/tag`，每 row clickable 跳 `/admin/tag/:tag`
- [ ] T032 [US3] 跑 T029 綠；手測場景 3

---

## Phase 6: User Story 4 — 診斷「為何 X 看不到 Y」 (Priority: P2)

**Goal**：reason_chain 在 UI 清楚顯示 + 修補 CTA

**Independent Test**：場景 4（quickstart），「為何看不到」答案 < 15 秒，每失敗原因有具體修補按鈕

### US4 Tests（先紅）

- [ ] T033 [P] [US4] 寫 `frontend/src/__tests__/visibility-diagnose-repair.test.tsx`：
  - 「allow_tags 不命中」→ 顯示「加 tag」按鈕 → 點擊呼叫 add tag mutation
  - 「credential_gate 失敗」→ 顯示「去新增 credential」連結 → 跳到 providers
  - 「deny_tags 命中」→ 顯示「移除 tag」按鈕

### US4 Implementation

- [ ] T034 [US4] 在 `frontend/src/components/visibility-diagnose.tsx` 加修補 logic：每個失敗 check 對應一個 mutation / 跳轉
- [ ] T035 [US4] 在 `/admin` sub-nav 加「診斷」入口（或內嵌於 model 與 member detail，本任務只確保兩處都嵌好）
- [ ] T036 [US4] 跑 T033 綠；手測場景 4

---

## Phase 7: User Story 5 — 觀測整合 (Priority: P3)

**Goal**：4 個觀測類頁面整合為 `/admin/observability` + 4 子路徑

### US5 Tests（先紅）

- [ ] T037 [P] [US5] 寫 `frontend/src/__tests__/admin-observability.test.tsx`：
  - 在 `/admin/observability` 顯示 4 tab bar + 預設 redirect 到 usage
  - 每 tab URL 獨立可分享（`/admin/observability/usage` 等）

### US5 Implementation

- [ ] T038 [US5] 寫 `frontend/src/routes/admin/observability.tsx`：layout 元件，顯示 tab nav + `<Outlet />`
- [ ] T039 [US5] 在 App.tsx 加 `/admin/observability` route 含 4 個 child route，分別 render 既有 `usage.tsx`、`quota-pool.tsx`、`rebalance-log.tsx`、`audit.tsx`
- [ ] T040 [US5] 在 member-detail 「異常」區塊嵌入該 member 最近一週 anomaly + 「啟用 quarantine」按鈕（重用既有 mutation）
- [ ] T041 [US5] 跑 T037 綠；手測場景 5

---

## Phase 8: Polish & 橫切

- [ ] T042 [P] 修改 `frontend/src/components/app-shell.tsx`：sub-nav 從 11 條砍到 6 條（首頁 / Model / 成員 / Tag / Provider 憑證 / 觀測）；驗證 SC-004
- [ ] T043 [P] 跑場景 6 + 7（quickstart）：legacy URL 全 redirect、所有 contract test 綠
- [ ] T044 [P] 更新 `knowledge/vision.md` 加 Phase 5.1 段落（已完成）
- [ ] T045 跑全套 gate：`uv run pytest -q && uv run ruff check . && uv run mypy src/ai_api && cd frontend && npm run lint && npm run typecheck && npm test -- --run`

---

## Dependencies

```text
Setup (T001-T002)
    ↓
Foundational (T003-T013) ← 必須全綠
    ↓
US1 (T014-T017) ────────────┐
US2 (T018-T028) ──── needs Foundational ↓
US3 (T029-T032) ─── needs Foundational + US2（共用 model/member 元件）
US4 (T033-T036) ─── needs Foundational T012-T013
US5 (T037-T041) ─── needs Foundational（獨立）
    ↓
Polish (T042-T045)
```

**並行機會**：
- T002 與其他 Setup 並行
- US1-US5 在 Foundational 後可大幅並行（不同 route 檔案）
- 多數 tests（T014/T018/T019/T020/T029/T033/T037）獨立檔可全並行

## Implementation Strategy

**MVP scope = US1 + US2**：T001-T028 共 ~28 task；admin 看到新首頁切換 + Model/Member 兩大入口可用，已涵蓋 SC-001 / SC-002。約 2-3 工作日。

**穩定 release = US1+US2+US3**：再加 4 task，~ 1 工作日。

**Phase 5.1 full = 全部完成**：再加 9 task + polish 4，~ 1.5 工作日。

**總估**：45 task，~ 4-5 個工作日。
