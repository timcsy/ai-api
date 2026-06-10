# Implementation Plan: 管理員成員管理批次化 + 安全刪除

**Branch**: `039-member-batch-admin` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/039-member-batch-admin/spec.md`

## Summary

讓管理員能（P1）一鍵**安全刪除**仍持有分配的成員、（P2）多選**批次刪除**、（P3）貼 email 清單**批次預建 local_password 成員**。核心是把目前「有分配就擋下」的 `MemberService.delete` 升級為「安全刪除」：在**單一交易**內**以 ORM 顯式**撤回並刪除該成員的分配、刪除憑證與 credential↔allocation 連結、把該成員的呼叫紀錄 `allocation_id` 設為 NULL（保留稽核）、再刪成員——**不依賴 DB 端 ondelete cascade**（SQLite 測試環境未開 FK pragma，靠 DB cascade 會 dev/prod 不一致）。批次端點 = 既有單筆服務的迴圈 + 逐筆結果聚合（不整批回滾）。前端沿用 `admin/tags.tsx` 既有的多選/批次樣板。**零 migration、零新套件、零新 enum**（`member_created`/`member_deleted` audit 已存在）。

## Technical Context

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、既有 `auth/invitations`（後端）；TanStack Query、shadcn/ui（前端）——**皆既有，不新增套件**
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——所有連帶刪除以 ORM 顯式處理，沿用既有 `members`/`allocations`/`credentials`/`credential_allocations`/`call_records`/`audit_events` schema
**Testing**: pytest（contract + integration）；前端 vitest + Testing Library
**Target Platform**: Linux server（k8s）+ 瀏覽器 SPA
**Project Type**: web application（backend + frontend）
**Performance Goals**: 批次操作為 admin 低頻互動；逐筆順序處理數百筆即可（無需平行化），單筆安全刪除為一個交易
**Constraints**: 安全刪除須原子（單筆）；批次逐筆獨立成敗、不整批回滾；不得刪除自己或最後一位 active 管理員；用量紀錄不得遺失（孤兒保留）
**Scale/Scope**: 後端 3 端點（改 1 + 新 2）+ 1 服務方法升級；前端 1 頁（成員列表）多選 + 2 個對話框

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 先寫失敗 contract/integration 測試（安全刪除連帶、批次逐筆摘要、防呆守衛），再實作。
- **II. 契約優先**：✅ Phase 1 先定 3 端點契約（DELETE 行為變更 + 2 個 bulk 端點的 request/response + 錯誤格式）。
- **III. 整合測試覆蓋外部依賴**：✅ 安全刪除的連帶（分配/憑證/連結刪除 + CallRecord 轉孤兒）以整合測試對真實 ORM 行為驗證——**特別要驗 CallRecord 在刪除後仍存在且 `allocation_id IS NULL`**（不能只 mock）。
- **IV. 可觀測性**：✅ 每筆刪除/建立寫結構化 audit（既有 `member_deleted`/`member_created`）；批次回傳逐筆結果含失敗原因碼。
- **V. YAGNI**：✅ 不新增表/欄位/enum/旗標；批次 = 既有單筆邏輯的迴圈；前端沿用既有 bulk 樣板。不做 CSV 上傳、不做角色批次、不做 explicit-purge。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/039-member-batch-admin/
├── plan.md              # 本檔
├── research.md          # Phase 0：6 個決策（顯式 cascade、批次交易邊界、防呆守衛、email 解析、UI 樣板、零 migration）
├── data-model.md        # Phase 1：刪除連帶圖 + 批次結果形狀（無 schema 變更）
├── quickstart.md        # Phase 1：US1–US3 + 零回歸手動驗收
├── contracts/
│   └── member-admin.md  # Phase 1：3 端點契約
└── tasks.md             # Phase 2（/speckit.tasks 產生，非本指令）
```

### Source Code (repository root)

```text
src/ai_api/
├── services/
│   └── members.py          # 升級 delete → 安全刪除（ORM 顯式連帶，單一 tx）；新增 bulk helpers（or 端點層迴圈）
├── api/
│   └── admin_members.py     # 改 DELETE /members/{id} 行為；新增 POST /members/bulk-delete、POST /members/bulk-create
└── models/                  # 不動（FK 行為已存在，但實作走 ORM 顯式不靠 DB ondelete）

tests/
├── contract/
│   └── test_member_batch_admin.py   # 安全刪除 + 2 bulk 端點契約 + 防呆守衛
└── integration/
    └── test_member_safe_delete.py    # 連帶刪除 + CallRecord 轉孤兒保留（真實 ORM 行為）

frontend/src/
├── routes/admin/
│   └── members.tsx          # 多選（Set<string>）+ 批次刪除動作列 + 批次新建對話框 + 單筆刪除確認升級
└── __tests__/
    └── members-batch.test.tsx        # 多選/批次/新建摘要 UI 測試
```

**Structure Decision**: web application（既有 `backend src/ai_api` + `frontend/src`）。本功能集中在成員管理一條垂直切面：服務層 `members.py`、API 層 `admin_members.py`、前端 `admin/members.tsx`。沿用既有 `tags.tsx` 的批次 UI 慣例與既有 `bulk-apply` 端點的回應風格。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
