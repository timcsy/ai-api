# Phase 0 — Research

## R1：多 Provider 抽象層的選擇

**Decision**：採 `litellm` 作為 library（**不**啟用 Proxy server form），版本 pin 為 `>=1.55,<2`

**Rationale**：
- 接 100+ provider 一次到位（含未來 Ollama/vLLM），不必逐家寫 adapter
- Library form 對外只是 `litellm.acompletion()` 函式呼叫；**LiteLLM Proxy 的 CVE 集中在 admin UI / master key / virtual key 三條路徑，library form 完全不曝這些表面**
- 內建 OpenAI 相容 response normalization，符合 spec FR-002
- 從 Phase 011 的 `openai` SDK swap 角度看，這次是「轉變抽象層級」，不是「回到原樣」——這次是 multi-provider 真正用上 library 的多 provider 能力
- 版本鎖 major 1：避免 v2 不相容；patch 由 Renovate 監看

**Alternatives considered**：
- **各家官方 SDK（openai / anthropic / google-genai）+ 自寫 adapter**：~400 行 normalization；新 provider = 寫新 adapter；對 4 家以上的長期維護成本高於用 litellm
- **僅 OpenAI-compat 模式**（用 `openai` SDK 換 base_url）：Anthropic 原生 API 不相容；失去 Claude tool use 等 provider-specific 能力
- **litellm Proxy form**：直接被 spec 排除（CVE 集中、UI 重疊我們既有 admin、master key god mode）

**參考**：experience.md 「build vs adopt 教訓」——library vs service 形態必須明確；本次 spec FR 已明示 library only。

## R2：對稱加密方案

**Decision**：採 `cryptography.fernet.Fernet`（AES-128-CBC + HMAC-SHA256），單一 key from K8s Secret

**Rationale**：
- Fernet 是 audited、固定參數、ill-form 自動拒絕；不會踩 IV 重用等錯誤
- 純 Python 既有 `cryptography` 套件（已透過 `argon2-cffi` 間接帶入體系）；無新編譯期依賴
- 32 bytes base64-urlsafe key 易於 K8s Secret 表達
- 已有 audit history（PyCA cryptography 維護活躍）

**Alternatives considered**：
- **AES-GCM 直接呼**：需要自管 nonce / AAD，容易踩 nonce 重用；CP 值低
- **age**（modern file encryption）：函式庫小但社群成熟度不如 cryptography；對單欄位加密過度
- **資料庫端加密 (TDE / pgcrypto)**：把加密邊界推到 DB 邊界外，金鑰管理變成 DBA 責任；違反「應用層 own 加密邏輯」的單一責任原則

**Key rotation 策略**（spec 未要求，但留位）：
- 首版用單一 active key
- 未來加 rotation 時：欄位加 `enc_key_version`，新 key 加入時舊資料先批次重加密、再啟用新 key

**測試**：
- Roundtrip（encrypt → decrypt 一致）
- Tampered ciphertext 拒絕
- 錯誤 key 解密 raises（pod 啟動時觸發 → 拒啟動）

## R3：Fernet Key 從 K8s Secret 載入的方式

**Decision**：環境變數注入（`PROVIDER_KEY_ENC_KEY`）；Helm chart 透過 `secretKeyRef` 從 K8s Secret 取得；本機 dev 允許從 `.env` 直接設

**Rationale**：
- 沿用既有 Phase 2.5 的 cookie key 模式（`SESSION_SECRET_KEY` 也是同樣套路），運維直覺
- 不引入新基建（vault sidecar / projected volume 等）
- pod 啟動時讀 settings 並嘗試初始化 Fernet 物件；失敗即 `sys.exit(1)`，K8s 自動標 CrashLoopBackOff，event 顯示原因（SC-006）
- Helm chart 把該 Secret 標為**必要**：缺漏時 `helm template` 渲染失敗或 deployment 引用空值 → pod 啟動就死

**Alternatives considered**：
- **Projected volume + file path**：對 Fernet 沒額外好處，多一層讀檔流程
- **External-Secrets + Vault**：在 spec assumptions 已排除（沒挑供應商 + 1-2 週基建），不在本 phase 範圍

## R4：Round-Robin Provider Credential 選擇策略

**Decision**：DB 端用 `ORDER BY last_used_at ASC NULLS FIRST LIMIT 1` 挑下一個 active credential，挑中後立刻 `UPDATE last_used_at`

**Rationale**：
- 不需 application-level counter / state；horizontal scale 自動分散
- `NULLS FIRST` 讓全新加入的 key 立刻參與輪替（先做工，建立 last_used）
- 衝突可能性：兩個 worker 同時挑到相同 row → 都用沒事；下次自然輪到別人。不需要 row-level lock
- 不做 weight / least-load：spec FR-009 明示首版 round-robin，YAGNI

**Alternatives considered**：
- **Application-level counter（Redis）**：引入 Redis 為了一個 counter，過頭
- **Random**：分配不均，不滿足「輪替」語意
- **Health-aware**（看上次回應時間 / 錯誤率）：YAGNI；spec 已標 provider failover 排除

## R5：兩段過濾的執行位置

**Decision**：
1. **Catalog list/detail endpoint**（`GET /catalog/models`、`GET /catalog/models/{slug}`）：在 query level 過濾，**只回成員看得到的 model**
2. **Proxy router**：呼叫 `/v1/chat/completions` 時，**在 model lookup 之後、upstream 之前**，重跑同一個過濾 function，命中 deny 直接 403（防禦性二次檢查）

**Rationale**：
- Catalog 過濾用 SQL JOIN 一次完成（performant）；不需要 N+1
- Proxy 二次檢查存在於「前端忘記過濾」「成員直接 curl」場景，是 defense-in-depth
- 同一 function 兩處呼叫，邏輯不會分裂

**Filtering function 簽章**（不在這裡寫 code，只規格化）：

```
visible_to_member(member, models) -> list[models]
  return [
    m for m in models
    if credential_gate(m.provider) and access_policy(m, member.tags)
  ]
```

**邏輯細節**：
- `credential_gate(provider)`：`SELECT 1 FROM provider_credentials WHERE provider = ? AND status = 'active' LIMIT 1`
- `access_policy(model, member_tags)`：
  - 若 `model.denied_tags ∩ member_tags ≠ ∅` → False（deny 優先）
  - 否則若 `model.default_access == 'open'` → True
  - 否則若 `model.allowed_tags ∩ member_tags ≠ ∅` → True
  - 否則 → False

**Tag 變更立即生效**（SC-004 / FR-018）：不引入快取；每次 catalog 或 proxy 呼叫都讀 DB（百人量級沒性能問題）

## R6：CLI Migration `migrate_azure_env`

**Decision**：純 CLI 命令 `python -m ai_api.cli.migrate_azure_env`，從 settings 讀 `AZURE_OPENAI_API_KEY` / `_API_BASE` / `_API_VERSION` 建立一筆 `ProviderCredential(provider='azure_openai', label='migrated-from-env', ...)`，寫 audit `provider_credential_created` with metadata `source=env_migration`

**Rationale**：
- 不開 admin endpoint：避免 production 誤觸發（要進 pod 內執行才能跑）
- Idempotent：偵測同 provider + 相同 fingerprint 已存在則跳過、印「already migrated」
- 兩 release 策略由 deployment 流程實現（plan SC-007）；本 CLI 只處理 step 2

**Alternatives considered**：
- **Alembic migration 內做**：migration 不該知道 env；schema 變更與資料 migration 分離
- **Admin UI 按鈕**：production 風險（按錯造成重覆 / 對錯環境）

## R7：Catalog YAML Schema 擴充

**Decision**：在既有 `model_catalog` YAML 加 4 個欄位，全部**必填**：

```yaml
- slug: gpt-4o-mini
  display_name: GPT-4o mini
  provider: azure_openai            # NEW required
  default_access: open              # NEW required: 'open' | 'restricted'
  allowed_tags: []                  # NEW required (可空 list)
  denied_tags: []                   # NEW required (可空 list)
  family: gpt
  # ... 既有欄位
```

**Rationale**：
- spec FR-014 明示「admin 必須明確指定」default_access，無系統預設
- CLI loader 收到缺欄 fail-fast，error message 列出缺欄與 model slug
- 既有 YAML 升級時用 migration script 或 sed 批次補欄

**Provider 命名**：採 snake_case provider id：`azure_openai`、`openai`、`anthropic`、`gemini`（首批 4 家）

## R8：升級流程（兩 release）

**Decision**：

| Release | 程式碼路徑 | 部署動作 |
|---|---|---|
| 現況 | 只讀 env | — |
| **N+1**（transitional） | 讀 credential 時：DB 優先 → 找不到 fallback env | 部署 + 跑 `migrate_azure_env` CLI |
| **N+2**（final） | 只讀 DB，env 路徑刪除 | 部署 + Helm values 移除 `AZURE_OPENAI_API_KEY` |

**Rationale**：滿足 SC-007 zero downtime + 滿足 user 選的 Q3:B「完全移除 env」。

**測試**：US4 integration 完整覆蓋兩 release 的行為（fixture 兩種狀態各跑一次）。

## R9：與既有 Phase 2.5 `allowed_providers` 的關係

**Decision**：保留既有 `Settings.allowed_providers`；當 admin 試圖新增不在 allowlist 內的 provider credential，admin endpoint 直接 422 拒絕

**Rationale**：
- spec assumptions 明示「既有 allowlist 仍生效」
- defense-in-depth：catalog YAML 即使誤填，credential 層也擋
- 不在 allowlist 內的 provider credential 不該存在於 DB 是「絕對」原則

**測試**：contract test 確認新增不在 allowlist 的 provider 回 422 + error code `provider_not_allowed`

## R10：前端三個新 admin 視圖的資料流

**Decision**：沿用既有 TanStack Query pattern，每個視圖一個 `useQuery` + 對應 mutations；URL 不帶 filter state（與既有 admin 視圖不同——admin 操作本質是 CRUD，不需要 URL 共享）

**Rationale**：
- providers / tags / model-access 三個視圖都是 admin-only，不需要 URL 分享過濾
- 與既有 `admin/members.tsx`、`admin/allocations.tsx` 互一致
- 一次性 banner 顯示明文 key 採用既有 `AlertDialog` + `Dialog` 組合（與 token rotation 模式相同）

**測試**：Vitest + Testing Library 各加 ~5 tests / 視圖（共 ~15 frontend tests 增量）
