# Quickstart: 管理員 Bootstrap 與部署強化

## 本地驗證

### 1. CLI 佈建（OIDC 預設）

```bash
# 乾淨 dev DB
DATABASE_URL="sqlite+aiosqlite:////tmp/bootstrap.db" uv run alembic upgrade head
DATABASE_URL="sqlite+aiosqlite:////tmp/bootstrap.db" \
  uv run python -m ai_api.cli.create_admin --email admin@org.edu --name "系統管理員"
# 預期：created admin admin@org.edu (google_oidc); will bind on first Google login

# 重跑 → idempotent
DATABASE_URL="sqlite+aiosqlite:////tmp/bootstrap.db" \
  uv run python -m ai_api.cli.create_admin --email admin@org.edu
# 預期：admin admin@org.edu already exists; no change（退出碼 0）
```

### 2. CLI 佈建（本地密碼）

```bash
DATABASE_URL="sqlite+aiosqlite:////tmp/bootstrap.db" \
  uv run python -m ai_api.cli.create_admin --email pwadmin@org.edu --provider local_password
# 預期：created admin pwadmin@org.edu; invitation: <一次性連結>
```

### 3. 啟動防呆

```bash
# production 訊號 + 預設 token → 拒絕啟動
COOKIE_SECURE=true ADMIN_BOOTSTRAP_TOKEN=local-dev-admin-only \
  uv run python -c "from ai_api.main import create_app; create_app()"
# 預期：RuntimeError（token 為空或預設值，拒絕在 production 啟動）

# production 訊號 + 自訂 token → 正常
COOKIE_SECURE=true ADMIN_BOOTSTRAP_TOKEN=$(openssl rand -hex 32) PROVIDER_KEY_ENC_KEY=... \
  uv run python -c "from ai_api.main import create_app; create_app()"
```

## K8s 部署驗證

```bash
# 渲染 chart，確認 bootstrap-admin Job 存在且排在 migrate 之後
helm template test deploy/helm/ai-api \
  --set adminBootstrapToken=$(openssl rand -hex 32) \
  --set bootstrapAdmin.enabled=true \
  --set bootstrapAdmin.email=admin@org.edu \
  --set database.url=postgresql+asyncpg://u:p@h:5432/db \
  --set providerKeyEncKey=... \
  | grep -A2 'job: bootstrap-admin'
```

## 測試

```bash
uv run pytest tests/integration/test_create_admin_cli.py \
              tests/unit/test_startup_admin_token_guard.py \
              tests/integration/test_us4_helm_template.py -v
uv run pytest          # 全套維持綠
uv run ruff check .
```

## 驗收對應

- US1（首位 admin 佈建）→ 本地驗證 1、2 + CLI 整合測試
- US2（防呆）→ 本地驗證 3 + 啟動防呆測試
- US3（文件）→ `docs/deployment.md` 可獨立帶領維運者完成部署
