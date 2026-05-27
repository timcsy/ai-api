# Phase 1 Data Model: 管理員 Bootstrap 與部署強化

本功能**不新增資料表、不變更 schema、不新增 migration**。僅複用既有 `Member` 實體。

## 既有實體（僅參照，不變更定義）

### Member（`src/ai_api/models/member.py`）

佈建動作會建立／升級的既有實體。相關欄位：

| 欄位 | 說明 | 佈建行為 |
|------|------|----------|
| `id` | ULID | 新建時產生 |
| `email` | 唯一、正規化為小寫 | 佈建以此比對 idempotent / 衝突 |
| `provider` | `local_password` / `google_oidc` | 由 `--provider` 決定；既有成員 provider 不符 → 拒絕 |
| `display_name` | 顯示名稱 | 由 `--name` 或預設 email |
| `is_admin` | 管理員旗標（預設 False） | 佈建確保為 True（`set_is_admin`） |
| `status` | `active` / `disabled` | 新建為 active |
| `password_hash` | 本地密碼雜湊 | OIDC 路徑為 None；密碼路徑經邀請設定 |
| `created_by` | 建立來源標記 | 佈建以 `"bootstrap-cli"` 標記，與既有 `"bootstrap-admin"`/`"auto_register"` 區別 |

### 狀態轉移（佈建視角）

```text
(無此 email) ──create(provider, send_invitation)──▶ Member(status=active, is_admin=False)
                                                          │
                                            set_is_admin(True)
                                                          ▼
                                                 Member(is_admin=True)   ← 佈建完成

(email 已存在, provider 相符) ──set_is_admin(True)──▶ no-op 若已是 admin；否則升級
(email 已存在, provider 不符) ──▶ 拒絕（不變更）
```

## 設定值（非持久化實體，供部署編排）

| 設定 | 來源 | 用途 |
|------|------|------|
| `bootstrapAdmin.enabled` | Helm values | 是否啟用佈建 Job |
| `bootstrapAdmin.email` | Helm values → CLI `--email` | 指定首位 admin email |
| `bootstrapAdmin.provider` | Helm values → CLI `--provider` | 登入方式（預設 `google_oidc`） |
| `bootstrapAdmin.displayName` | Helm values → CLI `--name` | 顯示名稱（可選） |
| `DEFAULT_ADMIN_BOOTSTRAP_TOKEN` | `config.py` 常數 | 防呆比對的已知預設值字面值 |
| `COOKIE_SECURE` | 既有環境變數 | production 判定訊號 |
