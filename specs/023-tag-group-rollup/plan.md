# 實作計畫：Tag-based 群組成本 rollup

**Branch**: `023-tag-group-rollup` | **Date**: 2026-06-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-tag-group-rollup/spec.md`

## 摘要

在既有 `aggregate_usage` 加一個 `group_by="tag"` 維度：JOIN `CallRecord → Allocation →
MemberTag`，依 `MemberTag.tag` 聚合。多 tag 重疊由 JOIN 自然產生（一成員 N tag → 該成員
呼叫在 N 個 tag 各計一次），刻意接受、UI 標示。下鑽（某 tag 的成員明細）重用既有 member
維度 + tag 成員過濾。前端 `/admin/usage` 加「依 Tag」選項 + 重疊提示 + 點 tag 展開成員。
**無新表、無 migration、無新依賴。**

## 技術脈絡

**Language/Version**: Python 3.11+（後端）/ TypeScript strict + React 19 + Vite 6（前端），皆既有
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2、TanStack Query、shadcn/ui（皆既有，**不新增套件**）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——沿用既有
`member_tags`（composite PK `member_id, tag`）與 `call_records`
**Testing**: pytest（後端 contract + 整合）+ vitest（前端）
**Target Platform**: 既有 K8s 部署，無新部署元件
**Project Type**: Web application（backend + frontend，既有）
**Performance Goals**: tag 聚合查詢單一 GROUP BY JOIN，≤ 既有 member 維度查詢的延遲量級（< 200ms p95）
**Constraints**:
- 既有 member/allocation/model 維度零退化（FR-SC-004）
- 一般成員不可取得跨成員聚合（FR-012/013）
- 重疊為刻意語意，UI 必須標示，且**不**把各 tag 加總當平台總額（FR-006/007）
**Scale/Scope**: 每部署數十個 tag、數百成員；聚合 row 數 = distinct tag 數（小）

## 憲章檢核（Constitution Check）

*GATE：必須在 Phase 0 research 前通過。Phase 1 design 後重核。*

### I. Test-First（不可妥協）
- ✅ tasks 將以「先寫失敗測試 → 實作」順序；contract test 驗 tag 聚合 = 成員各自相加
- ✅ 缺陷修復亦以可重現失敗測試起手

### II. API 契約優先
- ✅ 純擴充既有 `GET /admin/usage` 的 `group_by` enum（加 `tag`）+ 新增 tag 成員下鑽端點；
  以 OpenAPI 定義後才實作
- ✅ **非破壞性**：既有 `group_by=member/allocation/model` 不變；新增值與新端點

### III. 整合測試覆蓋外部依賴
- ✅ DB 聚合（多 JOIN + 重疊語意）以整合測試驗證，特別是「多 tag 成員重複計入」正確性

### IV. 可觀測性
- ✅ 沿用既有 usage 端點的 log；無新外部依賴

### V. 簡潔優先（YAGNI）
- ✅ **不新增 entity / 表 / migration**——沿用 `member_tags` distinct（呼應既有「Tag 設計：先用
  distinct 推導」lesson）
- ✅ tag **不做時間版本化**（採查詢當下歸屬）——明文寫進 spec 假設
- ✅ 重疊**不去重**——刻意語意，UI 標示即可
- ✅ 首頁 Top 5 tags 卡延到階段 14（不在本範圍）

### 語言與文件規範
- ✅ spec / plan / tasks / checklists 皆繁體中文；code 識別字英文；commit 英文；UI 文案繁中

**Gate 結果（Phase 0 前）**：通過。無偏離項。

**重核（Phase 1 後）**：
- I. TDD：contracts 已定義；tasks 將生成「先寫聚合正確性測試 → 才實作 tag 分支」。✅
- II. 契約優先：`contracts/admin-usage-tag.openapi.yaml` 完整（擴充 enum + 下鑽端點，明標 NON-BREAKING）。✅
- III. 整合測試：tag 聚合的多 JOIN + 重疊正確性 + service_only + member 隔離皆有整合測試情境（quickstart 1–8）。✅
- IV. 可觀測性：沿用既有 usage 端點 log，無新外部依賴。✅
- V. YAGNI：維持「無新表 / 無 migration / 無新依賴 / tag 不版本化 / 不去重」。✅

**Phase 1 後 Gate 結果**：通過。設計穩定，可進入 `/speckit.tasks`。

## 專案結構

### 文件（本 feature）

```text
specs/023-tag-group-rollup/
├── plan.md                  # 本檔
├── spec.md                  # 已完成
├── research.md              # Phase 0 輸出
├── data-model.md            # Phase 1 輸出
├── quickstart.md            # Phase 1 輸出
├── contracts/
│   └── admin-usage-tag.openapi.yaml
├── checklists/requirements.md  # 已完成
└── tasks.md                 # /speckit.tasks 階段產生
```

### 原始碼（既有結構，標 NEW / 改）

```text
backend (src/ai_api/)
├── services/usage.py        # 改：GroupBy 加 "tag"；新增 tag 聚合分支 + tag 成員下鑽函式
├── api/usage.py             # 改：group_by enum 接受 tag；新增 GET /admin/usage/tag/{tag}/members
└── services/member_tags.py  # 既有（list_distinct 可重用，可能不改）

frontend (frontend/src/)
└── routes/admin/usage.tsx   # 改：Select 加「依 Tag」；tag 列可點開成員明細；重疊提示文字

tests/
├── contract/test_usage_tag.py        # NEW: tag 維度端點契約 + 重疊正確性
└── integration/test_usage_tag_agg.py # NEW: 多 JOIN 聚合 + 多 tag 重疊 + member 隔離
```

**Structure Decision**: 沿用既有 web application 結構。**零新增頂層目錄、零新表、零 migration**。
改動集中在 `services/usage.py`（加 tag 分支）、`api/usage.py`（enum + 下鑽端點）、
`frontend/.../usage.tsx`（Tag 視圖 + 下鑽 + 重疊提示）。

## Complexity Tracking

> 無憲章違反項，本節空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| —         | —          | —                                   |

## 下一步

- Phase 0 / Phase 1 artifacts 由本 `/speckit.plan` 後續產生
- Phase 1 完成後重核憲章
- `/speckit.tasks` 以 plan + research + data-model + contracts 產出 tasks.md
