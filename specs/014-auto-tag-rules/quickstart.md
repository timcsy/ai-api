# Quickstart：Rule-Based Auto-Tagging 驗收場景

## 前置
- Phase 5 + 5.1 已部署（tag / access policy / 診斷已存在）
- admin 已登入

## 場景 1：定義學生/老師規則 + 測試（US1 / SC-001 / SC-003）

1. 進 Tag 區 → 「自動標籤規則」
2. 新增規則 A：matcher `email_localpart_regex`、pattern `[a-z]{0,2}\d{6,}`、tag `student`
3. 新增規則 B：matcher `always`、tag `teacher`（fallback）
4. 確認列表顯示 A 在 B 之前（order）
5. 用「測試 email」：
   - `b10901234@school.edu` → 命中規則 A → `student`
   - `prof.wang@school.edu` → 命中規則 B → `teacher`
6. 嘗試新增惡意 regex `(a+)+$` → **被拒**，提示 unsafe_regex

**通過判準**：2 條規則 3 分鐘內建好 + 測試正確 + 惡意 regex 被擋。

## 場景 2：首次註冊自動貼 tag（US2 / SC-002 / SC-005）

1. 規則設好後，用 `b10901234@school.edu` 走 OIDC 首次註冊（或 admin 建立此 email 的 local 成員）
2. 查該成員 → tag 含 `student`、標 `source=auto`
3. 用 `prof.wang@school.edu` 註冊 → tag 含 `teacher`（fallback）
4. 把某 model 設 restricted + allowed `["student"]` → `b10901234` 在 catalog 看得到、`prof.wang` 看不到
5. `b10901234` 再次登入 → 規則**不重跑**（tag 不變）

**通過判準**：學號→student、其他→teacher 各 100% 正確；auto tag 走 access policy 與手動 tag 行為一致。

## 場景 3：auto tag 辨識與覆蓋（US3 / SC-006）

1. 在成員詳情 / 成員列表看 `b10901234` → `student` tag 有「自動」標記
2. admin 手動移除該 auto tag
3. `b10901234` 再次登入 → tag **不被重貼**（首次註冊才跑）
4. 查稽核 → `member_tag_added` 事件 details 有 `source=auto, rule_id=...`

**通過判準**：auto 與 manual 視覺可分；移除後不重貼；audit 有來源。

## 場景 4：相容性回歸（SC-005）

```bash
uv run pytest -q          # 既有 + 新測試全綠
cd frontend && npm test -- --run
```

**通過判準**：既有 access policy / 診斷 / tag 詳情測試零回歸。
