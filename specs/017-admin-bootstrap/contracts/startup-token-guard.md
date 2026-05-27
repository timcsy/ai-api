# 契約: 啟動防呆（ADMIN_BOOTSTRAP_TOKEN）

在 `create_app()` 既有 fail-fast 區塊（緊接 `get_fernet()` 後）加入一道驗證。

## 規則

```text
if COOKIE_SECURE 為 true 且 ADMIN_BOOTSTRAP_TOKEN ∈ {"", DEFAULT_ADMIN_BOOTSTRAP_TOKEN}:
    create_app() raise RuntimeError（明確訊息）
否則:
    正常建立 app
```

- `DEFAULT_ADMIN_BOOTSTRAP_TOKEN` = `"local-dev-admin-only"`（自 `config.py` 匯出之常數）。
- production 訊號 = `COOKIE_SECURE`（既有環境變數，HTTPS 部署本就開啟）。

## 行為矩陣

| COOKIE_SECURE | ADMIN_BOOTSTRAP_TOKEN | create_app() |
|---------------|------------------------|--------------|
| true | `local-dev-admin-only`（預設） | raise RuntimeError |
| true | `""`（空） | raise RuntimeError |
| true | 自訂強值 | 正常 |
| false | `local-dev-admin-only` | 正常（保留 dev 零設定） |
| false | `""` | 正常 |

## 訊息契約

- 錯誤訊息 MUST 指出「token 為空或為預設值、拒絕在 production 啟動」與修正方向。
- 錯誤訊息 MUST NOT 包含 token 的實際值。

## 與既有行為的相容性

- 既有 `require_admin` 兩條路徑（X-Admin-Token / admin session）邏輯不變。
- dev 與既有 274 admin_headers 測試（`COOKIE_SECURE` 預設 false）不受影響。
