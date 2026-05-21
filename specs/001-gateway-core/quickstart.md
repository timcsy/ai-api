# Quickstart: 階段 1 — 分流核心

本檔給開發者一個最小可行的「跑起來、驗證一遍、撤回一遍」流程，用以核對
spec 的 Acceptance Scenarios 與 Success Criteria。**所有指令均以 repo root
為 cwd**。

---

## 0. 先決條件

- Python 3.11+ 與 `uv`（或 `pip` + venv）
- Docker（跑 Postgres）
- Azure OpenAI 已部署至少一個模型 deployment，並準備好：
  - `AZURE_OPENAI_API_BASE`（例：`https://my-resource.openai.azure.com`）
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_API_VERSION`（例：`2024-06-01`）
  - 一個 deployment 名稱（例：`gpt-4o-mini-prod`）

---

## 1. 啟動本機依賴

```bash
docker compose -f deploy/docker-compose.yml up -d postgres
```

設定 `.env`（或匯出環境變數）：

```bash
DATABASE_URL=postgresql+asyncpg://aiapi:aiapi@localhost:5432/aiapi
ADMIN_BOOTSTRAP_TOKEN=local-dev-admin-only
AZURE_OPENAI_API_BASE=https://my-resource.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-06-01
```

跑 migration、啟服務：

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn ai_api.main:app --reload --port 8000
```

驗證健康：

```bash
curl -s localhost:8000/healthz
# {"status":"ok"}
```

---

## 2. 驗證 User Story 1：建立分配並代理呼叫

**建立分配**：

```bash
curl -s -X POST localhost:8000/admin/allocations \
  -H "X-Admin-Token: local-dev-admin-only" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "alice@example.com",
    "resource_model": "gpt-4o-mini-prod",
    "note": "Alice 試用"
  }'
```

回應形如：

```json
{
  "id": "01J...",
  "subject": "alice@example.com",
  "resource_model": "gpt-4o-mini-prod",
  "status": "active",
  "created_at": "2026-05-21T...",
  "created_by": "bootstrap-admin",
  "token_prefix": "aiapi_xy",
  "token": "aiapi_xy....FULL_TOKEN..."
}
```

**保留 `token`**——之後**不會再有第二次機會**取得明文。

**以該憑證代理呼叫**：

```bash
curl -s -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer aiapi_xy....FULL_TOKEN..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini-prod",
    "messages": [{"role":"user","content":"hello"}]
  }'
```

**驗證**：
- 回應內容來自 Azure OpenAI
- 回應 body、headers、伺服器日誌中**找不到** `AZURE_OPENAI_API_KEY` 的明文
  → 對應 SC-003

---

## 3. 驗證 User Story 2：撤回後即刻拒絕

```bash
# 撤回
curl -s -X DELETE localhost:8000/admin/allocations/<ALLOCATION_ID> \
  -H "X-Admin-Token: local-dev-admin-only"
```

**5 秒內**再用同一憑證呼叫：

```bash
curl -s -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer aiapi_xy....FULL_TOKEN..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini-prod","messages":[{"role":"user","content":"hi"}]}'
```

預期回應：

```json
{ "error": { "code": "allocation_revoked", "message": "...", "request_id": "..." } }
```

→ 對應 SC-002

**冪等性**：再次 `DELETE` 同一 ID，應回應 200 + status=revoked，不視為錯誤。

---

## 4. 驗證 User Story 3：呼叫可追溯

```bash
curl -s "localhost:8000/admin/allocations/<ALLOCATION_ID>/calls?limit=10" \
  -H "X-Admin-Token: local-dev-admin-only"
```

預期看到：步驟 2 的成功呼叫 + 步驟 3 的拒絕呼叫，皆帶 `request_id`、`outcome`、
`status_code`、token 用量。

→ 對應 SC-004

額外驗證匿名拒絕：
```bash
curl -s -X POST localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer aiapi_nope" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini-prod","messages":[]}'
```
這次呼叫在 CallRecord 中 `allocation_id=null`、`outcome=rejected_unauthenticated`
——對應 FR-013，不歸屬任何分配。

---

## 5. 驗證 User Story 4：宣告式部署 + 安全更新

**部署到開發叢集**（kind / 真實 dev cluster 皆可，但**本機不需要**跑 K8s
也能完成 1~4 的驗證）：

```bash
helm install ai-api ./deploy/helm/ai-api \
  --namespace ai-api --create-namespace \
  --set azureOpenAI.apiKey=$AZURE_OPENAI_API_KEY \
  --set azureOpenAI.apiBase=$AZURE_OPENAI_API_BASE
```

驗證：
```bash
kubectl -n ai-api get pods
kubectl -n ai-api port-forward svc/ai-api 8000:80
# 然後重跑步驟 2~4
```

**模擬失敗更新並回滾**：

```bash
# 故意升級到一個不存在的 LiteLLM tag
helm upgrade ai-api ./deploy/helm/ai-api \
  --reuse-values \
  --set image.litellmTag=does-not-exist

# 觀察 readiness 失敗，回滾
helm rollback ai-api
```

→ 對應 SC-006（≤ 5 分鐘恢復）

---

## 6. 跑完整測試套件

```bash
# 單元 + 契約測試（快）
uv run pytest tests/unit tests/contract

# 完整三層（含整合，會需要 Postgres + Azure OpenAI sandbox）
uv run pytest
```

CI 必跑全部；本機 push 前建議至少跑 unit + contract。

---

## 對應的 Success Criteria 檢核表

| SC | 如何在本 quickstart 驗證 |
|---|---|
| SC-001 | 步驟 2 全程 < 1 分鐘 |
| SC-002 | 步驟 3 撤回後拒絕 |
| SC-003 | 步驟 2 結束時抓回應 + log，grep `$AZURE_OPENAI_API_KEY` 應 0 命中 |
| SC-004 | 步驟 4 查詢可看到所有呼叫並反查 subject/resource_model |
| SC-005 | 步驟 5 從 helm install 到 healthz=ok ≤ 10 分鐘、指令 ≤ 5 |
| SC-006 | 步驟 5 後段 rollback ≤ 5 分鐘 |
| SC-007 | 步驟 6 contract 套件全綠 |
| SC-008 | `git log -- tests/ src/` 應顯示測試 commit 早於對應實作 commit |
