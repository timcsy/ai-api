# 部署指南（Kubernetes / Helm）

本文件帶領維運者把 AI API Manager 部署到 Kubernetes，並完成首位管理員的設定。Helm chart 位於 [`deploy/helm/ai-api`](../deploy/helm/ai-api)。

---

## 1. 必填機密與設定

以 Secret（建議 sealed-secrets / external-secrets，勿明文進 git）提供下列值。對應 `values.yaml`：

| 設定（values） | 環境變數 | 必填 | 說明 |
|----------------|----------|------|------|
| `database.url` | `DATABASE_URL` | ✅ | 外部 Postgres，asyncpg。例：`postgresql+asyncpg://user:pass@host:5432/db` |
| `providerKeyEncKey` | `PROVIDER_KEY_ENC_KEY` | ✅ | Fernet 金鑰（加密 provider 憑證）。產生：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`。**缺值 pod 拒絕啟動。** |
| `adminBootstrapToken` | `ADMIN_BOOTSTRAP_TOKEN` | ✅ | 後台 break-glass 金鑰（見 §4）。**正式環境若為空或預設值，pod 拒絕啟動。**產生：`openssl rand -hex 32` |
| `baseUrl` | `BASE_URL` | ✅ | 對外網址，例：`https://aiapi.example.com`（OIDC redirect 與前端端點用） |
| `cookieSecure` | `COOKIE_SECURE` | ✅(正式) | 正式環境設 `true`（HTTPS）。同時作為「正式環境」判定訊號（見 §4） |
| `googleOauth.clientId` / `.clientSecret` | `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | OIDC 登入需要 | Google OAuth 憑證 |
| `azureOpenAI.*` | `AZURE_OPENAI_*` | 視 provider | Azure OpenAI 連線 |

遷移（`alembic upgrade head`）由 chart 內建的 `migration-job` 以 `pre-install,pre-upgrade` hook 自動執行，無需手動。

---

## 2. 首位管理員：誰是 admin？

系統有兩條管理員認證路徑：

1. **Admin member**：登入後 session 對應的成員 `is_admin=True`（後台 UI 走這條）。
2. **Bootstrap token**：帶 `X-Admin-Token: $ADMIN_BOOTSTRAP_TOKEN` 的請求（前端不使用，定位為 break-glass，見 §4）。

**全新部署的資料庫沒有任何 admin member**，OIDC 自動註冊的新成員也一律不是 admin。因此你必須佈建首位管理員，否則沒有人進得了後台。

### 自動佈建（建議）

在 `values.yaml` 設定，Helm 會以 `pre-install,pre-upgrade` hook Job（排在遷移之後、app 上線之前）執行佈建，idempotent，每次升級安全重跑：

```yaml
bootstrapAdmin:
  enabled: true
  email: "admin@org.edu"
  provider: "google_oidc"     # 或 local_password
  displayName: "系統管理員"
```

- **`google_oidc`（建議）**：建立一筆該 email、無密碼的管理員成員。該人**第一次用 Google 登入**相同 email 時自動綁定，即取得 admin session。全程不需要傳遞任何密碼或 token。
- **`local_password`**：建立管理員成員並產生一次性邀請連結，連結會印在該 Job 的 pod log（`kubectl logs job/...-bootstrap-admin-...`），管理員用它設定密碼。

行為細節：
- 指定 email 已是該 provider 的管理員 → 不重複建立、視為成功。
- 指定 email 已存在但登入方式不同 → Job 失敗並提示衝突，不覆寫既有帳號（請改用相符的 provider 或換 email）。

### 手動佈建（CLI）

也可不經 Helm，直接跑 CLI（需可連到 DB）：

```bash
python -m ai_api.cli.create_admin --email admin@org.edu --provider google_oidc
```

---

## 3. 部署流程總覽

```
helm upgrade --install ai-api deploy/helm/ai-api -f my-values.yaml
  └─ pre-* hook (weight 0): migration-job        → alembic upgrade head
  └─ pre-* hook (weight 1): bootstrap-admin-job   → 佈建首位 admin（idempotent）
  └─ Deployment 滾動更新                          → app pods（金鑰不合則拒絕啟動）
管理員 → 用 Google 登入（或邀請連結設密碼）→ 即為 admin
```

---

## 4. Bootstrap token 與啟動防呆

`ADMIN_BOOTSTRAP_TOKEN` 是一把萬能後門金鑰：任何帶此 header 的請求都被視為完整管理員。前端從不使用它，日常管理請一律走 admin member 登入。它的定位是 **break-glass（緊急救援）**，請存於 Secret、嚴格控管、定期輪替。

**啟動防呆**：當 `COOKIE_SECURE=true`（正式環境訊號）且 `ADMIN_BOOTSTRAP_TOKEN` 為空或仍是開發預設值 `local-dev-admin-only` 時，pod 會**拒絕啟動**（CrashLoopBackOff），逼你設定強隨機值。本機開發（`COOKIE_SECURE=false`）維持零設定可用。錯誤訊息不會印出 token 實際值。

---

## 5. 救援：所有管理員都失聯怎麼辦？

系統已防止「降級最後一位管理員」，但若帳號仍全數失聯（離職、信箱失效等），用以下任一方式重建一位 admin：

- **重跑佈建 Job**：調整 `bootstrapAdmin.email` 後 `helm upgrade`，或
- **一次性 CLI**：以同一 image 起一個臨時 Job 或 `kubectl exec` 進任一 pod 執行
  ```bash
  python -m ai_api.cli.create_admin --email rescue@org.edu --provider google_oidc
  ```
- **最後手段**：以 break-glass token 呼叫 admin API 建立成員並 `PATCH is_admin=true`。

---

## 6. 驗證

```bash
helm template test deploy/helm/ai-api \
  --set adminBootstrapToken=$(openssl rand -hex 32) \
  --set bootstrapAdmin.enabled=true --set bootstrapAdmin.email=admin@org.edu \
  --set database.url=postgresql+asyncpg://u:p@h:5432/db \
  --set providerKeyEncKey=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

確認渲染出 migration Job 與 bootstrap-admin Job，且後者的 hook-weight 大於前者。
