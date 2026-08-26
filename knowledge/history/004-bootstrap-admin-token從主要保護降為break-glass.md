# 004：bootstrap admin token 從「主要保護」降為 break-glass
> 日期：2026-05-27

## 轉移
- 舊（superseded）：階段 1（001 FR-019 + Assumptions）以「單一 bootstrap admin token（env 注入）」保護
  管理員 API，作階段 1 的臨時方案。階段 3b（spec 010）的首位 admin bootstrap 也假設「用 X-Admin-Token
  `PATCH is_admin=true` 即可」。
- 新（spec 017 / 階段 8）：`create_admin` CLI（idempotent）以 helm pre-upgrade hook Job 在 migrate 之後
  佈建首位 admin；正式環境帶預設/空 token 即**啟動防呆 fail-fast**；bootstrap token 退為 **break-glass**，
  日常一律走 admin member session。

## 為什麼變
使用者一句「部署上去後管理員會是誰？」戳破「pod healthy ＝ 部署完成」的錯覺：全新 DB 無 admin、後台只吃
session、OIDC 註冊者一律非 admin → 部署完成卻沒人進得了後台；唯一能動的是預設值公開已知的 bootstrap token
（等於後門）。「部署成功」的驗收要含「指定的人真能登入操作」，不只 pod healthy。安全預設（金鑰、後門 token）
一律啟動時 fail-fast，誤觸範圍才是 0。沿用既有 `COOKIE_SECURE` 當 production 訊號、不新增 `APP_ENV`（YAGNI）。

## 狀態
✅ 已採用。spec 010 的「token PATCH 即可」是被此轉移推翻的中途假設（其不足在切片之後才閉合）。
