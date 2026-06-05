---
description: "Tasks for 階段 21 — 憑證 UI 術語與層級收斂（統一「應用金鑰」、單一管理處、可改名）"
---

# 任務清單：憑證 UI 術語與層級收斂

**輸入文件**：`/specs/031-credential-ui-consolidation/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/rename.openapi.yaml](./contracts/rename.openapi.yaml) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：改名端點先寫失敗 contract（Red）再實作（Green）；前端關鍵互動以 vitest 固化。

**鐵則**：**不改資料模型、不新增 migration**；改名只改標籤——**不影響 token / 可用 model（scope）/ 狀態 / 歸戶**；
既有 proxy / 計費 / 領取 / token **零回歸**；分配詳情金鑰區降唯讀以**消除無聲連坐**。

**路徑慣例**：後端 `src/ai_api/`；前端 `frontend/src/`；測試 `tests/`、`frontend/src/__tests__/`

---

## Phase 1：Setup

- [X] T001 跑基準綠：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、
      `npm --prefix frontend run test && lint && typecheck && build` 全綠；`grep -rn "裝置" frontend/src` 盤點待改字眼；
      確認 `/me/credentials` 回的每把含 `allocations`（全部可用 model，分配詳情唯讀清單要用）。

---

## Phase 2：US2 — 應用金鑰可改名（後端，P1）

**目標**：member/admin 可改金鑰名稱（含「預設」），不影響 token / 可用 model；留稽核。**先做，因 US1 改名 UI 依賴此端點。**

### Tests First (Red)

- [X] T002 [US2] 新增 `tests/contract/test_credential_rename.py`：`PATCH /me/credentials/{id}`（`{name}`）→ 名稱變、該 token 仍可呼叫、可用 model 不變；`{name, add, remove}` 同送兩者皆生效；空/超長名 → 422/400。
- [X] T003 [P] [US2] 同檔加：成員改**他人**金鑰名 → 404/403；admin `PATCH /admin/credentials/{id}`（`{name}`）→ 200 + 留稽核 `credential_renamed`。
- [X] T004 [US2] 跑 T002–T003 確認 **全 Red**。

### Implementation (Green)

- [X] T005 [US2] 在 `src/ai_api/api/schemas.py` 的 `ScopePatchRequest` 加選填 `name`（沿用名稱長度上限 `CredentialNameStr`）。
- [X] T006 [US2] 在 `src/ai_api/models/auth_audit.py` 加 `credential_renamed`（VARCHAR enum，免 migration）。
- [X] T007 [US2] 在 `src/ai_api/services/allocations.py` 加 `rename_credential(credential_id, name)`（或 `patch_credential_scope` 接 `name`）——只改 `Credential.name`，不碰 token/scope。
- [X] T008 [US2] 改 `src/ai_api/api/me.py` `PATCH /me/credentials/{id}`：若帶 `name` → 改名 + 稽核（actor=member）；與 scope add/remove 並行。
- [X] T009 [US2] 改 `src/ai_api/api/credentials.py` admin `PATCH /admin/credentials/{id}`：若帶 `name` → 改名 + 稽核（actor=admin）。
- [X] T010 [US2] 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**；`ruff` + `mypy` 清。

---

## Phase 3：US1 — 一物一名「應用金鑰」+ 單一管理處 + 改名 UI（P1）🎯 MVP

**目標**：全站對此物件只稱「應用金鑰」；建立/改名/改 model/rotate/撤回只在 dashboard 金鑰卡。

### Implementation

- [X] T011 [US1] 改 `frontend/src/components/app-credentials-card.tsx`：每把加「**改名**」（就地編輯 → `PATCH /me/credentials/{id}` `{name}`，成功 invalidate）；卡標題/文案統一「應用金鑰」。
- [X] T012 [P] [US1] 前端 vitest：`frontend/src/__tests__/app-credentials-card.test.tsx` 加改名互動（改名送出 + 清單更新）。
- [X] T013 [P] [US1] 術語統一：`frontend/src/routes/device-authorize.tsx`、`frontend/src/components/codex-install-card.tsx` 把「裝置/憑證」對此物件的稱呼改「應用金鑰」；安裝卡加「會在你的應用金鑰新增一把」。

---

## Phase 4：US3 — 分配詳情降唯讀、消除無聲連坐（P1）

**目標**：model 詳情頁金鑰區唯讀、顯示每把全部 model、連本尊；不在此撤回/新增。

### Implementation

- [X] T014 [US3] 新增 `frontend/src/components/allocation-keys-readonly.tsx`：讀 `/me/credentials`（前端 filter「scope 含此 allocation」）→ 唯讀列出「能用此 model 的應用金鑰」，每筆顯示**全部**可用 model（badge）+「前往管理」連 dashboard 金鑰卡；無撤回/新增/rotate。
- [X] T015 [US3] 改 `frontend/src/routes/allocation-detail.tsx`：`DeviceCredentialsCard` → `AllocationKeysReadonly`。
- [X] T016 [US3] 改 `frontend/src/routes/admin/allocations.tsx`：移除「查看裝置憑證」dropdown 項 + dialog（治理改走成員頁）。
- [X] T017 [P] [US3] 前端 vitest：`frontend/src/__tests__/allocation-keys-readonly.test.tsx` 驗唯讀清單渲染（顯示全部 model、無管理鍵、有「前往管理」連結）。

---

## Phase 5：US4 — 撤回明示連坐 + admin 治理移成員頁 + 安裝接續（P2）

**目標**：撤回確認明示會一起失效的 model；admin 在成員層治理金鑰。

### Implementation

- [X] T018 [US4] 改 `frontend/src/components/app-credentials-card.tsx` 撤回確認文案：明示「此金鑰涵蓋的 N 個 model（列出）會一起失效」。
- [X] T019 [US4] 改 `frontend/src/routes/admin/member-detail.tsx`：加**唯讀應用金鑰清單**（`GET /admin/members/{id}/credentials`）+ 撤回（`DELETE /admin/credentials/{id}`）+ 改名（`PATCH /admin/credentials/{id}` `{name}`）；用語「應用金鑰」。
- [X] T020 [P] [US4] 前端 vitest：admin 成員金鑰清單渲染 + 撤回/改名呼叫（`frontend/src/__tests__/admin-member-credentials.test.tsx`）。
- [X] T021 [US4] 退役 `frontend/src/components/device-credentials-card.tsx` 的管理用途：確認已無 import 後刪除元件；改寫/移除 `frontend/src/__tests__/credential-list.test.tsx`。

---

## Phase 6：Polish 與跨領域

- [X] T022 全站術語收尾：`grep -rn "裝置" frontend/src`（排除 device-flow 內部 API/變數）對使用者可見文字皆為「應用金鑰」；無殘留。
- [X] T023 跑 `uv run pytest tests/` 全套零回歸（含改名 + 既有 proxy/計費/token，SC-006）；`uv run ruff check . && uv run mypy src/` 零警告。
- [X] T024 前端 `npm --prefix frontend run test && lint && typecheck && build` 綠；金鑰卡 + 唯讀清單 + admin 清單在 **360px** 不溢出（沿用階段 16 RWD）。
- [X] T025 [P] 更新 `knowledge/vision.md` 階段 21 → ✅（完成日、實際交付）；`knowledge/history/completed-phases-detail.md` 追加「## 階段 21」（術語統一、單一管理處、降唯讀、改名）。
- [X] T026 commit + push + 開 PR；push 前 `ruff check .` + 前端 build；等 CI 全綠後 squash merge 到 main。
- [ ] T027 main image build 綠後 `helm upgrade`（同既有指令 + 新 sha；本階段**無 migration**）；live 驗：改名、分配詳情唯讀、撤回明示連坐、admin 成員金鑰治理。
- [ ] T028 收尾：vision 階段 21 改 ✅、history 補上、roadmap 一致；標記 tasks 全完成。

---

## 依賴與順序

```text
Phase 1 (Setup)
   ↓
Phase 2 (US2 改名後端) ← US1 改名 UI 依賴
   ↓
Phase 3 (US1 一物一名 + 改名 UI) ── MVP
   │
Phase 4 (US3 分配詳情降唯讀)
   │
Phase 5 (US4 撤回明示 + admin 治理 + 退役舊卡)
   ↓
Phase 6 (Polish：全測 + RWD + 文件 + 部署)
```

**MVP**：US2（改名後端）+ US1（一物一名 + 改名 UI）即首個價值。US3 消連坐、US4 收尾。

**[P] 並行**：T003；US1 的 T012/T013；US3 的 T017；US4 的 T020；Polish 的 T025。

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 US2（改名後端，P1） | 9 | 3 |
| 3 US1（P1，MVP） | 3 | 1 |
| 4 US3（P1） | 4 | 1 |
| 5 US4（P2） | 4 | 1 |
| 6 Polish | 7 | 0 |
| **總計** | **28** | **6** |

---

## 格式檢核

- ✅ `- [ ] T###` 開頭、含 ID、描述、檔案路徑；Setup/Polish 無 Story 標；US1–US4 含 `[US#]`
- ✅ 可並行標 `[P]`
- ✅ TDD：改名端點 Tests First → Red → Green；前端互動 vitest；既有全套零回歸把關

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
