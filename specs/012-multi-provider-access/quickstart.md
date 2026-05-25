# Quickstart：Phase 5 多 Provider 場景驗證

> 給 admin 上手 + 給驗收者跑「能不能用」的最短路徑。

## 前置條件

- 已部署 Phase 5 release N+1 或 N+2（K8s）；本機 dev 環境也適用
- 環境變數 `PROVIDER_KEY_ENC_KEY`（dev）或 K8s Secret 已注入（production）
- 已存在 1 個 admin 帳號（透過 `ADMIN_BOOTSTRAP_TOKEN` 或既有 admin promote 流程）

## 場景 A：Admin 加入第一筆 Anthropic credential 並驗證代理

1. **登入 admin web UI**：開瀏覽器到 `/admin/login`（local password 或 Google SSO）
2. **新增 Anthropic credential**：
   - 進入 `/admin/providers` → 「新增」
   - 選 provider `anthropic`、label 填 `team-a-anthropic-prod`、貼上 plaintext API key
   - 按確認；UI 出現一次性 banner 顯示明文 key 與 fingerprint（**離開頁面後永遠看不到明文**）
3. **載入 Anthropic model 到 catalog**：
   - 在 catalog YAML 加入 `claude-3-5-sonnet`，欄位包含 `provider: anthropic`、`default_access: open`、`allowed_tags: []`、`denied_tags: []`
   - 跑 `python -m ai_api.cli.load_models <yaml>` upsert
4. **驗證 member 看得到 + 用得到**：
   - 任一 active member 登入，到 `/catalog` 應看到 `claude-3-5-sonnet`
   - 該 member 拿一筆 active allocation 的 token，跑：
     ```bash
     curl https://<host>/v1/chat/completions \
       -H "Authorization: Bearer $TOKEN" \
       -H "Content-Type: application/json" \
       -d '{"model":"claude-3-5-sonnet","messages":[{"role":"user","content":"hi"}]}'
     ```
   - 應回 200 + OpenAI 相容 response schema

**通過判準**：第 4 步 curl 200 且 response 含 `choices[0].message.content`。

## 場景 B：Tag-based 存取限制

1. **建立 2 個 member**（沿用既有 admin members CRUD）：alice、bob
2. **為 alice 加 tag**：
   - 進入 `/admin/members/{alice_id}` → tags 區段 → 加 `eng`
3. **限制 model 給 `eng`**：
   - 進入 `/admin/catalog/models/claude-3-5-sonnet/access`
   - 設定 `default_access: restricted`、`allowed_tags: ["eng"]`、`denied_tags: []`
4. **驗證可見性**：
   - alice 拿 token 呼叫 `GET /catalog/models` → 含 `claude-3-5-sonnet`
   - bob 拿 token 呼叫同 endpoint → **不**含
   - bob 直接 curl `/v1/chat/completions` 指定 `claude-3-5-sonnet` → 回 403 `model_forbidden`
5. **批次貼標**：
   - 進入 `/admin/tags` → bulk apply
   - 選 `eng` + 多選 [bob, charlie, dave]
   - 確認後 3 人立即擁有 `eng`；bob 再呼叫 catalog 立刻看到 claude

**通過判準**：第 4 步三項全對 + 第 5 步 bob 重呼可看到。

## 場景 C：Credential rotation 即時生效

1. **抓 active credential id**：`/admin/providers` 列表中複製 Azure credential id
2. **rotate**：點該 row 的 rotate；貼新 plaintext key；確認
3. **舊 key 立刻無效**：跑一條用舊 key 的 upstream 呼叫（如果有保留外部測試 script），應 fail
4. **新 key 立刻接管**：跑 member proxy 呼叫，應回 200

**通過判準**：rotation 後 10 秒內所有 worker 用新 key（SC-003）。

## 場景 D：升級既有 Azure env 部署到 Phase 5（兩 release）

### Step 1：部署 Release N+1（transitional）

- 不動 Helm values：`AZURE_OPENAI_API_KEY` env 仍在
- 部署新 image
- 預期行為：DB 中尚無 Azure credential → upstream fallback 讀 env → 既有呼叫不中斷

### Step 2：跑 migration CLI

```bash
kubectl exec deploy/ai-api -- python -m ai_api.cli.migrate_azure_env
```

- 預期 stdout：`migrated 1 credential (provider=azure_openai, label=migrated-from-env)`
- 重複跑：`already migrated, skip`
- 驗證：`/admin/providers` 列表出現該筆 credential
- 此時行為：DB 有 credential → upstream 優先用 DB，env 不再被用

### Step 3：部署 Release N+2（final）

- Helm values 移除 `AZURE_OPENAI_API_KEY`
- 部署新 image（程式中 env fallback 路徑已刪）
- 預期：呼叫仍正常；env 完全不再被讀

**通過判準**：三個 step 之間 zero downtime；任何時間點 `/v1/chat/completions` 用合法 token 呼叫都應 200。

## 場景 E：加密金鑰遺失（負面測試）

1. 故意把 `PROVIDER_KEY_ENC_KEY` 從 Helm Secret 移除
2. 重新部署
3. **預期**：pod 拒絕啟動，K8s event 顯示 `PROVIDER_KEY_ENC_KEY missing or invalid`
4. 把 Secret 補回，pod 重新啟動正常

**通過判準**：SC-006 — 不會以「半啟動」狀態跑。

---

## Smoke test（自動化版本，CI 與本機可跑）

```bash
# 從 repo root
pytest tests/integration/test_us1_multiprovider.py -v
pytest tests/integration/test_us2_credential_ui.py -v
pytest tests/integration/test_us3_tag_access.py -v
pytest tests/integration/test_us4_azure_env_migration.py -v
pytest tests/integration/test_credential_rotation_immediacy.py -v
```

期待：全部綠燈。
