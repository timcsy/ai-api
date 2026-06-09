# Tasks: 應用分頁（應用目錄）—— Codex 為第一個應用

**Feature**: `037-application-catalog` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/apps-and-allocations.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 有行為的後端衍生欄、前端頁面/捷徑皆先寫失敗測試再實作。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`（皆 repo root 相對）。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract -q -k allocations && cd frontend && npm test -- --run` 綠（改動前基準）。

---

## Phase 2: Foundational（阻擋所有 user story 的前置）

**目的**：把「Agent 相容」資料沿既有 `/me/allocations` 暴露——所有 user story（狀態判斷、建金鑰捷徑預過濾）都依賴它。

- [X] T002 [P] 寫/擴充 `tests/contract/test_me_allocations.py`（先失敗）：`GET /me/allocations` 每筆回 `agent_compatible` —— seed 三個分配:(a) 模型 capabilities 含 `responses`（available）→ `true`；(b) 模型 capabilities 無 responses（unknown）→ `false`；(c) orphan slug（不在 catalog）→ `false`。`current_member` 隔離不變。
- [X] T003 改 `src/ai_api/api/me.py`：`list_my_allocations` 多載 `slug→capabilities`（從 `ModelCatalog`），`_alloc_public` 加唯讀 `agent_compatible = responses_support.get_support(caps)["state"] == "available"`（orphan/None caps → false）。令 T002 轉綠。

**Checkpoint**：`/me/allocations` 帶 `agent_compatible`，前端可用。

---

## Phase 3: User Story 1 — 應用分頁 + Codex 一鍵設定（P1）🎯 MVP

**Goal**：成員導覽「應用」→ `/apps` → Codex 卡（含一鍵設定）；dashboard/金鑰頁去除安裝卡。

**Independent Test**：進 `/apps` 見 Codex 卡 + 一鍵設定；dashboard/金鑰頁不再有安裝卡。

- [X] T004 [P] [US1] 寫 `frontend/src/__tests__/apps-page.test.tsx`（先失敗）：render `ApplicationsPage` → 顯示 Codex 卡標題 + 一鍵設定（`CodexInstallCard` 內容）出現。
- [X] T005 [P] [US1] 改 `frontend/src/__tests__/mobile-nav.test.tsx`（先失敗）：`MAIN_NAV` 期望清單加「應用」（drawer 列出「應用」目的地）。
- [X] T006 [US1] 新增 `frontend/src/routes/apps.tsx`（`ApplicationsPage`）：渲染 Codex 應用卡（標題 + 一句說明 + 既有 `CodexInstallCard` 一鍵設定）；`baseUrl` 同既有用法。
- [X] T007 [US1] 改 `frontend/src/components/app-shell.tsx`：`MAIN_NAV` 加 `{ to:"/apps", label:"應用" }`；`frontend/src/App.tsx` 加 `<Route path="/apps" element={<ApplicationsPage/>} />`。令 T004/T005 轉綠。
- [X] T008 [US1] 收斂去重（FR-003）：`frontend/src/components/member-overview.tsx` 與 `frontend/src/routes/keys.tsx` **移除** `CodexInstallCard`（搬到 `/apps`）；若 dashboard/keys 既有測試斷言該卡存在，改為不斷言（搬家）。

**Checkpoint**：US1 可獨立驗收（應用頁 + 一鍵設定 + 單一所在地）。

---

## Phase 4: User Story 2 — 建金鑰捷徑（scope 預選 Agent 相容）（P1）

**Goal**：「為 Codex 建金鑰」只納入 Agent 相容分配；無相容分配→指引不建。

**Independent Test**：捷徑 picker 只列 agent_compatible；無相容分配→顯示指引、無建立鈕。

- [X] T009 [P] [US2] 寫 `frontend/src/__tests__/apps-codex-create-key.test.tsx`（先失敗）：(a) 有 agent_compatible 分配 → 卡片顯示「為 Codex 建金鑰」，開啟後 picker **只列** agent_compatible（非相容不出現）、預選；送出呼叫 `POST /me/credentials` body 含 name + 只含 agent_compatible 的 `allocation_ids`；(b) 0 個 agent_compatible → 顯示「目前沒有可用於 Codex 的模型」+ 指引、**無**建立鈕。
- [X] T010 [US2] 在 `frontend/src/routes/apps.tsx` 加：狀態（依 `/me/allocations` 算 `agentAllocs`）+ 「為 Codex 建金鑰」聚焦建立流程（picker = agentAllocs 預選、名稱預設「Codex」→ `POST /me/credentials` → token 顯示一次）；0 相容時顯示指引、不開建立。令 T009 轉綠。

**Checkpoint**：US2 可獨立驗收（捷徑只建 Agent 相容金鑰、無相容給指引）。

---

## Phase 5: User Story 3 — 多介面說明 + 桌面 App △→✓（P2）

**Goal**：Codex 卡說明多介面共用設定；桌面 App 改 ✓；能自動的自動、其餘給連結。

**Independent Test**：桌面 App 標 ✓（無「△ 不建議」）；介面分自動/連結;連結可點。

- [X] T011 [P] [US3] 改 `frontend/src/__tests__/codex-install-card.test.tsx`（先失敗）：斷言桌面 App 段為新 ✓ 文案（「用一鍵安裝後也能用」/「共用設定」），且**不**含舊「不建議」字樣；網頁版仍「不適用」。
- [X] T012 [US3] 改 `frontend/src/components/codex-install-card.tsx`：桌面 App 段 △→✓（共用 `~/.codex`、免再設定，移除「不建議」）；介面區分「能自動（CLI；VS Code 擴充見 T013）」與「給連結（桌面 App / Cursor / JetBrains，『裝好免再設定』）」。令 T011 轉綠。
- [X] T013 [US3] VS Code 擴充（FR-007/009，先驗證再決定）：查證 Codex 官方 VS Code extension id —— **可靠確認** → 安裝腳本 `src/ai_api/install/codex.{sh,ps1}.tmpl` 加「偵測 `code` → 可選 `code --install-extension <id>`」，偵測不到則略過不報錯；**無法確認** → v1 僅在 Codex 卡放 marketplace 連結（link-only），不動安裝腳本。於 research.md/卡片註明所採路徑。

**Checkpoint**：US3 可獨立驗收（介面誠實呈現、App ✓）。

---

## Phase 6: Polish & Cross-Cutting

- [X] T014 跑後端 `python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api/api/me.py` 全綠；確認 device-flow/計費/金鑰零回歸（SC-006）。
- [X] T015 [P] 前端 `cd frontend && npx tsc --noEmit && npm run build && npm test -- --run` 全綠（含 apps/nav/install-card 新舊測試）。
- [X] T016 [P] 確認 `alembic heads` 無新增、依賴（pip/npm）無新增。
- [X] T017 依 `quickstart.md` 走 US1–US3 + 零回歸手動驗收；**三平台煙霧**至少一台「CLI 一鍵安裝 → CLI 可用 → 桌面 App 共用設定也可用」（沿用階段 19 習慣）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **Foundational（T002–T003）** 阻擋全部（前端狀態/捷徑都需 `agent_compatible`）。
- **US1（T004–T008）** 依賴 Foundational；MVP。
- **US2（T009–T010）** 依賴 US1（同在 `apps.tsx`）+ Foundational（agent_compatible）。
- **US3（T011–T013）** 與 US1/US2 大致獨立（改 `codex-install-card` + 安裝腳本），可平行於 US2。
- **Polish（T014–T017）** 最後。

## 平行機會
- Foundational：T002（後端測試）可獨立起草。
- 測試先寫：T004/T005（US1）、T009（US2）、T011（US3）不同檔可平行。
- US3 與 US2 可平行（不同檔）。
- Polish：T015/T016 可平行。

## MVP 範圍
**US1（T001–T008）** 即 MVP：應用分頁 + Codex 一鍵設定 + 單一所在地。US2（建金鑰捷徑）、US3（多介面/App ✓）為增量。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
