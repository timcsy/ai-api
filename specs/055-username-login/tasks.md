---
description: "Task list for 本地登入允許以帳號（非 email）登入"
---

# Tasks: 本地登入允許以帳號（非 email）登入

**Prerequisites**: spec.md、plan.md
**Tests**: TDD——測試先於實作。**零 migration、零回歸**（既有 email 登入測試全綠為硬底線）。

## Phase 1: Setup
- [X] T001 基線：`pytest tests/ -q -k "login or member or tag_rule"` 全綠（零回歸起點）。

## Phase 2: Foundational（識別碼工具——阻斷全部）
- [X] T002 [test] `tests/unit/test_identifier.py`：`normalize_identifier`（strip+lower）、`is_email`（含 `@` 且合法）、`validate`（禁空白/空/超長；`@` 允許）邊界。先紅。
- [X] T003 新建 `src/ai_api/auth/identifier.py`：`normalize_identifier()` / `is_email()` / `validate_identifier()`（含 `@`→走 EmailStr 驗證；否則帳號規則）。
- [X] T004 跑 T002 綠。

## Phase 3: US1 帳號登入（P1，核心）
- [X] T005 [test][US1] `tests/contract/test_local_login.py` 擴充：帳號型成員（識別碼非 email）+ 密碼登入成功；錯密碼→通用 401；大小寫不敏感；速率限制/稽核不變。先紅。
- [X] T006 [US1] `api/auth.py`：`LocalLoginRequest.email: EmailStr` → 識別碼 `str`，登入前 `normalize_identifier`；查詢 `Member.email == 識別碼` 照舊；錯誤/鎖定/session 全不動。
- [X] T007 [US1] 跑 T005 綠 + 既有 email 登入測試零回歸。

## Phase 4: US2 帳號建立成員 + 邀請（P1）
- [X] T008 [test][US2] 契約：以帳號建立本地成員→201 + 邀請連結；重複識別碼→重複；非法（空白/超長）→擋；`@` 允許。先紅。
- [X] T009 [US2] `api/admin_members.py`（`CreateMemberRequest`、`BulkCreateRequest` 的 `EmailStr`/adapter）→ 改用 `validate_identifier` + normalize；`services/members.py::create` 接受帳號、唯一性沿用。
- [X] T010 [US2] 跑 T008 綠。

## Phase 5: US3 帳號型成員自動分組（P2）
- [X] T011 [test][US3] `tests/unit/test_tag_rules.py`：`identifier_regex` 對帳號匹配、指派 tag；`email_domain` 對帳號（無網域）不匹配且不出錯；「測試識別碼」工具接受帳號。先紅。
- [X] T012 [US3] `models/tag_rule.py` `MatcherType` 加 `identifier_regex`（免 migration）；`services/tag_rules.py::_matches` 支援它（比對整個識別碼）；`api/admin_tag_rules.py` `TestRequest.email: EmailStr`→`str`、序列化含新型別。
- [X] T013 [US3] 跑 T011 綠。

## Phase 6: 前端
- [X] T014 [US1/US2] `login.tsx`（`type=email`→`text`、標籤「帳號 / Email」、拿掉 email regex）；`members.tsx` 建立成員欄位/標籤/放寬驗證；`tag-rules.tsx` 新 matcher 選項 + 測試輸入放寬；相關 `__tests__` 跟改。
- [X] T015 前端全套 `vitest run` + `tsc --noEmit; echo $?` + `npm run build` 綠。

## Phase 7: Polish & 驗收（部署前停）
- [X] T016 全套零回歸：`pytest tests/ -q` + `ruff check .` + `uv run mypy src/ai_api`；前端全套 vitest + tsc(退出碼) + build。
- [ ] T017 **本機/預備驗證**：以帳號建成員→設密碼→登入；email 登入仍正常；帳號型成員拿到 identifier_regex tag、網域規則不誤匹配。→ **停在此處交付使用者確認**（登入敏感，正式部署前先驗）。
- [ ] T018 （使用者確認後）PR + squash-merge；前後端兩 image、**無 migration**；部署 ccsh + tew；真機驗一輪登入。
- [ ] T019 知識同步：experience 蒸餾「email 在本地登入只是未驗證識別碼→可放寬成帳號（重用欄位零 migration、含@才走 email 驗證）；自動 tag 網域式對無網域識別碼自然不匹配、加 identifier_regex 補齊」；vision 視需要加一筆。

## Dependencies
- Foundational（T002–T004）阻斷全部。US1（T005–07）、US2（T008–10）依賴它；US3（T011–13）獨立於 US1/US2 但共用識別碼概念。前端（T014–15）依賴後端。
- **MVP＝Foundational + US1 + US2**（帳號可建、可登入）。US3 分組、前端打磨其後。
- **硬底線：既有 email 登入 / OIDC 零回歸**（每階段都跑既有登入測試）。
