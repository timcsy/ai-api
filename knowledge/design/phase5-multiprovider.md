# Phase 5：多 Provider + Admin 管理憑證 + Tag-based 存取規則

## 對使用者帶來什麼

- **成員（member）**：用同一個 allocation token 可以呼叫 4 家 LLM 供應商
  （Azure OpenAI / OpenAI / Anthropic / Gemini）。看得到哪些 model 由
  admin 控制。
- **管理員（admin）**：UI 內可管理各家 provider 的 API key、把成員打 tag、
  決定哪些 tag 能用哪個 model。不再需要改 K8s Secret / Helm values 才能
  替換 provider key。

## 新增的 UI

入口：頂部 nav 點「管理員」進入後，第二行 sub-nav 列出所有 admin 頁面：

| 頁面 | 路徑 | 用途 |
|---|---|---|
| Provider 憑證 | `/admin/providers` | CRUD 各家 provider 的 API key |
| Tag | `/admin/tags` | 看現有 tag 與使用人數 + 批次貼標 |
| Model 存取 | `/admin/model-access` | 每個 model 設 default_access + allow / deny tags |

## Admin 操作手冊

### A. 新增一筆 Provider 憑證

1. 進入 `/admin/providers` 按「新增」
2. 選 provider（azure / openai / anthropic / gemini）
3. 填入 label（人類可讀標記，例「team-a-prod」）
4. 貼上 plaintext API key
5. （選填）base_url —— Azure 必填
6. 按「建立」 → **一次性 banner** 顯示明文 key + fingerprint。離開頁面後再也看不到明文。

### B. Rotate 一筆 Credential

1. 在 `/admin/providers` 列表點該筆「Rotate」
2. 貼新 plaintext key → 確認
3. **舊 key 立即失效**，新 key 立即生效。新明文一次性顯示。

### C. 為成員打 tag

兩種方式：

**單人**：到 `/admin/members/{id}` 內個別加（後端 endpoint 已可用；前端
UI 還沒在 members 頁加 inline tag chips，這是下版改進）。

**批次**：到 `/admin/tags` 按「批次貼標」→ 輸入 tag 名稱（格式
`^[a-z][a-z0-9_-]{0,63}$`）→ 多選成員 → 套用。已有此 tag 的成員會跳過。

### D. 設定 Model 的存取規則

1. 進入 `/admin/model-access`
2. 選 model（從 catalog 抓所有 model 含 deprecated）
3. 設定：
   - **default_access**：`open`（所有人可見，被 denied_tags 排除者除外）
     或 `restricted`（只有 allowed_tags 命中者可見）
   - **allowed_tags**：list of tag 字串
   - **denied_tags**：list of tag 字串（**永遠優先於 allowed**）
4. 套用 → 即時生效，不需 cache invalidation

## 兩段過濾邏輯

成員看到的 model = `credential gate ∩ access policy`：

1. **Credential gate**：model 對應 provider 至少要有 1 筆 active credential，否則隱藏
2. **Access policy**：通過 gate 後，套用：
   - 命中 denied_tags → 拒絕
   - 否則 default_access == open → 允許
   - 否則命中 allowed_tags → 允許
   - 否則 → 拒絕

Catalog `GET /catalog/models` 與 detail 都套用這個 filter；proxy
`POST /v1/chat/completions` 在 routing 前**再跑一次**（防禦性二次檢查），
被拒則回 `403 model_forbidden`。

## 升級既有 Azure 部署到 Phase 5（兩 release zero-downtime）

### Release N+1（transitional）

- Helm values 維持 `azureOpenAI.apiKey` 不動，**新增** `providerKeyEncKey`
  （用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 產生）
- 部署
- 跑 migration：

  ```bash
  kubectl exec deploy/ai-api -- python -m ai_api.cli.migrate_azure_env
  ```

- 預期輸出：`migrated 1 credential (provider=azure, label=migrated-from-env, ...)`
- 之後 proxy 自動優先使用 DB credential（env 仍作 fallback）

### Release N+2（final）—— 目前尚未實作

待 spec FR-019 第二階段：
- 把 `proxy/router.py` 內的 Azure env fallback 路徑移除
- Helm values 移除 `azureOpenAI.apiKey`

## 安全性保證（自動化驗證）

- 任何 4xx / 5xx 錯誤訊息、日誌、稽核紀錄中**完全找不到** provider plaintext key（grep test 通過）
- 加密金鑰遺失情境下，pod **拒絕啟動**且 K8s event 顯示明確原因
- Helm chart `required` function 確保 `providerKeyEncKey` 缺值時 template 就失敗

## 限制（首版排除）

- ❌ Self-hosted provider（Ollama / vLLM）UI flow
- ❌ Rule matcher（複合條件式）—— 只支援 tag 集合 AND/NOT
- ❌ Provider failover
- ❌ 按 provider 切配額池
- ❌ Provider 連線測試 endpoint（`/admin/providers/{id}/test-connection`）

## 相關檔案

- 規格：`specs/012-multi-provider-access/`
- 後端 endpoint：`src/ai_api/api/admin_{providers,tags,model_access}.py`
- 服務：`src/ai_api/services/{crypto,provider_credentials,member_tags,model_access}.py`
- 前端：`frontend/src/routes/admin/{providers,tags,model-access}.tsx`
- Migrations：`alembic/versions/0009_phase5_multiprovider_schema.py` + `0010_phase5_audit_events.py`
- Helm：`deploy/helm/ai-api/templates/secret.yaml`、`values.yaml`
