# CLI 契約: `ai_api.cli.create_admin`

首位管理員佈建指令。idempotent，供 Helm hook Job 或維運者手動執行。

## 呼叫方式

```bash
python -m ai_api.cli.create_admin --email <EMAIL> [--provider google_oidc|local_password] [--name <DISPLAY_NAME>]
```

## 參數

| 參數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `--email` | 是 | — | 首位管理員 email（正規化為小寫比對） |
| `--provider` | 否 | `google_oidc` | 登入方式 |
| `--name` | 否 | email | 顯示名稱 |

設定來源：`DATABASE_URL` 等經 `get_settings()` 由環境讀取（與其他 CLI 一致）。

## 行為與退出碼

| 情境 | 動作 | stdout | 退出碼 |
|------|------|--------|--------|
| email 不存在（`google_oidc`） | 建立無密碼成員 + 升級 admin | `created admin <email> (google_oidc); will bind on first Google login` | 0 |
| email 不存在（`local_password`） | 建立成員 + 升級 admin + 發邀請 | `created admin <email>; invitation: <one-time-link>` | 0 |
| email 已存在、provider 相符、已是 admin | no-op | `admin <email> already exists; no change` | 0 |
| email 已存在、provider 相符、非 admin | 升級為 admin | `promoted existing member <email> to admin` | 0 |
| email 已存在、provider 不符 | 拒絕，不變更 | （stderr）`refusing: <email> exists with provider <other>` | 非 0 |
| 資料表結構未就緒 | 失敗 | （stderr）明確錯誤 | 非 0 |
| 缺 `--email` | 失敗 | （stderr）用法說明 | 非 0 |

## 不變式

- **idempotent**：相同 `--email`／`--provider` 重跑任意次，結果一致且退出 0（不重複建立、不報錯）。
- **不洩漏密鑰**：不印出 bootstrap token；OIDC 路徑不印任何密鑰；local_password 僅印一次性邀請連結。
- **不繞過保護**：只升級 admin，不執行降級，不影響「不可降級最後一位 admin」保護。
- **不改 schema**：僅 INSERT/UPDATE `members`（與既有 service 相同路徑）。
