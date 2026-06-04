---
description: "Tasks for 階段 18 — 憑證模型重構（每分配多 per-device 憑證）"
---

# 任務清單：憑證模型重構（每分配多 per-device 憑證）

**輸入文件**：`/specs/028-per-device-credentials/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/credentials.openapi.yaml](./contracts/credentials.openapi.yaml) /
[quickstart.md](./quickstart.md)

**測試（憲章 TDD）**：後端先寫失敗測試（Red）再實作（Green）。**最高優先固化**：
①**既有 token 零回歸**（migration 後舊 token 仍解析/呼叫）②**撤回不連坐**③**owner-isolation**。
改主鍵的 migration **必在 Postgres 整合測試驗**。

**鐵則**：既有 token 零回歸（FR-004）、撤回不連坐（FR-002）、跨成員隔離（FR-005）、額度/歸戶在分配層不變（FR-003/010）。

**路徑慣例**：後端 `src/ai_api/`、`alembic/versions/`；測試 `tests/`；前端 `frontend/src/`

---

## Phase 1：Setup

- [X] T001 跑基準綠（實作前對照）：`uv run pytest tests/ -q`、`uv run ruff check .`、`uv run mypy src/`、
      `npm --prefix frontend run test && lint && typecheck && build` 全綠；確認**不新增依賴**、下一個 migration 為 `0015`

---

## Phase 2：Foundational（阻斷性前置：1:N schema + migration + 零回歸）

**⚠️ 所有 US 都依賴新的 1:N 憑證模型；先把「換 schema 不破壞既有」做完。**

### Tests First (Red)

- [X] T002 新增 `tests/integration/test_credential_migration.py`（Postgres）：seed「舊式」資料（一分配一憑證）→ 跑
      `alembic upgrade head` → 斷言 (a) 該舊 token 仍能 `lookup_by_token` 解析到同一分配；(b) 該分配現有一把 `name="預設"` 的憑證
- [X] T003 [P] 同檔加 `test_multi_credential_lookup_and_revoke`：同分配建多把 → 各 fingerprint 解析到同分配；對一把設 `revoked_at` →
      該把解析不到、其他仍可（service/DB 層）
- [X] T004 跑 T002–T003 確認 **全 Red**

### Implementation (Green)

- [X] T005 改 `src/ai_api/models/credential.py`：主鍵改獨立 `id`（ULID）、`allocation_id` 改一般 FK + 索引（非唯一）、
      加 `name`/`last_used_at`（nullable）/`revoked_at`（nullable）；`token_fingerprint` 維持唯一
- [X] T006 改 `src/ai_api/models/allocation.py`：`credential`（scalar）→ `credentials`（list）；相關 `selectinload` 調整
- [X] T007 新增 `alembic/versions/0015_per_device_credentials.py`：以 `batch_alter_table` 重建 `credentials`（id PK、allocation_id FK+索引、
      加三欄、fingerprint 唯一）；**既有每列補 `id`(新 ULID) + `name="預設"`、token_fingerprint/prefix/created_at 原樣搬**（既有 token 不失效）
- [X] T008 改 `src/ai_api/services/allocations.py`：`lookup_by_token` 加 `revoked_at IS NULL`（fingerprint 唯一 → 仍 1 把命中 → 回 allocation）；
      成功驗證時**節流更新** `last_used_at`（距上次 > 5 分鐘才寫）
- [X] T009 改 `src/ai_api/services/allocations.py` 既有 sink：建立分配（admin + 自助 `services/self_service.py`）時建**第一把**具名憑證
      （`name="預設"`）；`rotate_token` 改為 per-credential 語意（撤該把 + 發新把）；不破壞既有 `/me/.../rotate-token` 與 admin rotate
- [X] T010 改 `src/ai_api/api/schemas.py` 與顯示點（`api/me.py`、`api/allocations.py`、前端讀 `token_prefix` 處）：適配「一分配多憑證」
      （原讀單一 credential 改為憑證清單；分配詳情顯示改對應）
- [X] T011 跑 T002–T003 + 既有全套 `uv run pytest tests/` 確認 **全 Green、零回歸**

**Checkpoint**：新 schema 上線、既有 token/領取/計費零回歸。可進 US1–US3。

---

## Phase 3：US1 — 為多裝置各發一把具名憑證（P1）🎯 MVP

**目標**：成員自助對一分配新增多把具名憑證，每把可呼叫、皆歸該分配。

### Tests First (Red)

- [X] T012 [US1] 新增 `tests/contract/test_me_credentials.py::test_add_credential_returns_token_once_and_callable`：POST
      `/me/allocations/{id}/credentials`（name）→ 回明文一次 + prefix；該 token 可成功打 proxy
- [X] T013 [P] [US1] 同檔加 `test_multiple_credentials_bill_same_allocation`：再加一把 → 兩把都能呼叫、用量皆歸該分配；
      `test_list_credentials_no_plaintext`（GET 不含明文）
- [X] T014 [US1] 跑 T012–T013 確認 **全 Red**

### Implementation (Green)

- [X] T015 [US1] 在 `src/ai_api/services/allocations.py` 加 `add_credential(allocation, name) -> GeneratedToken`（show-once）與 `list_credentials(allocation)`
- [X] T016 [US1] 在 `src/ai_api/api/me.py` 加 `POST /me/allocations/{id}/credentials`（`current_member` 擁有者檢查、回 `CredentialCreated`）
      與 `GET /me/allocations/{id}/credentials`（回不含明文的清單），schema 對齊 contract
- [X] T017 [US1] 跑 T012–T013 確認 **全 Green**
- [X] T018 [P] [US1] 前端：在分配詳情/dashboard 加「我的裝置/憑證」清單 + 「新增裝置」（複用**遮罩 + 一鍵複製**面板，顯示一次）；
      `frontend/src/routes/allocation-detail.tsx`（或 dashboard 對應元件）
- [X] T019 [P] [US1] 前端 vitest：`frontend/src/__tests__/credential-list.test.tsx` 驗清單渲染 + 新增面板複製內容；跑 lint/typecheck/build 綠

---

## Phase 4：US2 — 逐把獨立撤回、不連坐（P1）

**目標**：撤回某一把，立即失效、同分配其他照常可用；成員不得撤他人的。

### Tests First (Red)

- [X] T020 [US2] 在 `tests/contract/test_me_credentials.py` 加 `test_revoke_one_does_not_affect_others`：一分配 A、B 兩把 →
      DELETE A → A 呼叫被拒、B 仍成功
- [X] T021 [P] [US2] 同檔加 `test_revoke_owner_isolation`：成員對**他人**分配/憑證 GET/POST/DELETE → 403
- [X] T022 [US2] 跑 T020–T021 確認 **全 Red**

### Implementation (Green)

- [X] T023 [US2] 在 `src/ai_api/services/allocations.py` 加 `revoke_credential(credential_id)`（軟撤回：設 `revoked_at`，被撤即排除 lookup）
- [X] T024 [US2] 在 `src/ai_api/api/me.py` 加 `DELETE /me/allocations/{id}/credentials/{cid}`（擁有者檢查；非本人 → 403、不存在 → 404）
- [X] T025 [US2] 跑 T020–T021 確認 **全 Green**
- [X] T026 [P] [US2] 前端：清單每把加「撤回」+ 顯示 `last_used_at`/狀態；撤回後即時更新；跑 lint/typecheck/build 綠

---

## Phase 5：US3 — 管理員可見並撤回成員所有憑證（P2）

**目標**：admin 列出某分配所有憑證並逐把撤回，留稽核。

### Tests First (Red)

- [X] T027 [US3] 新增 `tests/contract/test_admin_credentials.py`：`GET /admin/allocations/{id}/credentials` 列出全部；
      `DELETE .../{cid}` 撤一把 → 該把失效、其他不受影響、**留稽核事件**；未認證 → 401
- [X] T028 [US3] 跑 T027 確認 **全 Red**

### Implementation (Green)

- [X] T029 [US3] 在 `src/ai_api/api/allocations.py` 加 admin `GET`/`DELETE /admin/allocations/{id}/credentials[/{cid}]`（複用 `list/revoke_credential`，撤回寫稽核）
- [X] T030 [US3] 跑 T027 確認 **全 Green**
- [X] T031 [P] [US3] 前端：`frontend/src/routes/admin/allocations.tsx`（或分配詳情）加某成員憑證清單 + 逐把撤回；跑 lint/typecheck/build 綠

---

## Phase 6：Polish 與跨領域

- [X] T032 跑 `uv run pytest tests/` 全套確認零回歸（既有 token/領取/計費/配額 + 新測試全綠，SC-006）
- [X] T033 跑 `uv run ruff check . && uv run mypy src/` 零警告
- [X] T034 跑 `npm --prefix frontend run test && lint && typecheck && build`；裝置清單 + 新增面板在 **360px 手機**不溢出（沿用階段 16 RWD）
- [X] T035 [P] 更新 `knowledge/vision.md` 階段 18 → ✅（填完成日、列實際交付、連結 history）；roadmap/狀態同步
- [X] T036 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 18：憑證模型重構」詳情（schema 1:1→1:N、migration 0015、零回歸保證）
- [ ] T037 commit + push + 開 PR；push 前先 `ruff check .` + 前端 lint/build；**特別檢視 migration**；等 CI 全綠後 squash merge 到 main
- [ ] T038 main image build 綠後 `helm upgrade`（同既有指令 + 新 sha）；**確認 migration 0015 在部署套用**；live 驗：既有成員的舊 token **仍可呼叫**、可新增一把/撤一把
- [ ] T039 收尾：vision 階段 18 改 ✅、history 補上、roadmap 狀態一致；標記 tasks 全完成

---

## 依賴與順序

```text
Phase 1 (Setup)
   ↓
Phase 2 (Foundational：1:N schema + migration 0015 + lookup + 適配既有 sink + 零回歸測試) ← 阻斷
   ↓
Phase 3 (US1 新增憑證) ── MVP
   │
Phase 4 (US2 撤回不連坐) ── 依 US1 的清單/service
   │
Phase 5 (US3 admin 管理) ── 依 service add/revoke/list
   ↓
Phase 6 (Polish：全測/RWD + 文件 + 部署（含 migration）)
```

**MVP**：Foundational（零回歸換 schema）+ US1（新增多裝置憑證）即首個價值。US2/US3 接力。

**[P] 並行機會**：US1 的 T013/T018/T019；US2 的 T021/T026；US3 的 T031；Polish 的 T035/T036。

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 Foundational | 10 | 3 |
| 3 US1（P1，MVP） | 8 | 3 |
| 4 US2（P1） | 7 | 2 |
| 5 US3（P2） | 5 | 2 |
| 6 Polish | 8 | 0 |
| **總計** | **39** | **10** |

---

## 格式檢核

- ✅ `- [ ] T###` 開頭、含 ID、描述、檔案路徑；Setup/Foundational/Polish 無 Story 標；US1–US3 含 `[US#]`
- ✅ 可並行標 `[P]`
- ✅ TDD：每段 Tests First → Red → 實作 → Green；最高優先固化既有 token 零回歸 + 撤回不連坐 + owner-isolation；migration 在 Postgres 驗

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
