# Quickstart / 驗證: 配額池設定移到前端

1. **首次零行為變更**：未在 UI 設過時，`GET /admin/quota-pool/status` 的 config = 現行 env 值；rebalance 行為同現況。
2. **admin 設定**：監控頁填 T／保底 → 儲存（`PUT /admin/quota-pool/config`）→ 頁面「目前生效值」即新值。
3. **生效**：按「手動執行再分配」→ 各分配月配額以新值更新（或等每月 cron）。**全程不重部署**。
4. **建議**：建議區顯示近月用量 + 建議 T（≈2×）/保底 + 原因 → 按「套用建議」帶入表單。
5. **驗證**：把 T 設成 < 保底×N → 儲存被擋（422）；T < 近月用量 → 警告但可確認存。
6. **稽核**：改設定後於稽核紀錄可見 `pool_config_updated`。
7. **單一真理**：監控頁顯示值 == rebalance 實際用值（同 DB 來源）。

部署：後端 + 前端兩 image bump；**有 migration 0021 → `--set migrationJob.enabled=true`**；部署後驗 `alembic current = 0021`。
