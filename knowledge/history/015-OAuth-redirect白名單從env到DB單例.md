# 015：OAuth redirect 白名單從 env 到 admin 可編 DB 單例
> 日期：2026-08-25

## 轉移
- 舊（superseded）：redirect 白名單原本只從 env `OAUTH_REDIRECT_ALLOWLIST` 讀（fixed、要改得重部署）。
- 新（spec 057 FR-010，維護者追加）：改用 `oauth_config`（`CHECK id=1`）**從 env lazy-seed**、之後 DB 為
  單一真理 + `GET/PUT /admin/oauth/config` + 後台頁「應用授權」。空清單 = fail-closed。

## 為什麼變
「該可設定又不想每次 redeploy」→ lazy-seed DB 單例；env 退為 bootstrap 預設、搬家零行為變更。這是該模式在
本專案的**第三次套用**（pool_config → anomaly_config → oauth_config）。上線時 fail-closed，待 admin 於後台
加 origin 才啟用（安全預設 fail-closed，同「安全設定啟動時 fail-fast」）。

## 狀態
✅ 已採用。OAuth 本體（Auth Code + PKCE、first-party、無 client_secret/refresh）見
`completed-phases-detail.md` 階段 43；OAuth 只是「發既有 Credential 的 UX」、不另立權限或計費模型。
