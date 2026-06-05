# Implementation Plan: 憑證 UI 術語與層級收斂（統一「應用金鑰」、單一管理處、可改名）

**Branch**: `031-credential-ui-consolidation` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/031-credential-ui-consolidation/spec.md`

## Summary

純前端為主的 UX 收斂 + 一個改名端點。統一全站術語為「**應用金鑰**」、把建立/改名/改 model/rotate/撤回收斂到 dashboard 單一處；分配（model）詳情頁的金鑰區降**唯讀**（列「能用此 model 的金鑰」、每筆顯示其全部 model、連到本尊），消除「撤一把無聲連坐」；撤回確認**明示**會一起失效的 model；安裝 Codex / device 授權頁改「應用金鑰」字眼並接上清單。**唯一後端改動**：既有「調整金鑰」端點多收選填 `name`（member + admin），改名留稽核。不動資料模型、不新增 migration。

## Technical Context

**Language/Version**: TypeScript strict + React 19 + Vite 6（前端為主）/ Python 3.11+（後端僅 1 個改名端點擴充）
**Primary Dependencies**: TanStack Query、shadcn/ui、Tailwind（前端）；FastAPI、SQLAlchemy 2.x async、Pydantic v2（後端，**皆既有，不新增套件**）
**Storage**: PostgreSQL / SQLite；**不新增表、不新增 migration**（`Credential.name` 已存在，僅允許更新）
**Testing**: vitest（前端）、pytest（後端改名 contract）；既有全套零回歸
**Target Platform**: 既有 web
**Project Type**: web（既有 backend `src/ai_api/` + frontend `frontend/`）
**Performance Goals**: 無新熱路徑；改名為單列 UPDATE
**Constraints**: 既有 proxy / 計費 / 領取 / token **零回歸**（只動 UI 與改名端點，不改 scope / 資料模型）
**Scale/Scope**: 後端 +1 欄位於既有 PATCH（member + admin）；前端：app 卡加改名、分配詳情降唯讀、admin 成員頁加金鑰治理、字眼統一、退役 DeviceCredentialsCard 的「管理」用途

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First**：✅ 改名端點先寫失敗 contract（member 改名 + admin 改名 + 改名不影響 token/scope + 擁有者邊界），前端關鍵互動以 vitest 固化。
- **II. 契約優先**：✅ `contracts/rename.openapi.yaml`（PATCH `/me/credentials/{id}` 與 `/admin/credentials/{id}` 加選填 `name`）。
- **III. 整合測試覆蓋外部依賴**：N/A（無 schema 變更、無新外部依賴）；以既有全套零回歸把關。
- **IV. 可觀測性**：✅ 改名留稽核（`credential_renamed`，VARCHAR enum 免 migration）。
- **V. 簡潔優先（YAGNI）**：✅ 改名併進既有 PATCH（不另開端點）；分配詳情用既有「scope 含此分配的金鑰」清單做唯讀（免新後端）；退役而非重寫 DeviceCredentialsCard。

**結論：無違規。**這是低風險的 UI 收斂 + 一個欄位擴充。

## Project Structure

### Documentation (this feature)

```text
specs/031-credential-ui-consolidation/
├── plan.md ├── research.md ├── data-model.md ├── quickstart.md
├── contracts/rename.openapi.yaml
└── tasks.md（/speckit.tasks 產出）
```

### Source Code (repository root)

```text
src/ai_api/
├── api/schemas.py            # 改：ScopePatchRequest 加選填 name
├── api/me.py                 # 改：PATCH /me/credentials/{id} 接受 name → 改名 + 稽核
├── api/credentials.py        # 改：admin PATCH /admin/credentials/{id} 接受 name + 稽核
├── services/allocations.py   # 改：rename 邏輯（或 patch_credential_scope 接受 name）
└── models/auth_audit.py      # 改：加 credential_renamed enum 值（免 migration）

frontend/src/
├── components/
│   ├── app-credentials-card.tsx       # 改：每把加「改名」（就地編輯）
│   ├── allocation-keys-readonly.tsx   # 新：分配詳情用——唯讀「能用此 model 的應用金鑰」+ 每筆全部 model + 連 dashboard
│   ├── codex-install-card.tsx         # 改：說明「會在你的應用金鑰新增一把」
│   └── device-credentials-card.tsx    # 退役（移除「管理」用途；其 member/admin 掛點改用唯讀/成員層）
├── routes/
│   ├── allocation-detail.tsx          # 改：DeviceCredentialsCard → AllocationKeysReadonly
│   ├── admin/allocations.tsx          # 改：移除「查看裝置憑證」dialog（治理改走成員頁）
│   ├── admin/member-detail.tsx        # 改：加唯讀應用金鑰清單 + 撤回 + 改名（用 /admin/members/{id}/credentials）
│   └── device-authorize.tsx           # 改：「裝置」字眼 → 「應用金鑰」
tests/
├── contract/test_credential_rename.py # 新：member/admin 改名 + 不影響 token/scope + owner isolation
frontend/src/__tests__/
├── app-credentials-card.test.tsx      # 改：加改名互動
└── (retire credential-list.test.tsx if DeviceCredentialsCard removed)
```

**Structure Decision**: 沿用既有 web 結構。改名併入既有 PATCH（member + admin），不另開端點。分配詳情新增唯讀元件 `AllocationKeysReadonly`（讀既有 `/me/allocations/{id}/credentials`，顯示每把的全部可用 model + 「前往管理」連 dashboard）；退役 `DeviceCredentialsCard` 的管理用途（admin 分配頁 dialog 移除，治理移到 `admin/member-detail`）。全站「裝置 / 憑證」字眼掃為「應用金鑰」。

## Complexity Tracking

> 無憲章違規，免填。風險低（UI 收斂 + 單欄位擴充）；以既有全套零回歸 + 改名 contract 把關。
