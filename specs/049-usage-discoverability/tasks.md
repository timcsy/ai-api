# Tasks: 「如何呼叫」可發現性重設計

**Input**: Design documents from `specs/049-usage-discoverability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui.md, quickstart.md

**Tests**: 包含（Constitution 原則 I Test-First 非協商）——vitest 先寫且先失敗，再實作。

**Organization**: 按 user story（P1/P2/P3）分階段；**純前端、零後端、零 migration、零新套件**。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同檔案、無未完成依賴，可並行
- **[Story]**: US1 / US2 / US3（對映 spec 的 P1/P2/P3）

---

## Phase 1: Setup（共用資料來源）

- [X] T001 [P] 在 `frontend/src/lib/catalog-models.ts` 加一個 hook/util：查 `/catalog`（成員可見）→ 回 `Map<slug, {kind, displayName, supportsResponses}>`（`supportsResponses = responses_support.state === "available"`）。US1/US2 共用的 kind 來源（重用既有 catalog 查詢/快取，不新增端點）

**Checkpoint**: 有 slug→kind/responses 對照表——Foundational 可開工

---

## Phase 2: Foundational（阻塞 US1 + US2）

**⚠️ CRITICAL**: 共用 `UsageExplorer`（model 下拉 + `ApiUsageExample`）——US1 金鑰頁與 US2 應用卡都用它，未完成前兩者無法開工

- [X] T002 [P] vitest（先失敗）：`frontend/src/__tests__/usage-explorer.test.tsx`——給一組 models 顯下拉、選中顯範例（依 kind 餵 isEmbedding/isOcr/supportsResponses）、空清單顯提示
- [X] T003 建 `frontend/src/components/usage-explorer.tsx`：props `{ models: {slug,label,kind,supportsResponses}[]; emptyHint: string }`——渲染 model 下拉 + 選中 → `<ApiUsageExample model kind supportsResponses isEmbedding={kind==='embedding'} isOcr={kind==='ocr'} />`；空清單 → `emptyHint`；**重用既有 `ApiUsageExample`，不複製範例文本**

**Checkpoint**: 共用「下拉 + 範例」元件就緒——US1/US2 可獨立進行

---

## Phase 3: User Story 1 - 金鑰頁「如何使用這把金鑰」（Priority: P1）🎯 MVP

**Goal**: 每把金鑰旁就有「如何使用」，選一個（這把金鑰可用的）model → 即時可複製範例，不鑽詳情。

**Independent Test**: 有 1+ 可用 model 的金鑰 → 金鑰卡有「如何使用這把金鑰」→ 選 model → 範例正確（端點/slug/`$TOKEN`）。

### Tests for User Story 1 ⚠️（先寫、先失敗）

- [X] T004 [P] [US1] vitest：`frontend/src/__tests__/key-how-to-use.test.tsx`——金鑰卡顯「如何使用這把金鑰」；下拉列**該金鑰 scope 內 active 的 model**；兩把金鑰各自清單不混；選 embedding/ocr 顯對應端點；空 scope 顯提示

### Implementation for User Story 1

- [X] T005 [US1] `frontend/src/components/app-credentials-card.tsx`：每把金鑰卡加「**如何使用這把金鑰**」區——用既有 `credsQuery` 的 `cred.allocations`（`status==='active'`）取 scope model，join T001 的 catalog map 補 `kind`/`supportsResponses`/label → 餵 `UsageExplorer`
- [X] T006 [US1] `frontend/src/components/app-credentials-card.tsx`：顯眼標題 + base URL + `$TOKEN` 佔位提示（金鑰只顯示一次，範例不顯明文）；scope 無 active model → `emptyHint`（去領取/已被撤回）

**Checkpoint**: MVP 成立——成員在金鑰頁不鑽詳情就找得到怎麼用

---

## Phase 4: User Story 2 - 應用頁「直接用 API / SDK」卡（Priority: P2）

**Goal**: 應用頁成為「怎麼用」總站——工具卡 + 直接 API/SDK 卡。

**Independent Test**: 開 `/apps` → 同時有工具卡（Codex）與「直接用 API / SDK」卡；後者可選 model 顯範例。

### Tests for User Story 2 ⚠️（先寫、先失敗）

- [X] T007 [P] [US2] vitest：`frontend/src/__tests__/apps-direct-api.test.tsx`——應用頁有「直接用 API / SDK」tile + 工具卡；Direct API 詳情可選 model 顯範例

### Implementation for User Story 2

- [X] T008 [P] [US2] `frontend/src/components/app-logos.tsx`：加一個通用 API/code logo
- [X] T009 [US2] 建 `frontend/src/components/direct-api-detail.tsx`：成員可用 model（T001 catalog map 的全部成員可見 model）→ 餵 `UsageExplorer`
- [X] T010 [US2] `frontend/src/lib/applications.tsx`：註冊表加一筆 `{ id:"api", name:"直接用 API / SDK", blurb, Logo, Detail: DirectApiDetail }`（`apps.tsx` 自動多一張 tile + 詳情，註冊表驅動）

**Checkpoint**: US1 + US2——「怎麼用」有單一總站

---

## Phase 5: User Story 3 - 各處 cross-link 指過來（Priority: P3）

**Goal**: 儀表板/分配/模型詳情都看得到通往「如何使用 / 應用」的入口。

**Independent Test**: 三處各有一個通往「如何使用 / 應用」的明顯連結。

### Tests for User Story 3 ⚠️（先寫、先失敗）

- [X] T011 [P] [US3] vitest：`frontend/src/__tests__/usage-crosslinks.test.tsx`——儀表板（有金鑰待辦）、分配詳情、模型詳情各有通往「如何使用 / 應用」的連結

### Implementation for User Story 3

- [X] T012 [US3] `frontend/src/routes/dashboard.tsx`（或 `components/member-overview.tsx`）：「有金鑰了」待辦/快速接入加「**開始呼叫 → 如何使用**」連結（指金鑰頁/應用）
- [X] T013 [P] [US3] `frontend/src/routes/allocation-detail.tsx`：既有 `ApiUsageExample` 保留 + 加「**想接工具 → 看應用**」連結
- [X] T014 [P] [US3] `frontend/src/routes/catalog-detail.tsx`：同上（既有範例保留 + 「想接工具 → 看應用」連結）

**Checkpoint**: 三個 user story 全部獨立可用

---

## Phase 6: Polish & Cross-Cutting

- [X] T015 標籤/scent 檢查：入口與標題用白話、喊得出「怎麼用 / 開始呼叫」（FR-007），非僅靠「應用」一詞
- [X] T016 全綠關卡：`npx tsc --noEmit` + `npx vitest run` + `npx vite build` 綠；**確認零後端改動**（`git diff` 後端 `src/` 為空、無 migration）；範例**單一來源**（全程只有一個 `ApiUsageExample`，無重複範例文本，SC-006）
- [ ] T017 部署後煙霧（quickstart.md）：純前端只 bump frontend tag；金鑰頁選 model 看範例、應用「直接 API/SDK」卡、三處 cross-link 實際點過；找一位真成員試「拿到金鑰 → 不問人完成首呼」（SC-007 質性）

---

## Dependencies & Execution Order

- **Setup（T001）**：無依賴
- **Foundational（T002–T003）**：依賴 T001（catalog map）；**BLOCKS US1 + US2**（兩者都用 `UsageExplorer`）
- **US1（P1）/ US2（P2）/ US3（P3）**：US1/US2 依賴 Foundational；US3（cross-link）僅依賴「目的地存在」（US1/US2 的頁面），但連結本身可先放。三者落在**不同檔**，可並行
  - 建議順序 US1（MVP）→ US2 → US3
- **Polish（T015–T017）**：依賴所需 user story 完成

### Within Each User Story
- 測試先寫且先失敗 → 實作 → 重構
- 同 story 內：跨檔測試/元件標 [P]；改同一檔（`app-credentials-card.tsx`）的實作任務為順序

### Parallel Opportunities
- 各 story 測試任務（T004、T007、T011）標 [P] 可並行先寫
- T008（logo）/ T013 / T014 與其他不同檔，可並行
- 三個 user story 因落在不同檔（app-credentials-card / applications+direct-api / dashboard+detail），整體可並行推進

---

## Implementation Strategy

### MVP First（User Story 1）
1. Setup（T001）→ 2. Foundational（T002–T003 `UsageExplorer`）→ 3. US1（T004–T006 金鑰頁）→ **STOP & VALIDATE**（金鑰頁不鑽詳情可達、下拉=這把金鑰 model、範例正確＝MVP）→ 視情況先上線。

### Incremental Delivery
1. Setup + Foundational → 共用「下拉 + 範例」就緒
2. US1 → 金鑰頁「如何使用」（MVP，直接解學生痛）
3. US2 → 應用「怎麼用」總站
4. US3 → 各處 cross-link
5. Polish（標籤 + 全綠 + 部署煙霧）

### 零後端鐵證
- 後端 `src/` git diff 為空、無新 migration（純前端 + 既有 `/me/credentials`、`/catalog`）。

## Notes
- [P] = 不同檔、無依賴；改 `app-credentials-card.tsx` 同檔的實作任務為順序。
- **單一來源鐵律**：範例只有一個 `ApiUsageExample`，金鑰頁/應用卡/詳情頁全部餵它 props，不複製文本（experience「同一概念兩份必 drift」）。
- 改 UI 顯示字串要連帶更新 `frontend/src/__tests__` 斷言（experience「改字串要同步測試，否則 Frontend CI 紅」）。
- 純前端 → 部署只 bump `frontend.image.tag`（backend 維持上一個 sha）。
