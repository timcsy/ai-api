# Quickstart 驗收：會員介面分頁化

純前端。以下為手動 + 自動驗收腳本。

## 自動測試（先紅後綠）

```bash
cd frontend
npm test -- app-shell mobile-nav dashboard legacy-redirects keys-page allocations-page usage-page app-credentials
```

預期：改測試先失敗（紅）→ 實作後全綠。

## 手動驗收（dev server）

```bash
cd frontend && npm run dev
```

以**會員**身分登入，逐項確認：

1. **導覽（US1）**：頂部見「我的儀表板 / 金鑰 / 分配 / 用量 / 模型目錄」。逐一點擊載入對應頁。
2. **深連結（US1）**：直接開 `/keys`、`/allocations`、`/usage` 並重新整理 → 正確載入。開既有 `/dashboard/allocations/<id>` → 仍正確載入詳情。
3. **精簡儀表板（US2）**：`/dashboard` 只見摘要（用量/花費、金鑰數、分配數、安裝 Codex、待辦）；**不再**有金鑰表格全文 / 用量圖表 / 分配卡整列。
   - 無金鑰帳號 → 待辦「去建立第一把金鑰」連到 `/keys`。
   - 有可領取 model → 待辦連到 `/allocations`。
4. **一句解釋（US3）**：`/allocations` 與 `/keys` 頁首各見「分配＝你能用哪些模型；金鑰＝拿來連線的鑰匙」。
5. **金鑰編輯合一（US4）**：金鑰頁某把金鑰操作列只剩「編輯 / 重新產生 / 撤回」。點「編輯」→ 同時改名 + 改可用 model → 儲存生效（同一把 token 不需換）。
6. **Rotate 中文化（US4）**：以 **admin** 進 `/admin/providers` → 憑證操作見「重新產生金鑰」（無英文 Rotate）；功能照常。
7. **手機（360px）**：DevTools 360px → 頂部選單（漢堡）含同 5 項；各頁不溢出。

## 零回歸檢查

- 後端未改動：`/me/*`、`/v1/*`、proxy 計費皆不變。
- 線上 smoke：壞 token 打 `/v1/chat/completions` 應 401（與部署後驗證一致）。
