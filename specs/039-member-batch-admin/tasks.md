# Tasks: 管理員成員管理批次化 + 安全刪除

**Feature**: `039-member-batch-admin` | **Input**: plan.md / spec.md / research.md / data-model.md / contracts/member-admin.md / quickstart.md

**測試策略**：Constitution I（Test-First, NON-NEGOTIABLE）→ 安全刪除連帶（含 CallRecord 孤兒保留）、批次逐筆摘要、防呆守衛、前端多選/批次/新建摘要，皆**先寫失敗測試再實作**。

**路徑慣例**：後端 `src/ai_api/`、測試 `tests/`、前端 `frontend/src/`（皆 repo root 相對）。

**核心約束（research）**：連帶刪除走**服務層 ORM 顯式**、不靠 DB ondelete（SQLite 測試未開 FK pragma）；批次**逐筆獨立成敗、不整批回滾**；守衛（self / last-admin）放服務層。**零 migration、零套件、零新 enum**。

---

## Phase 1: Setup

- [X] T001 確認分支與基線：`cd /Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api && python -m pytest tests/contract/test_member*.py tests/contract/test_admin*.py -q && ruff check src/ai_api` 綠（改動前基準）；確認 `alembic heads` = `0018`（本功能不應變動）。

---

## Phase 2: Foundational

> 本功能無跨 story 的獨立共用前置：US1 的「安全刪除服務」即是 US2 所依賴的基礎，故併入 US1。US3（批次新建）與 US1/US2 獨立。直接進 US1。

---

## Phase 3: User Story 1 — 安全刪除單一成員（P1）🎯 MVP

**Goal**：`DELETE /admin/members/{id}` 由「有分配就擋下」升級為「安全刪除」——撤分配 + 刪憑證/連結 + CallRecord 轉孤兒保留 + 刪成員，單一交易；含防呆守衛。

**Independent Test**：有 active 分配（且有 CallRecord）的成員 → 刪除成功（204）、CallRecord 仍在且 `allocation_id IS NULL`；刪自己 → 403；最後一位 admin → 409。

- [X] T002 [P] [US1] 寫 `tests/integration/test_member_safe_delete.py`（先失敗）：seed 一位成員 + 1 active 分配 + 該分配下數筆 `CallRecord` + 一把綁該分配的 credential（+ credential_allocation）。呼叫 `MemberService(s).delete(member_id, acting_admin_id=...)`（新簽章）→ 斷言：成員不存在、該成員所有 `Allocation`/`Credential`/`CredentialAllocation` rows 已刪、**`CallRecord` rows 仍存在且 `allocation_id IS NULL`、`subject` 不變**、寫了一筆 `member_deleted` 稽核。另測無分配成員 → 直接刪成功（回歸）。
- [X] T003 [P] [US1] 寫 `tests/contract/test_member_batch_admin.py`（先失敗，US1 部分）：`DELETE /admin/members/{id}` —— (a) 有分配成員 → 204 + 事後 GET 該成員 404、且其 CallRecord（查 DB 或用量端點）仍在；(b) 刪自己（當前 admin 的 member_id）→ 403 `cannot_delete_self`；(c) 系統僅一位 admin 時刪該 admin → 409 `last_admin`；(d) 不存在 → 404；(e) 無 admin session → 401/403。
- [X] T004 [US1] 升級 `src/ai_api/services/members.py` 的 `delete`：改名/擴充為安全刪除（簽章加 `acting_admin_id`）。在**單一交易**內依序：守衛（self → `CannotDeleteSelf`、last-active-admin → `LastAdmin`）→ 撤回 active 分配（沿用 `AllocationService.revoke` 語意/稽核）→ `UPDATE call_records SET allocation_id=NULL WHERE allocation_id IN (該成員分配)` → 刪 `credential_allocations` → 刪 `credentials` → 刪 `allocations` → 刪 `member` → 寫 `member_deleted` 稽核。**全程 ORM 顯式、不靠 DB cascade**（research R1）。移除舊的 `MemberHasActiveAllocations` 擋阻。
- [X] T005 [US1] 改 `src/ai_api/api/admin_members.py` 的 `DELETE /members/{member_id}`：傳入當前 admin id；對映新例外 → `CannotDeleteSelf`→403、`LastAdmin`→409、not found→404；成功 204。令 T002/T003 轉綠。
- [X] T006 [US1] 改 `frontend/src/routes/admin/members.tsx`：單筆「刪除」確認對話框升級，先抓該成員分配/憑證數，顯示「將移除 N 筆分配、M 把憑證；正在使用的金鑰會立即失效；過往用量會保留供稽核」；成功後 invalidate 成員列表 query。
- [X] T007 [P] [US1] 寫 `frontend/src/__tests__/members-batch.test.tsx`（先失敗，US1 部分）：單筆刪除確認對話框顯示連帶影響文案（分配/憑證數、金鑰立即失效、用量保留）。

**Checkpoint**：US1 可獨立驗收（有分配的成員可一鍵安全刪除 = MVP，痛點解除）。

---

## Phase 4: User Story 2 — 批次刪除多位成員（P2）

**Goal**：多選成員 → `POST /admin/members/bulk-delete` 逐筆套 US1 安全刪除，逐筆獨立成敗、回摘要。

**Independent Test**：選 4 位（含 1 位會觸發守衛）→ 200 + results 逐筆分類；未選者不受影響。

- [X] T008 [US2] 擴充 `tests/contract/test_member_batch_admin.py`（先失敗，US2 部分）：`POST /admin/members/bulk-delete` —— (a) 混合 ids（2 可刪 + 1 刪自己 + 1 不存在）→ 200、`deleted==2`、`failed==2`、results 逐筆 `status`/`reason` 正確（`cannot_delete_self`/`not_found`）；(b) 其中一位的失敗不影響其他位實際被刪；(c) 空 `member_ids` → 400 `bad_request`；(d) 無 admin → 401/403。
- [X] T009 [US2] 在 `src/ai_api/api/admin_members.py` 新增 `POST /members/bulk-delete`：驗 `member_ids` 非空（空→400）；逐筆呼叫 US1 安全刪除（**各自獨立 tx/錯誤隔離**）、把例外對映成 `reason` 碼、聚合 `{deleted, failed, results[]}`。回應形狀依 `contracts/member-admin.md` §2。令 T008 轉綠。
- [X] T010 [US2] 改 `frontend/src/routes/admin/members.tsx`：沿用 `admin/tags.tsx` 的 `selected: Set<string>` 樣板——表頭/列 checkbox、選取後顯示批次動作列（「已選 N 位」+「批次刪除」）；批次刪除確認對話框顯示位數 + 連帶影響；提交打 `bulk-delete`、用 toast/摘要顯示 deleted/failed。
- [X] T011 [P] [US2] 擴充 `frontend/src/__tests__/members-batch.test.tsx`（先失敗，US2 部分）：勾選多位 → 出現「已選 N 位」批次動作列；送出後渲染 deleted/failed 摘要。

**Checkpoint**：US2 可獨立驗收（規模化清理；建立在 US1 之上）。

---

## Phase 5: User Story 3 — 批次預建 local_password 成員（P3）

**Goal**：貼 email 清單 → `POST /admin/members/bulk-create` 逐筆建 local_password 成員 + 邀請連結，回 4 類摘要。

**Independent Test**：貼「新 + 已存在 + 格式錯 + 同批重複」→ 200 + 逐筆分類 + created 帶 invitation_url。

- [X] T012 [P] [US3] 擴充 `tests/contract/test_member_batch_admin.py`（先失敗，US3 部分）：`POST /admin/members/bulk-create` —— 輸入含（1 新 + 1 既存 + 1 格式錯 + 1 同批重複）→ 200、`created/exists/invalid/duplicate` 計數正確、results 逐筆 `status` + `created` 帶 `invitation_url`；空清單 → 400；無 admin → 401/403；驗每筆 created 寫 `member_created` 稽核。
- [X] T013 [US3] 在 `src/ai_api/api/admin_members.py` 新增 `POST /members/bulk-create`：解析多行 emails（trim/去空行/同批去重）→ 逐筆套既有 `MemberService.create(provider=local_password, send_invitation=True)`；`MemberAlreadyExists`→`exists`、驗證失敗→`invalid`、同批重複→`duplicate`、成功→`created`+ 由 `invitation_plaintext` 組 `invitation_url`（沿用既有單筆端點組 URL 的方式）。聚合計數 + results。回應依 `contracts/member-admin.md` §3。令 T012 轉綠。
- [X] T014 [US3] 改 `frontend/src/routes/admin/members.tsx`：「批次新增成員」對話框（多行 textarea + 提交）；結果渲染逐筆摘要（created 附可複製的邀請連結、exists/invalid/duplicate 標示）；成功後 invalidate 成員列表。
- [X] T015 [P] [US3] 擴充 `frontend/src/__tests__/members-batch.test.tsx`（先失敗，US3 部分）：貼多行 email 提交 → 渲染 created/exists/invalid/duplicate 摘要 + created 列顯示邀請連結。

**Checkpoint**：US3 可獨立驗收（批次預建本地帳號）。

---

## Phase 6: Polish & Cross-Cutting

- [X] T016 後端全綠：`python -m pytest tests/ -q` + `ruff check src/ai_api` + `mypy src/ai_api/services/members.py src/ai_api/api/admin_members.py`；確認既有成員/分配/計費零回歸（SC-006）。
- [X] T017 [P] 前端全綠：`cd frontend && npx tsc --noEmit && npm run build && npm test -- --run`（含 members-batch 新測試）。
- [X] T018 [P] 確認 `alembic heads` 仍為 `0018`（無新增）、依賴（pip/npm）無新增（research R6）。
- [X] T019 依 `quickstart.md` 走 US1–US3 + 零回歸手動驗收（含真機驗 CallRecord 孤兒保留：刪一位有用量的成員後，其呼叫紀錄仍在且 `allocation_id` 為 NULL）。

---

## Dependencies & 執行順序

- **Setup（T001）** → **US1（T002–T007）** MVP（安全刪除服務 + 端點 + 單筆 UI）。
- **US2（T008–T011）** 依賴 US1 的安全刪除服務（批次只是迴圈 + 摘要）。
- **US3（T012–T015）** 與 US1/US2 **獨立**（不碰安全刪除），可平行於 US2。
- **Polish（T016–T019）** 最後。

## 平行機會
- 測試先寫：T002（integration）、T003（contract US1）、T007（前端 US1）不同檔可平行起草。
- **US3 與 US2 可整段平行**（不同端點、不同 UI 區塊；US3 不依賴 US1 服務）。
- Polish：T017/T018 可平行。

## MVP 範圍
**US1（T001–T007）** 即 MVP：有分配的成員可一鍵安全刪除（直接解除使用者當下撞到的痛點）。US2（批次刪除）、US3（批次新建）為增量。

## Format 驗證
所有任務皆 `- [ ] Txxx [P?] [Story?] 描述 + 檔路徑`；Setup/Foundational/Polish 無 story 標籤、US 階段帶 [US#]。
