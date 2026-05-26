# Implementation Plan: Rule-Based Auto-Tagging

**Branch**: `014-auto-tag-rules` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-auto-tag-rules/spec.md`

## Summary

新增 `TagRule` 實體（admin 有序規則）+ `MemberTag.source` 欄位。成員**首次建立**時（OIDC 自助註冊 + admin 手動建立）跑規則引擎 first-match-wins 自動貼 tag（source=auto）。regex matcher 有 anchor / 長度 / 複雜度三道護欄。新增 admin CRUD + 排序 + 「測試 email」endpoints 與 UI 頁。auto tag 與既有 tag 完全等價（access policy / 診斷 / tag 詳情不改）。

## Technical Context

**Language/Version**：Python 3.11+（後端）+ TypeScript strict / React 19（前端）
**Primary Dependencies**：FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、既有前端 stack；**不引入 re2**（用標準 `re` + 護欄）
**Storage**：PostgreSQL / SQLite；新表 `tag_rules`；既有 `member_tags` 加 `source` + `rule_id` 欄
**Testing**：pytest（後端，目前 277 baseline）；Vitest（前端，目前 65 baseline）
**Target Platform**：Linux server（K8s）；dev uvicorn + Vite
**Performance Goals**：首次註冊規則評估 < 100ms（SC-004）；規則只在 cold path（建立成員）跑，不在登入 hot path
**Constraints**：regex 防 ReDoS（anchor + ≤64 長度 + 複雜度檢查）；既有 API contract 不破壞
**Scale/Scope**：規則 < 20 條、百人量級成員；後端 +1 表 +1 欄 +5 endpoints +1 service；前端 +1 admin 頁

## Constitution Check

### I. Test-First (NON-NEGOTIABLE) ✅
- regex 護欄：unit test 先（合法 / 巢狀量詞拒絕 / 未 anchor 自動補 / 超長截斷）
- 規則評估：unit test first-match-wins + fallback + 無命中
- endpoints：contract test 先
- 註冊 hook：integration test（OIDC + admin-create 兩路徑都貼 tag）

### II. API 契約優先 ✅
- 5 個新 endpoint 先寫 OpenAPI（contracts/tag-rules.yaml）再實作
- 既有 endpoint 不動

### III. 整合測試覆蓋外部依賴 ✅
- 註冊 → 自動貼 tag → access policy 生效，端對端整合測試
- 既有 277 backend + 65 frontend 測試零回歸

### IV. 可觀測性 ✅
- auto 貼 tag 寫 `member_tag_added` audit + details `source=auto, rule_id`
- regex 拒絕寫結構化 log（不洩 pattern 內容給非 admin）

### V. 簡潔優先 (YAGNI) ✅
- 不引入 re2（cold-path 單次，護欄足夠）
- 不做「每次登入重算」「email 變更重算」（spec 明確排除）
- fallback 用 catch-all matcher（排最後），不另設 schema
- 複用既有 MemberTagService.add（idempotent）貼 tag

**Pass**：無 deviation。

## Project Structure

### Documentation (this feature)

```text
specs/014-auto-tag-rules/
├── plan.md              # 本檔
├── research.md          # Phase 0：regex 護欄策略 / hook 位置 / matcher 設計
├── data-model.md        # Phase 1：TagRule + MemberTag.source
├── quickstart.md        # Phase 1：3 user story 手動驗收
├── contracts/
│   └── tag-rules.yaml   # 5 endpoints
├── checklists/requirements.md  # 已完成
└── tasks.md             # /speckit.tasks 產生
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── tag_rule.py                  # NEW: TagRule ORM model + MatcherType enum
│   └── member_tag.py                # MODIFY: add source + rule_id columns
├── services/
│   ├── tag_rules.py                 # NEW: CRUD + regex guard + evaluate() + apply_to_new_member()
│   └── member_tags.py               # MODIFY: add() 接受 source 參數
├── api/
│   └── admin_tag_rules.py           # NEW: 5 endpoints (CRUD + reorder + test)
├── auth/
│   └── ... (no new file; hook called from existing creation points)
├── api/auth.py                      # MODIFY: _find_or_create_oidc_member 建立後呼叫 apply
└── services/members.py              # MODIFY: create() 建立後呼叫 apply

alembic/versions/
└── 0011_tag_rules.py                # NEW: tag_rules 表 + member_tags.source/rule_id

frontend/src/
└── routes/admin/
    └── tag-rules.tsx                # NEW: 規則 CRUD + 排序 + 「測試 email」
                                     #      （從 /admin/tag 頁加一個入口，或 sub-nav 不變、放 Tag 頁 tab）

tests/
├── unit/
│   ├── test_regex_guard.py          # NEW: anchor/length/complexity
│   └── test_tag_rule_eval.py        # NEW: first-match / fallback / no-match
├── contract/
│   └── test_admin_tag_rules.py      # NEW
└── integration/
    └── test_auto_tag_on_register.py # NEW: OIDC + admin-create 兩路徑
```

**Structure Decision**：沿用既有結構。註冊 hook **不新增 middleware**，只在既有兩個 member 建立點（`_find_or_create_oidc_member`、`MemberService.create`）建立成功後呼叫 `TagRuleService.apply_to_new_member(session, member)`。前端規則管理頁掛在 Tag 區（避免增加 sub-nav 第 7 條，呼應 Phase 5.1 的精簡原則）。

## Complexity Tracking

無偏離 constitution，本節留空。
