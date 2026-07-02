# Implementation Plan: 本地登入允許以帳號（非 email）登入

**Branch**: `055-username-login` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)

## Technical Context

- Python 3.11+（後端）/ TypeScript strict + React 19（前端）；FastAPI、SQLAlchemy 2.x async、Pydantic v2
- **零 migration**：登入識別碼沿用既有 `members.email`（String(320)、唯一、NOT NULL）；tag matcher 是 `Enum(native_enum=False)` VARCHAR，加值免 migration
- 對應原則 6（可達性）、原則 2（可追蹤）；守零回歸

## 核心決策（Option C 折衷，spec Assumptions 已凍結）

- **只放寬 local**；OIDC 一律 email。`email` 欄重用為「登入識別碼」，值可為 email（含 `@`）或帳號（不含 `@`）。
- **識別碼正規化**：統一 `strip().lower()`；帳號禁 `@`、禁空白、非空、≤320。含 `@` 者走既有 email 驗證（沿用 `EmailStr` 判斷）。
- **自動 tag**：現有 `email_localpart_regex` 對無 `@` 帳號＝整串比對，已可用；額外加一個 `MatcherType.identifier_regex`（比對整個識別碼、語意清楚，VARCHAR 免 migration）。網域/後綴對帳號自然不匹配。

## 需改動的點（無新資料結構）

```
backend/
  src/ai_api/auth/identifier.py            # NEW 小工具：normalize_identifier() + is_email() + validate（禁@/空白/長度）
  src/ai_api/api/auth.py                   # LocalLoginRequest.email EmailStr→識別碼(str)+正規化；查詢照舊
  src/ai_api/api/admin_members.py          # CreateMemberRequest/BulkCreate：EmailStr→識別碼驗證
  src/ai_api/services/members.py           # create：接受帳號、正規化、唯一性沿用
  src/ai_api/api/admin_tag_rules.py        # TestRequest.email EmailStr→str
  src/ai_api/models/tag_rule.py            # MatcherType 加 identifier_regex（免 migration）
  src/ai_api/services/tag_rules.py         # _matches 支援 identifier_regex（比對整個識別碼）
tests/
  tests/contract/test_local_login.py       # 擴充：帳號登入成功/錯密碼通用錯誤/大小寫
  tests/contract/test_admin_members*.py     # 帳號建立成員 + 邀請
  tests/unit/test_identifier.py            # normalize/validate/is_email 邊界
  tests/unit/test_tag_rules.py             # identifier_regex 對帳號匹配 + 網域對帳號不誤匹配
frontend/
  src/routes/login.tsx                     # type email→text、標籤「帳號 / Email」
  src/routes/admin/members.tsx             # 建立成員欄位/標籤/放寬前端驗證
  src/routes/admin/tag-rules.tsx           # 新 matcher 選項 + 測試輸入放寬
  src/__tests__/login.test.tsx, members*    # 跟改
```

## Constitution Check

- **零 migration / 零回歸**：email 路徑不變（email 仍是合法識別碼）；既有登入測試全綠為硬底線。✅
- **TDD**：識別碼正規化/驗證單元 + 帳號登入契約 + tag identifier_regex 單元先行。✅
- **不新增套件**、**單一真理**（識別碼唯一欄不變）。✅
- **安全零削弱**：通用錯誤、速率限制、稽核、session 全沿用（只換識別碼型別）。✅

## Phase 分解見 tasks.md
