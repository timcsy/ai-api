---
description: "Tasks for 階段 20 — scoped application credentials（憑證綁一組分配，M:N）"
---

# 任務清單：scoped application credentials（憑證 ↔ 分配 多對多）

**輸入文件**：`/specs/030-scoped-app-credentials/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/credentials.openapi.yaml](./contracts/credentials.openapi.yaml) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：後端先寫失敗測試（Red）再實作（Green）。**最高優先固化**：
① **既有單分配 token 零回歸**（migration 0017 後解析/呼叫/歸戶不變）
② 一 token 多 model **各自歸戶** + scope 外 **model_mismatch（0 計費）**
③ **擁有者邊界**（成員不得綁他人分配 / 碰他人 key）。schema 改/加 **必在 Postgres 整合測試驗**。

**鐵則**：額度/歸戶仍 per-allocation（不移到 token，FR-010）；token 仍 show-once + hash-only（FR-011）；
歸戶無歧義靠 `UNIQUE(credential_id, resource_model)`（FR-003）；`credentials` 被 `device_authorizations.credential_id`
（階段 19）FK 參照 → migration **in-place ALTER，不可 drop+rename 整表**。

**路徑慣例**：後端 `src/ai_api/`、`alembic/versions/`；測試 `tests/`；前端 `frontend/src/`

---

## Phase 1：Setup

- [X] T001 跑基準綠：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、
      `npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**不新增依賴**、下一個 migration 為 `0017`、
      盤點所有 `lookup_by_token` / `.allocation_id`（credential 相關）/ `Allocation.credentials` 的呼叫點（重構波及面）。

---

## Phase 2：Foundational（阻斷性：M:N schema + migration 0017 + proxy 解析 + 零回歸 = US3）

**⚠️ 所有 US 都依賴新模型；先把「換 schema + 改熱路徑而不破壞既有 token」做完。涵蓋 spec US3（零回歸）。**

### Tests First (Red)

- [X] T002 新增 `tests/integration/test_credential_migration_0017.py`（Postgres）：seed 舊式單分配憑證（含一筆 device_authorizations 參照該 credential）→ `alembic upgrade head` → 斷言 (a) 舊 token 仍 `lookup_credential_by_token` + 依其 model `resolve_scope_allocation` 解析到原分配；(b) `credential_allocations` 補了一列（credential, allocation, resource_model）；(c) `credentials.member_id` 補齊、`allocation_id` 欄已移除；(d) device_authorizations FK 並存無損。
- [X] T003 [P] 新增 `tests/contract/test_proxy_multimodel.py`：建立一把 scope=A+B 的憑證（service 層）→ 用該 token 打 model A 歸戶 A、打 B 歸戶 B；打 scope 外 C → `model_mismatch` 403 且 0 計費（先全 Red）。
- [X] T004 跑 T002–T003 確認 **全 Red**。

### Implementation (Green)

- [X] T005 改 `src/ai_api/models/credential.py`：移除 `allocation_id` + 其關係；加 `member_id`（FK members, NOT NULL）+ `member` 關係；`allocations` 經關聯表（list）。
- [X] T006 [P] 新增 `src/ai_api/models/credential_allocation.py`：`CredentialAllocation(credential_id, allocation_id, resource_model)`；`PK(credential_id, allocation_id)`、`UNIQUE(credential_id, resource_model)`、`INDEX(allocation_id)`；在 `models/__init__.py` 匯出。
- [X] T007 改 `src/ai_api/models/allocation.py`：`credentials` 反向關係改經 `credential_allocations`（仍回「scope 含此分配的 key」）。
- [X] T008 新增 `alembic/versions/0017_scoped_credentials.py`：**in-place**——建 `credential_allocations`；`credentials` 加 `member_id`（nullable）；raw SQL backfill（`member_id ← allocations.member_id`、`INSERT credential_allocations SELECT id, allocation_id, resource_model`）；`member_id` 設 NOT NULL；drop `credentials.allocation_id`（FK/index/欄）。SQLite 用 `batch_alter_table`、Postgres 原生；無循環 FK。
- [X] T009 改 `src/ai_api/services/allocations.py`：加 `lookup_credential_by_token(token) -> Credential | None`（fingerprint + `revoked_at IS NULL` + 節流 `last_used_at`）與 `resolve_scope_allocation(credential, model) -> Allocation | None`（查 `credential_allocations`）；既有 `lookup_by_token` 標 deprecated 或回 scope 第一筆（顯示相容）；`add_credential` 改 `(member_id, name, allocation_ids)`。
- [X] T010 改 `src/ai_api/proxy/preflight.py`（+ `proxy/auth.py`）：token→`lookup_credential_by_token`（None→401）→ `resolve_scope_allocation(cred, requested_model)`（None→`model_mismatch` 403）→ 之後 status/quota/access/billing **沿用既有、per-allocation 不變**；`proxy/guard.py` 退為防禦性 assert。
- [X] T011 改所有受波及 sink：`api/me.py`、`api/allocations.py`、`services/self_service.py`、`services/device_flow.py` 等對 `credential.allocation_id` / `lookup_by_token` 的引用，改用新模型（顯示點取 scope）。
- [X] T012 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**；`ruff` + `mypy` 零警告。

**Checkpoint**：新 M:N 模型 + proxy 解析上線、既有 token/領取/計費零回歸。可進 US1。

---

## Phase 3：US1 — 一把應用 key 用多個 model（P1）🎯 MVP

**目標**：成員建立具名 key、勾選多筆分配，一 token 用多 model。

### Tests First (Red)

- [X] T013 [US1] 新增 `tests/contract/test_scoped_credentials.py`：`POST /me/credentials`（name + allocation_ids=[A,B]）→ 201 回明文一次 + scope；該 token 打 A、B 皆 200；`GET /me/credentials` 回成員所有 key、**不含明文**。
- [X] T014 [P] [US1] 同檔加：scope 內 model 重複 → 409；scope 含**他人**分配 → 403、不建立。
- [X] T015 [US1] 跑 T013–T014 確認 **全 Red**。

### Implementation (Green)

- [X] T016 [US1] 在 `src/ai_api/services/allocations.py` 完成 `add_credential(member, name, allocation_ids)`（驗每筆擁有者 + model 不重複 → 建 credential + 關聯）與 `list_member_credentials(member_id)`。
- [X] T017 [US1] 在 `src/ai_api/api/me.py` 加 `GET /me/credentials`、`POST /me/credentials`（`current_member` + CSRF；schema 對齊 contract，回 `AppCredentialCreated`）。
- [X] T018 [US1] 跑 T013–T014 確認 **全 Green**。
- [X] T019 [P] [US1] 前端：`frontend/src/components/app-credentials-card.tsx`（由 `device-credentials-card.tsx` 演進為成員層）——列出我的 key（名稱/可用 model/狀態/最後使用）+「建立」(命名 + **多選分配** + 一次性遮罩複製)；接進 `routes/dashboard.tsx`。
- [X] T020 [P] [US1] 前端 vitest：`frontend/src/__tests__/app-credentials-card.test.tsx` 驗清單 + 多選建立 + 複製內容；lint/typecheck/build 綠。

---

## Phase 4：US2 — 依 model 歸戶；scope 外被拒（P1）

**目標**：用真 token 端到端固化多 model 歸戶與邊界（實作多在 Foundational，本段補端到端契約）。

### Tests First (Red)

- [X] T021 [US2] 在 `tests/contract/test_proxy_multimodel.py` 加端到端：經 `/me/credentials` 建 A+B 的 token → `/v1/chat/completions` 打 A → `/me/usage`/呼叫紀錄歸戶 A、打 B 歸戶 B；打 C → 403 `model_mismatch`、無紀錄。
- [X] T022 [US2] 跑 T021 確認 **Red**（若 Foundational 已使其 Green，補齊缺口直到涵蓋歸戶斷言）。

### Implementation (Green)

- [X] T023 [US2] 確認/補 `preflight.py` 在 reject（model_mismatch）時**不寫計費紀錄**、在 success 時把 CallRecord 綁解析出的分配；跑 T021 確認 **Green**。

---

## Phase 5：US4 — 調整 scope + 撤回 / rotate（P2）

**目標**：對既有 key 增刪可用分配、撤回、rotate，即時生效、留稽核。

### Tests First (Red)

- [X] T024 [US4] 在 `tests/contract/test_scoped_credentials.py` 加：`PATCH /me/credentials/{id}`（add B）→ 同 token 立刻能打 B；（remove A）→ 立刻不能打 A、仍能打 B；移除至 0 → 409。`DELETE` → 其所有 model 失效、其他 key 不受影響。`POST .../rotate` → 換 token、scope 不變、舊失效。
- [X] T025 [US4] 跑 T024 確認 **Red**。

### Implementation (Green)

- [X] T026 [US4] 在 `src/ai_api/services/allocations.py` 加 `patch_credential_scope(credential_id, add, remove)`（驗擁有者 + model 不重複 + 不得到 0）、`revoke_credential`（沿用 + 連帶停用關聯解析）、`rotate_credential`（scope 不變）；皆寫稽核（`credential_scope_added`/`removed`、`credential_revoked`，VARCHAR enum 免 migration）。
- [X] T027 [US4] 在 `src/ai_api/api/me.py` 加 `PATCH /me/credentials/{id}`、`DELETE /me/credentials/{id}`、`POST /me/credentials/{id}/rotate`（擁有者 + CSRF）。
- [X] T028 [US4] 跑 T024 確認 **Green**。
- [X] T029 [P] [US4] 前端：`app-credentials-card.tsx` 每把加「編輯可用分配（多選）/ 撤回 / 重新產生」；撤回/rotate 沿用一次性遮罩；即時更新。

---

## Phase 6：US5 — admin 治理；成員自助只限自己的分配（P2）

**目標**：admin 管理任一成員的 key 與 scope；成員不可碰他人。

### Tests First (Red)

- [X] T030 [US5] 新增 `tests/contract/test_credential_owner_isolation.py`：成員對**他人** key 的 GET/PATCH/DELETE → 403/404；成員 patch 加**他人**分配 → 403。`GET /admin/members/{id}/credentials` 列出；`DELETE/PATCH /admin/credentials/{id}` 改/撤 → 留稽核；未認證 → 401。
- [X] T031 [US5] 跑 T030 確認 **Red**。

### Implementation (Green)

- [X] T032 [US5] 新增 `src/ai_api/api/credentials.py`（admin）：`GET /admin/members/{id}/credentials`、`DELETE`/`PATCH /admin/credentials/{id}`（複用 service，撤/改寫稽核）；於 `main.py` `include_router`（`/admin` prefix）。
- [X] T033 [US5] 跑 T030 確認 **Green**。
- [X] T034 [P] [US5] 前端：`frontend/src/routes/admin/member-detail.tsx`（或 allocations）加某成員的 app key 清單 + 撤回/改 scope；lint/typecheck/build 綠。

---

## Phase 7：US6 — Codex device-flow 多選 + 收尾 A（P2）

**目標**：device-flow 勾選多分配建一把 key；移除舊 Codex 分頁、單一 Codex 安裝來源。

### Tests First (Red)

- [X] T035 [US6] 新增 `tests/contract/test_device_multi_alloc.py`：`POST /me/device/{code}/approve {allocation_ids:[A,B]}` → mint 一把 scope=A+B 的 key；`/device/token` 取回 token → 打 A、B 皆通；含他人分配 → 403。
- [X] T036 [US6] 跑 T035 確認 **Red**。

### Implementation (Green)

- [X] T037 [US6] 改 `src/ai_api/services/device_flow.py` + `src/ai_api/api/me.py` approve：body `allocation_ids`（≥1，逐筆驗擁有者）→ `add_credential(member, device_label, allocation_ids)`；`/device/token` 成功回應附 scope 的 model 清單。
- [X] T038 [US6] 跑 T035 確認 **Green**。
- [X] T039 [P] [US6] 前端：`frontend/src/routes/device-authorize.tsx` 分配選單改**多選 checkbox**；安裝腳本樣板 `src/ai_api/install/codex.{sh,ps1}.tmpl` 寫入預設 `model = "<scope 首選>"`。
- [X] T040 [P] [US6] 前端：**移除** `frontend/src/components/api-usage-example.tsx` 的 Codex 分頁（收尾 A）；確認全站只剩一處 Codex 安裝（dashboard 一行指令卡）；改相關測試。

---

## Phase 8：Polish 與跨領域

- [X] T041 跑 `uv run pytest tests/` 全套零回歸（M:N + 既有 token/proxy/計費/配額/device-flow，SC-004/007）；`ruff check . && mypy src/` 零警告。
- [X] T042 前端：`allocation-detail.tsx` 原 per-allocation 憑證卡改唯讀「哪些 app key 含此分配」+「用此分配建 app key」捷徑；`npm --prefix frontend run test && lint && typecheck && build` 綠；清單/建立面板 **360px** 不溢出（沿用階段 16 RWD）。
- [X] T043 [P] 更新 `knowledge/vision.md` 階段 20 → ✅（完成日、實際交付、連結 history）；`knowledge/history/completed-phases-detail.md` 追加「## 階段 20」（M:N、migration 0017、proxy 解析、收尾 A）；若有新教訓補 `knowledge/experience.md`。
- [X] T044 commit + push + 開 PR；push 前 `ruff check .` + 前端 build；**特別檢視 migration 0017（in-place + device_authorizations FK 並存）與 proxy 熱路徑**；等 CI 全綠後 squash merge 到 main。
- [X] T045 main image build 綠後 `helm upgrade`（同既有指令 + `--set migrationJob.enabled=true` 套 0017 + 新 sha）；live 驗：**既有舊 token 仍可呼叫**、建一把多 model key 打多 model、撤一把不連坐。
- [X] T046 收尾：vision 階段 20 改 ✅、history 補上、roadmap 一致；標記 tasks 全完成。

---

## 依賴與順序

```text
Phase 1 (Setup)
   ↓
Phase 2 (Foundational：M:N schema + migration 0017 + proxy 解析 + 零回歸=US3) ← 阻斷
   ↓
Phase 3 (US1 建多 model key) ── MVP
   ↓
Phase 4 (US2 歸戶+邊界 端到端)  ← 實作多在 Foundational
   │
Phase 5 (US4 scope 編輯/撤回/rotate)
   │
Phase 6 (US5 admin 治理 + owner isolation)
   │
Phase 7 (US6 device-flow 多選 + 收尾 A)
   ↓
Phase 8 (Polish：全測 + 前端升層 + 文件 + 部署含 migration)
```

**MVP**：Foundational（換模型零回歸）+ US1（建多 model key、一 token 多 model）即首個價值。US2 端到端固化、US4/US5/US6 接力。

**[P] 並行**：T003（與 T002）、T006；US1 的 T014/T019/T020；US4 的 T029；US5 的 T034；US6 的 T039/T040；Polish 的 T043。

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 Foundational（含 US3 零回歸） | 11 | 3 |
| 3 US1（P1，MVP） | 8 | 3 |
| 4 US2（P1） | 3 | 2 |
| 5 US4（P2） | 6 | 2 |
| 6 US5（P2） | 5 | 2 |
| 7 US6（P2） | 6 | 2 |
| 8 Polish | 6 | 0 |
| **總計** | **46** | **14** |

---

## 格式檢核

- ✅ `- [ ] T###` 開頭、含 ID、描述、檔案路徑；Setup/Foundational/Polish 無 Story 標；US1–US6 含 `[US#]`
- ✅ 可並行標 `[P]`
- ✅ TDD：每段 Tests First → Red → 實作 → Green；最高優先固化既有 token 零回歸 + 多 model 歸戶/邊界 + 擁有者隔離；migration 在 Postgres 驗

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
