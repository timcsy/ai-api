---
description: "Task list for OpenAI 相容 /v1/models ＋ Copilot 上卡"
---

# Tasks: OpenAI 相容 `/v1/models` ＋ Copilot 上卡

**Input**: Design documents from `/specs/050-openai-models-copilot/`
**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/v1-models.md、quickstart.md（皆已產出）

**Tests**: 本專案 constitution 強制 TDD（原則 I），故**包含測試任務**，且測試先於實作（紅 → 綠 → 重構）。

**Organization**: 依 user story（P1→P3）分階段，每個 story 為獨立可測、可交付的增量。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行（不同檔案、無未完成相依）
- **[Story]**: US1 / US2 / US3
- 每個任務含精確檔案路徑

## Path Conventions

Web app：後端 `src/ai_api/`、`tests/`；前端 `frontend/src/`。

---

## Phase 1: Setup（共用前置）

**Purpose**: 確認既有環境就緒——本功能不新增套件、不新增表/migration。

- [X] T001 確認分支 `050-openai-models-copilot` 已 checkout，並跑一次基線 `cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && pytest tests/contract/test_responses_basic.py -q` 與 `ruff check .` 確保起點全綠（之後比對零回歸）

---

## Phase 2: Foundational（阻斷性前置）

**Purpose**: 無跨 story 的阻斷性前置——`/v1/models` 的後端僅 US1 使用，US2/US3 為前端與訊息層。**本階段無任務**，直接進 US1。

*(無 foundational 任務；US1 自帶其唯一需要的 service 方法。)*

---

## Phase 3: User Story 1 — 客戶端用金鑰列出可用模型（Priority: P1）🎯 MVP

**Goal**: `GET /v1/models` 與 `GET /v1/models/{id}` 以 Bearer 金鑰認證，回傳該金鑰 scope 內 active 分配的模型（OpenAI 相容），識別碼可原樣呼叫。

**Independent Test**: 帶有效金鑰打 `/v1/models` 得 scope 內模型清單；換 scope 不同金鑰得不同清單；無金鑰 401；清單 id 拿去 chat 不報 model_mismatch。不需 Copilot 即可驗收。

### Tests for US1（先寫、必須先紅）

- [X] T002 [US1] 在 `tests/contract/test_v1_models.py` 寫**失敗中**的契約測試，涵蓋 contracts/v1-models.md 全部 8 條不變式：list scope 一致（SC-001）、retrieve 對稱、401（缺/空/無效 Bearer，body 無模型資訊）、scope 隔離（兩把金鑰）、排除 paused/revoked 分配、未定價模型仍列、list 任一 id 原樣送 `/v1/chat/completions` 不回 `model_mismatch`（SC-002）、retrieve 不存在 id → 404。沿用既有 contract 測試的 fixtures（seed member/allocation/credential/credential_allocation + catalog/provider credential 模式，參考 `tests/contract/test_responses*.py`）

### Implementation for US1

- [X] T003 [US1] 在 `src/ai_api/services/allocations.py` 新增 `list_active_scope_allocations(self, credential) -> Sequence[Allocation]`：`Allocation` JOIN `CredentialAllocation` WHERE `credential_id == credential.id` AND `Allocation.status == AllocationStatus.active`，依 `resource_model` 排序回傳（沿用既有 import 與 `Sequence` 回傳慣例，見同檔 `scope_models`）
- [X] T004 [US1] 新建 `src/ai_api/proxy/models.py`：定義 OpenAI Model 序列化 helper `_to_openai_model(alloc, created_ts)`（`{id: resource_model, object:"model", created, owned_by: parse_provider(resource_model)[0]}`，`parse_provider` 來自 `proxy/allowlist`），與 `APIRouter()`；`created` 取對應 `ModelCatalog.created_at` epoch（一次查 catalog 建 slug→created 映射，查無則用 `alloc.created_at`）
- [X] T005 [US1] 在 `src/ai_api/proxy/models.py` 實作 `GET /models`：`parse_bearer_token(authorization)`（缺/空 → 401，重用 `proxy/auth.py`）→ `AllocationService.lookup_credential_by_token(token)`（None → 401 `unauthorized`）→ `list_active_scope_allocations` → 序列化成 `{"object":"list","data":[...]}`，依 id 排序
- [X] T006 [US1] 在 `src/ai_api/proxy/models.py` 實作 `GET /models/{id:path}`：認證同上 → `AllocationService.resolve_scope_allocation(credential, id)`（exact + 唯一 bare alias）→ 命中且 `status==active` 回單一 model object；否則 404 `{"error":{"code":"not_found",...}}`（不洩漏存在性）
- [X] T007 [US1] 在 `src/ai_api/main.py` 掛載：`from ai_api.proxy.models import router as models_router` 並 `app.include_router(models_router, prefix="/v1", tags=["proxy"])`（與既有 `/v1` proxy router 同前綴、緊鄰其後）
- [X] T008 [US1] 跑 `pytest tests/contract/test_v1_models.py -q` 轉綠 + `ruff check .`（與 CI 同範圍，含 tests/）；再跑既有 `tests/contract/test_chat*.py tests/contract/test_responses*.py -q` 確認既有 `/v1/*` 端點零回歸

**Checkpoint US1**: `/v1/models` list/retrieve 可用、scope 正確、id 可路由——任何 OpenAI 客戶端 / curl 立即可用（MVP 可獨立交付）。

---

## Phase 4: User Story 2 — 成員從應用商店接上 GitHub Copilot（Priority: P2）

**Goal**: 應用商店出現 Copilot 卡（設定步驟 + 建金鑰捷徑 + 零分配指引），成員照做能接上。

**Independent Test**: 前端測試斷言 Copilot 卡渲染、零相容分配時顯示指引（不給死路建立鈕）；真機 SC-004 驗收（部署後人工）。

**依賴**: US1 的 `/v1/models` 是 Copilot 真機可用的前提；但本 story 的前端卡可獨立開發/單測（不阻於 US1 上線）。

### Tests for US2（先寫、必須先紅）

- [X] T009 [P] [US2] 在 `frontend/src/__tests__/apps-copilot.test.tsx` 寫失敗測試：應用商店 tile 含「GitHub Copilot」；詳情頁渲染設定步驟與「建金鑰」捷徑；無相容分配時顯示指引文字、不出現可建立鈕（沿用既有 `apps-direct-api`/codex 卡測試模式）

### Implementation for US2

- [X] T010 [P] [US2] 在 `frontend/src/components/app-logos.tsx` 加 `CopilotLogo`（GitHub Copilot inline SVG mark，沿用既有 `ApiLogo`/Codex logo 寫法）
- [X] T011 [US2] 新建 `frontend/src/components/copilot-app-detail.tsx`：狀態（依 `/me/allocations` 的 `agent_compatible`/responses 相容計數，0 → 指引不給建立鈕，與 `codex-app-detail.tsx` 一致）+ 設定步驟（base URL `apiBaseUrl()` + `$TOKEN` + 在 Copilot 自訂端點填入）+ 建金鑰捷徑（重用 `POST /me/credentials`，picker 預選相容分配，token 顯示一次）
- [X] T012 [US2] 在 `frontend/src/lib/applications.tsx` 註冊 `{ id: "copilot", name: "GitHub Copilot", Logo: CopilotLogo, Detail: CopilotAppDetail }`（加一筆＝一張 tile + 一詳情，原則 7）
- [X] T013 [US2] 跑 `cd frontend && npx vitest run src/__tests__/apps-copilot.test.tsx` 轉綠 + `npx tsc --noEmit` + `npm run build`；再跑既有前端測試確認零回歸

**Checkpoint US2**: Copilot 卡上架、零分配指引正確、建金鑰捷徑可用（前端可獨立單測通過）。

---

## Phase 5: User Story 3 — 跨 model／過期續接時得到可操作的指引（Priority: P3）

**Goal**: 續接接不上時維持 fail-loud，且錯誤訊息**可操作**（提示開新對話）；Copilot 卡載明此行為。

**Independent Test**: 同金鑰跨兩分配續用同一對話 → 明確且可操作的錯誤；過期 → 明確 not_found；Copilot 卡文案含「跨 model ＝開新對話」。

**依賴**: 後端訊息層獨立；卡文案改 `copilot-app-detail.tsx`（US2 同檔 → 接在 T011 之後）。

### Tests for US3（先寫、必須先紅）

- [X] T014 [P] [US3] 在 `tests/contract/test_stored_responses.py`（既有跨分配/過期續接測試檔）加/改斷言：跨分配續接回 `response_forbidden`、過期回 `response_not_found`，且 `message` 為可操作中文（含「開新對話」字樣）——先讓訊息斷言失敗
- [X] T015 [P] [US3] 在 `frontend/src/__tests__/apps-copilot.test.tsx` 加斷言：Copilot 詳情頁含「同一把金鑰跨 model 切換＝開新對話」說明文字（先紅）

### Implementation for US3

- [X] T016 [US3] 在 `src/ai_api/proxy/responses.py`（約 line 283/286 的 `reject("response_not_found", ...)` / `reject("response_forbidden", ...)` 呼叫）把 `message` 調成可操作中文（明說「此對話屬另一分配／已過期，請開新對話」），**維持拒絕、不靜默降級**（對齊 experience「接不上的續接請求要明確拒絕」）；不動狀態碼與既有拒絕邏輯
- [X] T017 [US3] 在 `frontend/src/components/copilot-app-detail.tsx` 加一段說明：伺服器端對話記憶是 per-分配，同金鑰跨 model 切換＝開新對話（解釋原因，降低踩坑）
- [X] T018 [US3] 跑 `pytest tests/contract/test_responses_continuation.py -q`（或對應檔）+ `cd frontend && npx vitest run src/__tests__/apps-copilot.test.tsx` 轉綠 + `ruff check .`

**Checkpoint US3**: 續接 fail-loud 訊息可操作、卡上事先說明（體驗收尾完成）。

---

## Phase 6: Polish & Cross-Cutting（收尾與上線驗收）

- [X] T019 跑全套件零回歸：`pytest tests/ -q`（contract + integration + unit）+ `ruff check .`；`cd frontend && npx tsc --noEmit && npm run build && npx vitest run`
- [ ] T020 PR + squash-merge 到 main（CI 全綠：test / frontend / build-and-push / build-and-push-frontend），依維護者偏好前後端一起部署到同一新 sha（helm `--reuse-values` + `--set storedResponseCleanup.enabled=true --set storedResponseCleanup.schedule="0 3 * * *"`，**無 migration 故不設 migrationJob**）
- [ ] T021 **部署後真機驗收（SC-004，人工）**：依 `quickstart.md` §3——VS Code GitHub Copilot 指向本平台，確認「列模型 → 一次對話」端到端成功（非只 401 煙霧）；§4 帶真金鑰 curl `/v1/models` 回非空 list 且 id 可 chat。若揭露阻斷性限制 → 卡誠實標限制 / 延後（FR-010）
- [ ] T022 知識同步（經使用者確認後）：`knowledge/vision.md` 將階段 36 標為 ✅ 上線（rev 待定）+ 現狀/狀態同步；若真機揭露新坑，蒸餾一條進 `knowledge/experience.md`（呼應「新端點帶真憑證真打才算驗過」）

---

## Dependencies & Execution Order

- **Setup（T001）** → 一切之前。
- **US1（T002–T008，P1）**：MVP，後端純讀，獨立可交付。T002（測試）先；T003/T004 可平行（不同檔），T005/T006 依賴 T003+T004，T007 依賴 T005+T006，T008 最後。
- **US2（T009–T013，P2）**：前端卡，可與 US1 平行開發；真機驗收（T021）依賴 US1 上線。T009（測試）+ T010（logo）可平行；T011 依賴 T010；T012 依賴 T011；T013 最後。
- **US3（T014–T018，P3）**：後端訊息（T016）獨立；前端卡文案（T017）依賴 US2 的 T011（同檔）。
- **Polish（T019–T022）**：所有 story 完成後。T021 真機驗收依賴 T020 部署。

### 平行機會
- US1 與 US2 的前端可同時進行（不同子系統）。
- US1 內：`T003 [P]` 與 `T004 [P]`（service vs 新檔）。
- US2 內：`T009 [P]`（測試）與 `T010 [P]`（logo）。
- US3 內：`T014 [P]`（後端測試）與 `T015 [P]`（前端測試）。

## Implementation Strategy

- **MVP = US1**：`/v1/models` 一上線，所有 OpenAI 相容客戶端（含 curl/SDK，不只 Copilot）立即受惠——可先獨立交付。
- **US2/US3 為應用層收尾**：在 US1 可用後接上 Copilot 卡與續接體驗；Copilot 是否正式上卡以**真機驗收（T021）**為門檻，過不了就誠實標限制。
- **零回歸鐵律**：既有 `/v1/*` contract 測試 git diff 為空且全綠（T008、T019）。
