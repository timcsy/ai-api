# Implementation Plan: Admin Workflow Consolidation

**Branch**: `013-admin-ux-consolidation` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-admin-ux-consolidation/spec.md`

## Summary

把 Phase 5 留下的 11 個 entity-CRUD admin 頁，重組為 **6 個 journey-oriented 入口**：首頁（onboarding → 日常 dashboard）、Model（合併 catalog 管理 + 存取規則 + 檢視）、Member（成員 + 分配 + per-member 視角）、Tag（雙向群組規則）、觀測（用量 / 配額池 / Rebalance log / 稽核 tabs）、Provider 憑證（保留）。新增 1 個診斷 endpoint `GET /admin/diagnose/visibility?member_id=...&model_slug=...`。既有 endpoint 全保留；舊 URL 用 React Router redirect 維持 deep-link。不改 DB schema。

## Technical Context

**Language/Version**：TypeScript strict + React 19 + Vite 6（前端）；Python 3.11+ + FastAPI（後端，僅加一個 endpoint）
**Primary Dependencies**：shadcn/ui、TanStack Query、React Router DOM 7、既有後端 stack（無新增）
**Storage**：無 DB 變更
**Testing**：Vitest + Testing Library（前端，目前 56 tests baseline）；pytest（後端，目前 264 tests baseline）
**Target Platform**：Linux server（K8s）；本機 dev uvicorn + Vite
**Project Type**：web-service（後端 + SPA）
**Performance Goals**：visibility 診斷 < 200ms（百人 × 數十 model 線性掃過）；onboarding checklist 載入 < 500ms
**Constraints**：既有 11 admin URL deep-link 必須仍可 access（FR-012 / SC-005）；既有 API contract 不破壞（FR-013 / SC-006）
**Scale/Scope**：~10 admin 頁 → 6 入口、+ ~20 React Router 子路徑（detail pages）；後端 +1 endpoint

## Constitution Check

### I. Test-First (NON-NEGOTIABLE) ✅
- 後端新 endpoint：先寫 contract test（紅）→ 實作
- 前端新頁 / 整合頁：先寫 component smoke test → 實作
- Redirect 行為：寫 router test 驗證舊 URL 跳新位置

### II. API 契約優先 ✅
- 新 endpoint `GET /admin/diagnose/visibility` 先寫 OpenAPI（contracts/diagnose.yaml）再實作
- 既有 endpoint 不動契約

### III. 整合測試覆蓋外部依賴 ✅
- 不引入新外部依賴
- 既有 264 backend + 56 frontend tests 全部要繼續綠

### IV. 可觀測性 ✅
- visibility 診斷不寫新 audit（純查詢）
- 既有 audit 事件型別足夠

### V. 簡潔優先 (YAGNI) ✅
- 不引入新狀態管理 / 新元件庫
- Tag 詳情頁 / Model 詳情頁複用既有元件（Table / Badge / Form）
- 觀測類整合只做 Tabs 包裝，不重寫 4 個既有頁
- 不做「以 X 視角預覽」的權限模擬 sandbox（純函式評估即可）

**Pass**：所有原則均符合，無 deviation。

## Project Structure

### Documentation (this feature)

```text
specs/013-admin-ux-consolidation/
├── plan.md                # 本檔
├── research.md            # Phase 0：page → journey 對應決定
├── data-model.md          # Phase 1（極短：無 entity 變更）
├── quickstart.md          # Phase 1：5 個 user journey 的手動驗證腳本
├── contracts/
│   └── diagnose.yaml      # 新 endpoint
├── checklists/
│   └── requirements.md    # 已完成
└── tasks.md               # /speckit.tasks 產生
```

### Source Code (repository root)

```text
src/ai_api/
└── api/
    └── admin_diagnose.py            # NEW: GET /admin/diagnose/visibility

tests/
├── contract/
│   └── test_admin_diagnose.py       # NEW
└── integration/
    └── test_diagnose_visibility.py  # NEW: end-to-end 對 4 種 deny 路徑

frontend/src/
├── routes/admin/
│   ├── home.tsx                     # MODIFY: onboarding 完成後切換 dashboard 模式
│   ├── model.tsx                    # NEW: 合併原 catalog-manage / model-access / catalog(view)
│   ├── model-detail.tsx             # NEW: 單一 model 含 access policy + 可見性預覽
│   ├── member.tsx                   # MODIFY: 強化原 members 頁
│   ├── member-detail.tsx            # NEW: 該成員 tag / 能用的 model / allocations / 異常
│   ├── tag.tsx                      # MODIFY: 從原 tags 改為 tag 列表
│   ├── tag-detail.tsx               # NEW: 持有此 tag 的 members + 涵蓋的 models
│   ├── observability.tsx            # NEW: tab 包裝 usage / quota-pool / rebalance / audit
│   ├── catalog-manage.tsx           # KEEP（但 nav 移除）為 redirect target，內部跳 /admin/model
│   ├── model-access.tsx             # KEEP 同上
│   ├── tags.tsx                     # 改名為 tag.tsx 或保留作 redirect
│   ├── allocations.tsx              # 改成只 redirect 到 /admin/member（保留卡片視圖）
│   ├── usage.tsx                    # 內容搬到 observability.tsx 的 tab
│   ├── quota-pool.tsx               # 同上
│   ├── rebalance-log.tsx            # 同上
│   └── audit.tsx                    # 同上
├── components/
│   ├── app-shell.tsx                # MODIFY: 砍 sub-nav 到 6 項
│   └── visibility-diagnose.tsx      # NEW: 可重用的「以 X 視角看 Y」面板
└── lib/
    └── legacy-redirects.tsx         # NEW: 舊 URL → 新 URL 的 React Router 映射
```

**Structure Decision**：沿用既有 web-service 結構，前端在 `frontend/src/routes/admin/` 新增 4 個合併頁 + detail 頁，後端在 `src/ai_api/api/admin_diagnose.py` 加 1 個 endpoint。舊頁面 keep 為內容組件、route 改 redirect，保 deep-link 不壞。

## Complexity Tracking

無偏離 constitution，本節留空。
