# 013：本地登入識別碼從 EmailStr（限 email）到自由帳號
> 日期：2026-07-02

## 轉移
- 舊（superseded）：本地登入一直用 `EmailStr` 驗 email 當帳號（強制合法 email 格式）。
- 新（spec 055 / 階段 41，**零 migration**）：只放寬 **local** 登入接受任意識別碼（重用 `members.email` 欄、
  `@` 允許、只結構驗證 `validate_identifier`）；**OIDC 一律 email**；自動 tag 補 `identifier_regex` matcher
  讓純帳號也能分組。

## 為什麼變
組織內不少使用者沒有（或不想用）email。而 email 在本地登入**根本沒被驗證**——系統從不寄信給成員、邀請是
admin 手動交付的 token 連結、SMTP 只給 admin 通知。強制 email 格式毫無實質意義，純粹是型別選擇留下的自找限制。
教訓：加驗證前先問「這個欄位**真的**被當它宣稱的東西用嗎（有寄信/驗證嗎）？」放寬「身分/識別」欄位時要 grep
所有把它當 email 的隱形耦合（schema 驗證、字串切分、規則比對、UI 標籤）逐一決定，別只改登入。附帶：用
`partition("@")` 而非 `split("@")[1]` 天然對非 email 輸入安全。

## 狀態
✅ 已採用（Option C 折衷：接受「同一欄混裝兩種值」的語意債，本案可接受，比新增 `username` 雙軌省事）。
