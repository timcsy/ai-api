# 已完成階段：細部成功標準（封存）

本檔保存階段 1–8 的完整成功標準 / 核心原則 / 明確排除，作為詳細歷史紀錄。
`vision.md` 的〈路線圖〉只保留每個已完成階段的標題、完成標記與「交付」一句，
細節在此查閱。**未完成 / 規劃中的階段（3b.7、9、10）細節仍留在 vision.md。**

---

## 階段 1：分流核心可運作

完成（2026-05-21：本機 + k3s-tew 叢集全部 SC 達標）。前置：無。

**成功標準：**
- [x] 自製 FastAPI gateway 本機可運作（uvicorn）
- [x] K8s 部署以宣告式定義（Helm/Kustomize）並可在開發叢集驗證
- [x] 相依套件版本以自動化方式追蹤上游，且有回滾路徑
- [x] Azure OpenAI 串接成功，可代理至少一個模型
- [x] 可手動建立一筆「分配」並取得獨立憑證
- [x] 該憑證的呼叫可追溯到分配 ID
- [x] 撤回後該憑證立即失效

## 階段 2：身份驗證與成員管理

完成（2026-05-22；UI 留階段 3，本階段為後端 + admin API + 必要 HTML）。前置：階段 1。

**成功標準：**
- [x] 認證機制抽象化（可擴展介面），首發實作 Google Workspace SSO + Local password
- [x] 管理員可手動加入 email 至白名單
- [x] 管理員可設定自動註冊條件（例：email 網域）
- [x] 可設定登入來源限制（IP/網段等基本控管）
- [x] 管理員可由 admin API 建立、查看、撤回成員的分配（UI 留階段 3）
- [x] 一般成員登入後可看到自己的憑證與用量

## 階段 2.5：安全加固 (Hardening)

完成（2026-05-22；deploy artifacts 已交付，叢集端 SC-002 待人工驗證）。前置：階段 2。
交付：把 Phase 1 + 2 的已知攻擊面收緊到「可放心對組織內部開放」的水準，不引入新功能。

**成功標準（核心三件）：**
- [x] **應用層 provider allowlist**：`Settings.allowed_providers`；未列出的供應商即使配置存在也拒絕（FR-001~003 + 4 contract tests 通過）
- [x] **K8s NetworkPolicy（粗粒度）**：Helm template 已交付，deny-all egress + allow {DNS, Postgres podSelector, 443/TCP}，封 169.254.0.0/16（5 個 helm-template 結構測試通過；叢集生效需 CNI 支援）
- [x] CI 整合 **Trivy**：`image.yml` workflow 加 trivy-action@0.24.0 + `.trivyignore`，HIGH/CRITICAL 即擋
- [x] **per-allocation quota + 異常用量警報**：anomaly_detector service + CronJob template；3 個 integration test 涵蓋 baseline-spike / cold-start under / over absolute（實測 1101 calls 觸發 quarantine）

**成功標準（次要）：**
- [x] Pod `securityContext` 強化：`readOnlyRootFilesystem` + ALL caps drop + `allowPrivilegeEscalation: false` + tmp/cache emptyDir
- [x] 失敗登入額外加 **per-IP** rate limit（同 IP 10 失敗 → 鎖 15 min；2 contract tests）
- [x] 切換 base image 為 **distroless**（`gcr.io/distroless/python3-debian12:nonroot`）

**明確排除（留更後階段）：**
- ❌ FQDN-aware egress (Cilium / Envoy sidecar) — 文件記錄為候選升級
- ❌ cosign image 簽章 + admission controller（需建立簽章基建）
- ❌ external-secrets + Vault/KMS 接通（需挑選 KMS 供應商）

## 階段 2.6：供應鏈 / Scanner 加固 (Supply Chain Hardening)

完成（2026-05-22；140 tests 全綠，含 6 新 workflow-pinning tests）。前置：階段 2.5。
交付：把 Phase 2.5 引入的 Trivy 與 image build 流程從「能用」拉到「能信」—— 消除 mutable action / mutable scanner version、加上排程重掃、SBOM 與第二掃描器交叉驗證。

**成功標準（核心兩件）：**
- [x] **所有 workflow `uses:` ref pin commit SHA**（包含 image.yml、ci.yml、scheduled-scan.yml；test_workflow_pinning.py 驗證）；Trivy CLI 版本 `v0.70.0` pin
- [x] **`scheduled-scan.yml`**：每週一 06:00 UTC + workflow_dispatch；拉最新 successful image build 重掃；HIGH/CRITICAL 自動以 CVE id 去重開 GitHub issue

**成功標準（次要）：**
- [x] `scan-type: fs` step 掃 lockfile（在 docker build 前 fail-fast）
- [x] SBOM (CycloneDX) artifact 上傳，retention 90 天
- [ ] 季度跑 OSV-Scanner 或 Grype 作第二意見（人工流程，knowledge/design/supply-chain.md 紀錄）

**明確排除（留後階段或不做）：**
- ❌ 自架 trivy-server + 私有 vuln DB mirror（YAGNI，小團隊不需要）
- ❌ cosign image 簽章 + admission control（仍延後；範圍同 2.5 排除項）

## 階段 3a：用量觀測與費用計算（後端）

完成（2026-05-22；134 tests 全綠）。

**成功標準：**
- [x] 可按分配對象切分查看用量（每人／每分配／每模型；團隊維度延後）
- [x] 可看每個分配的歷史請求數、token 數（含時間序列）
- [x] 可設定／調整單筆分配的配額上限（月度，UTC 月初錨點）
- [x] 可標記哪些分配是「高額度服務用」（`is_service_allocation` boolean）
- [x] 維護一份可更新的價目資料來源（YAML 人工，CLI 載入 — Azure 主要模型）
- [x] 可由分配 ID 查到該分配累積費用（按時間區間）；費用可按 Member ／ 模型切分
- [x] 價目更新時，歷史紀錄使用「呼叫當時的價目」計算（point-in-time，FR-013）
- [x] CSV / JSON 匯出
- [x] CORS 預備（為 3b SPA 鋪路；cors_origins 非空時 SameSite=None+Secure）

## 階段 3b：管理員 Web UI（3b.0~3b.6 完成，3b.7 待開）

> 拆小子階段，每個 1 PR。3b.7（Playwright E2E + final polish）狀態見 vision.md。

- **3b.0 Stack + 基礎建設** ✅ — React 19 + Vite + shadcn/ui + Helm Ingress 分流 + 5 unit tests + login/home/404
- **3b.1 Member view** ✅ — dashboard + allocation detail (cursor pagination) + catalog browse + catalog detail + copy curl；backend 199 tests + frontend 43 tests
- **3b.2~3b.6 Admin suite** ✅（合併單一 PR）— 5 admin 視圖 (members CRUD / allocations CRUD / usage CSV+JSON / quota-pool monitor + manual trigger / rebalance-log)；Member.is_admin 雙軌認證 (c-β additive)；backend 210 tests + frontend 50 tests

## 階段 3c：自適應配額池（馬太效應 + 能量守恆）

完成（2026-05-22；167 tests 全綠，含 11 unit + 8 integration + 7 contract + 1 proxy 即時性）。前置：3a。
交付：每月自動再分配 quota，用量高的拿更多、低的被壓縮；總量守恆。

**核心原則：**
- **能量守恆**：`Σq_i = T`（T 為池總量），rebalance 前後不變，除非 admin 動 T
- **馬太效應**：上月用量越多 → 下月 quota 越大（按比例 + 保底）

**成功標準：**
- [x] `Settings.pool_total_tokens_per_month` 與 `pool_floor_per_allocation` 可設；資源池僅涵蓋**非服務型 active allocations**
- [x] 每月 UTC 月初由 CronJob 自動 rebalance；演算法：`q_i_new = floor + (T - floor*N) * (usage_i / Σ usage)`
- [x] 守恆檢核：rebalance 結束時 `Σq = T` assertion 通過（compute + apply 雙層）
- [x] **保底**：每個 allocation 即使上月零用量也至少拿到 `floor`
- [x] **`quota_locked` 旗標**：admin 手動設的 quota 不被 rebalance 覆寫；被鎖住的 quota 從 T 中扣除，剩餘給池內動態分配
- [x] **服務型分配豁免**：`is_service_allocation=true` 不進池、quota 由 admin 獨立管理
- [x] 新增 `RebalanceLog` 表記錄每次再分配前後的 quota（含 algorithm_version 欄位以便未來升 v2）
- [x] Edge: 新分配加入只拿 floor 直到下次月初；`floor * N > T` 即 `pool_exhausted_by_reserved`，rollback 並寫 audit

**明確排除：**
- ❌ 即時池容量視覺化（留 3b UI）
- ❌ 多池（按 model / Team 切池）— 首版單一全域池
- ❌ 跨月借貸 / 過期 token roll-over

## 階段 4：模型目錄 + 多面向 Filter

完成（2026-05-23；194 tests 全綠：10 unit + 12 contract + 5 integration on top of 167 prior）。前置：階段 1。
交付：類 Azure Foundry 的模型目錄；以「模型」為第一公民、提供 modality / capability / cost_tier / recommended_for 等多 facet filter；faceted counts API 讓 UI 直接渲染 sidebar。

**成功標準：**
- [x] `model_catalog` 表 + Alembic migration 0006
- [x] 首版 YAML 含 ≥ 8 個 Azure OpenAI 主力模型（實際 9：gpt-4o, gpt-4o-mini, o1-mini, o3-mini, text-embedding-3-small/large, dall-e-3, whisper-1, tts-1）
- [x] `GET /catalog/models` 多面向 filter，list 欄位 AND 語意（`?capability=vision&capability=function-calling&cost_tier=low` → 唯一命中 gpt-4o-mini）
- [x] `GET /catalog/filters` 回 faceted counts，schema 穩定（空 DB 與有資料 DB 回相同 dimension key 集合）
- [x] `GET /catalog/models/{slug}` 含 `example_request`（curl + JSON body）
- [x] CLI `python -m ai_api.cli.load_models <yaml>` upsert by slug；idempotent；YAML 未列出的 model **不刪除**（防事故 wipe，FR-005）
- [x] 棄用隔離：`status=deprecated` 不出現在預設列表，但 detail 仍可查到含 `deprecation_note`
- [x] 任何 active member 可看（新 `require_active_member` 依賴；無認證 401、disabled 403）

**明確排除（留 3b 或後階段）：**
- ❌ UI / 視覺呈現（留 3b SPA）
- ❌ 整合到「建立 allocation」流程作為 model picker（留 3b）
- ❌ 從 Azure 自動同步 model 清單（YAGNI）
- ❌ 即時定價（cost_tier 而非絕對價；knowledge/design/model-catalog.md 記載未來整合 SOP）

## 階段 5：多 Provider + Credential 管理 + Tag-based 存取規則

完成（2026-05-25；320 backend tests + 56 frontend tests 全綠；PR #12）。前置：階段 4。
交付：成員可使用多家 LLM 供應商（首批 4 家）；admin 在 UI 管理 provider API key 與成員存取規則；catalog 對成員的可見性 = credential gate ∩ access policy。

**核心原則：**
- **Credential gate**：admin 沒加對應 provider 的 key → 該 provider 的 model 對所有成員隱藏
- **Access policy**：通過 credential gate 後，再以 model 的 access policy + member 的 tag 過濾誰看得到、用得到
- **Tag 為主、規則為輔**：每個 model 設「允許 tag」「禁止 tag」；admin 為 member 打 tag 即可批次授權，不需逐人指定

**成功標準（核心五件）：**
- [x] **多 provider 接入**：`upstream.py` 用 `litellm`（library only），首批支援 Azure OpenAI / OpenAI cloud / Anthropic / Gemini；catalog 載入對應 model。Azure + Anthropic 有整合測試（`test_us1_multiprovider`）；OpenAI / Gemini 已配置 catalog YAML 並走 routing fixture，完整 4-provider contract matrix 留 T014 deferred
- [x] **ProviderCredential 實體**：admin CRUD endpoints + Fernet 加密欄位 + 建立時一次性顯示明文 + fingerprint + rotation + 停用 + 稽核事件（`provider_credential_created/rotated/disabled`）
- [x] **加密金鑰**：`PROVIDER_KEY_ENC_KEY` 由 K8s Secret 提供；Helm template 標示 Secret 為必要、缺則 pod 拒啟動
- [x] **MemberTag join table（無獨立 Tag entity）+ Model access policy**：`MemberTag(member_id, tag, ...)` composite-PK 表，tag 名稱集合由 `SELECT DISTINCT` 推導（YAGNI，未來需要 metadata 再升 Tag entity）；`ModelCatalog` 加 `default_access` (`open` / `restricted`) + `allowed_tags` + `denied_tags`；catalog list / detail endpoint 套用過濾；proxy 呼叫時防禦性二次檢查
- [x] **Admin UI**：
  - `/admin/providers`：list + 新增（一次性 banner 顯示明文）+ rotate + 停用 + 測試連線
  - `/admin/tags`：tag CRUD + bulk 批次貼標（select members → apply tag）
  - `/admin/model-access`：選 model → 設定 default_access + allow / deny tags（後端 endpoint：`PATCH /admin/catalog/models/{slug}/access`）
  - `/admin/catalog-manage`：列現有 catalog model + 新增 + 移除（後端 endpoints：`GET/POST/PATCH/DELETE /admin/catalog/models[/{slug:path}]`，含 audit）

**成功標準（次要）：**
- [x] 既有 `AZURE_OPENAI_API_KEY` env 提供 migration script 灌入 DB 後可移除
- [x] Provider 加 `test-connection` endpoint（`POST /admin/providers/{id}/test-connection`，回 `{ok, model, latency_ms}` 或 `{ok:false, error_type, message}`；UI 含「測試連線」按鈕）
- [x] 同 provider 多把 key 採 round-robin 或最少用量（首版 round-robin 即可）

**明確排除（留更後）：**
- ❌ Self-hosted provider（Ollama / vLLM）UI 與 health-check 流程
- ❌ Rule matcher（複合條件式）— 首版只支援單 tag 集合的 AND / NOT
- ❌ Provider failover（A 家掛了自動轉 B 家）— YAGNI 直到真的有需求
- ❌ 按 provider 切配額池（沿用 3c 全域池）

## 階段 5.1：管理員 UX 整併

完成（2026-05-25；PR #13）。前置：階段 5。
交付：階段 5 把 admin 功能逐一加成 11 個入口後過於零散；本階段以「使用者旅程」重新收斂成 6 個入口，不加新功能。

**成功標準：**
- [x] sub-nav 由 11 條整併為 **6 條**（首頁 / Model / 成員 / Tag / Provider 憑證 / 觀測）
- [x] 路由整併：`/admin/model`、`/admin/member`、`/admin/tag`、`/admin/observability`（觀測為 usage / quota / rebalance / audit 的 nested hub）
- [x] 舊深層連結以 React Router redirect 保留回溯相容（9 條 legacy → 新位置）
- [x] 抽出可複用的 `VisibilityDiagnose` 面板（含修復 CTA），跨 model / member 詳情共用

**明確排除（留後續 polish）：**
- ❌ 新頁的 RTL 測試（T018-T020）、AllocationCreateDialog 元件抽出 — 非阻塞

## 階段 5.2：規則自動標籤

完成（2026-05-26；後端 311 / 前端 69 全綠；PR #14）。前置：階段 5（Tag-based 存取）。
交付：admin 定義有序規則，新成員**首次註冊**時 first-match-wins 自動貼 tag；auto tag 與既有 tag 完全等價地進入 access policy，只多一個 `source=auto` 來源標記。

**核心原則：**
- **只在首次註冊跑**：規則評估是 cold path 單次，不在登入 hot path 重算
- **first-match-wins**：由上而下評估，套用第一條命中的規則；`always` 作為 fallback

**成功標準：**
- [x] `TagRule` 實體（order / matcher_type / pattern / tag / enabled）+ admin CRUD + 排序 + 「測試 email」dry-run（`/admin/tag-rules` 共 6 endpoints）
- [x] 4 種 matcher：`email_localpart_regex`（學號）/ `email_suffix` / `email_domain` / `always`（catch-all fallback）
- [x] **regex 防 ReDoS**：自動 anchor `^(?:...)$` + local-part ≤64 截斷 + 巢狀量詞 / 複雜度檢查；**不引入 re2**（cold-path 單次評估，護欄足夠）
- [x] 在 `_find_or_create_oidc_member`（OIDC 自助註冊）+ `MemberService.create`（admin 建立）兩個點掛 hook；包 try/except，**永不讓註冊流程崩潰**
- [x] `MemberTag` 加 `source`（manual / auto）+ `rule_id`；auto 貼 tag 寫稽核 `member_tag_added` details `source=auto, rule_id`
- [x] 前端規則頁掛在 Tag 區（**不增加第 7 條 sub-nav**）；成員詳情頁 auto tag 加「自動」徽章

**明確排除（留後續）：**
- ❌ 多重 auto tag（首版 first-match 單一 tag）
- ❌ 定期重算 / email 變更時重算（YAGNI；只首次註冊觸發）

## 階段 6：自助領取憑證

完成（2026-05-26；後端 335 / 前端 72 全綠；PR #15）。前置：階段 5（access policy）。
交付：把「取得可用憑證」從 admin 逐筆建立，變成成員自助。admin 逐 model 開放（`self_service_enabled` + 預設配額），被 access policy 允許的成員在儀表板一鍵領取一張 allocation；領到的與 admin 手動建立完全等價。

**核心原則：**
- **資格 = 既有可見性 ∩ 開放旗標**：複用 `evaluate_visibility`，不另立判定
- **撤回保有止血意義**：撤回自助 allocation 後鎖定該（成員, model），admin 解鎖前不可重領

**成功標準：**
- [x] `ModelCatalog` +`self_service_enabled`/+`self_service_default_quota`；`Allocation` +`origin`
- [x] `POST /me/allocations`（current_member + CSRF）資格五查（active / 開放 / 可見 / 未持有 / 未鎖定）
- [x] 自助 allocation 與手動完全等價（呼叫 / 計量 / quota pool / 撤回）
- [x] 撤回掛 `AllocationService.revoke`：`origin=self_service` 建 `self_service_reclaim_locks`；admin 解鎖端點
- [x] 前端：儀表板「可自助領取」+ 領取 + token 一次性；admin model 開關+配額；觀測→分配 鎖定列表+解鎖
- [x] `api-client` 非 GET 自動帶 CSRF（修好全 app /me mutation）

**明確排除（留後續）：**
- ❌ 自助調整自己配額 / 自助升級 model；審批流 / email 通知（YAGNI）

## 階段 7：價目表管理 UI

完成（2026-05-27；PR #16 / #17 / #20）。前置：階段 3a（pricing 後端）、階段 5（多 provider）。
問題：價目表（`price_list`，point-in-time 計費）原本只有後端——靠手寫 YAML + `python -m ai_api.cli.load_prices` 載入，admin 介面上看不到也改不了；且階段 5 之後的多 provider 新模型沒價目 → 成本算成 0。
交付：admin 在 UI 檢視 / 新增價目版本，沿用既有 point-in-time（不改歷史帳）。

**成功標準：**
- [x] admin 可在 UI 列出各 (provider, model) 生效價目 + 歷史版本（依 `effective_from`，標「目前生效 / 排程生效」）
- [x] admin 可新增價目版本，append-only 不覆寫歷史；單位可切每 1M / 每 1K + 常見供應商範本 + 自由指定 model
- [x] 涵蓋現行多 provider 模型；缺價目的模型 UI 標「未定價」
- [x] 沿用 `lookup_price_for_call` point-in-time，歷史用量帳不受新價目影響（整合測試驗證）
- [x] 既有 YAML + CLI 載入路徑保留（與 UI 寫同一張表，無 schema 變更）

**實作超出原規劃（#17 / #20）：**
- [x] 價目頁放 **Model 區**（`/admin/model/prices`），不增頂層 nav（守 5.1）；觀測不放價目
- [x] 會員與管理員的**模型目錄（列表卡片 + 詳情）** 顯示現價（每 1M）；分配詳情也顯示
- [x] 模型詳情顯示會員與該 model 的關係：已領取→連結憑證、開放自助→領取鈕、鎖定→提示

**明確排除：**
- ❌ 從供應商自動同步價目（YAGNI；人工/CLI + UI）
- ❌ 多幣別 / 匯率（沿用 USD per 1K tokens）

**階段 7 後續 UX polish（#22–#25）：** admin 模型詳情「基本資訊」可編輯（#22）、目錄詳情上下文長度標籤正名（#23）、分配管理與成員詳情預設隱藏已撤回 +「含已撤回」toggle（#24/#25）。

## 階段 8：部署強化 / 首位管理員 bootstrap

完成（2026-05-27；後端 364 / 前端 74 全綠；PR #26）。前置：階段 1（K8s 部署）、階段 5（ProviderCredential 啟動驗證模式）。
問題：全新部署的 DB 沒有任何 admin member，後台 UI 又只吃 session、從不送 bootstrap token → 部署完沒人進得了後台；且 `ADMIN_BOOTSTRAP_TOKEN` 預設值 `local-dev-admin-only` 是公開已知的萬能後門，未覆蓋即重大風險。
交付：首位 admin 自動佈建 + 不安全預設 token 啟動防呆 + 部署文件。

**成功標準：**
- [x] `ai_api.cli.create_admin`：idempotent 佈建首位 admin（OIDC 預建首次登入綁定／本地密碼邀請），複用 `MemberService.create` + `set_is_admin`；provider 衝突拒絕覆寫；不洩漏 token
- [x] 啟動防呆：`COOKIE_SECURE=true`（production 訊號）下 token 為空或預設值即拒絕啟動（比照 Fernet key fail-fast）；dev 維持零設定
- [x] Helm `bootstrap-admin-job.yaml`：pre-install/pre-upgrade hook（weight 1，排在 migrate 之後），僅在 `bootstrapAdmin.enabled` 且 email 非空時渲染
- [x] `docs/deployment.md`（README 連結）：必填機密、首位 admin、防呆、全員失聯救援；bootstrap token 定位為 break-glass
- [x] 無 schema 變更；既有授權兩路徑與「不可降級最後一位 admin」保護不變

**明確排除：**
- ❌ 多個首位 admin / 批次 admin 佈建（YAGNI）
- ❌ 新增 `APP_ENV` 環境變數（重用 `COOKIE_SECURE` 作 production 訊號）

## 階段 9：成員自助用量總覽

完成（2026-05-28；後端 375 / 前端 80 全綠；PR #30）。前置：階段 3a（用量聚合後端）、階段 7（價目 → 估算花費）。
依據：原則「可追蹤性」的使用端透明化——資源端（admin）與使用端（成員）兩面都該看得到自己的帳。
交付：成員在自己的儀表板看到個人整體用量總覽，嚴格只看自己的資料。

**成功標準：**
- [x] 成員可在儀表板看到跨自己所有分配的彙總：總 token（prompt / completion / total）、估算花費、呼叫次數
- [x] 可按 model／按分配拆分；可選時間區間（本月／近 7 天／近 30 天）
- [x] 花費沿用 point-in-time 價目（`CallRecord.cost_usd` 逐筆加總，與 admin 同口徑）；含未定價呼叫時 `has_unpriced` 標示低估
- [x] 配額視角：分配卡片顯示本月已用／配額 + 進度條（含 3c 池動態配額）；無限額顯示無上限
- [x] **嚴格資料隔離**：`GET /me/usage` 以 `current_member` 限定，無參數能看他人（測試證明 A 取不到 B）
- [x] 複用既有 `aggregate_usage`（加可選 `member_id`，三分支皆已 join `Allocation`），admin 路徑零退化

**實作要點：**
- `aggregate_usage(member_id=...)`：base_filter 加 `Allocation.member_id`，`group_by="member"+member_id` 回單列＝摘要
- `GET /me/usage`：summary（含 `has_unpriced` 由獨立 count 偵測 `cost_usd` NULL/0 且 token>0）+ 可選 `group_by=model|allocation` breakdown；`group_by=member` 回 422
- 前端 `<UsageSummary>`（degrade quietly on error，不破壞儀表板）+ 分配卡片配額進度條

**明確排除：**
- ❌ 跨成員比較／排行（admin 才有意義）
- ❌ 匯出 CSV／JSON、預算告警／超額通知、即時 streaming 用量（YAGNI / 沿用批次聚合）
