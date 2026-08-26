# 005：存取治理從「email 白名單為主」到「成員清單單一真理」
> 日期：2026-05-30

## 轉移
- 舊（superseded）：階段 2 把 email 白名單當「日常管理機制之一」，與自動註冊規則、來源限制並列（兩條
  路徑都能管 access）。
- 新（階段 12）：白名單退為 **bootstrap-only**（`is_email_allowed`：DB 有任何 admin → admin mode、白名單
  不生效；DB 無 admin → bootstrap mode 才查白名單）。成員清單成為 access 的單一真理。

## 為什麼變
Phase 11 上線實測暴露：admin 在 `/admin/members` 新增的成員 OIDC 登入被白名單擋、老師收到「this account
is not allowed」。根因是白名單與成員管理兩條路徑管同一件事、心智雙軌、靠 admin 兩邊同步不現實 → 使用者被
無聲擋下。設計時就要回答「誰是該機制的 source of truth」，其他機制 derive 自它或只在它不存在時生效。
「bootstrap-only fallback」把這原則寫進程式：平時不在路徑上、不會 drift，緊急時（首位 admin）還在。

## 狀態
✅ 已採用（原則 5「集中管理單一真理」的具現）。同模式後續反覆套用（env→DB 單例）。
