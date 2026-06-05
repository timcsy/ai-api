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

## 階段 019：憑證暫停 / 恢復（屬階段 10 的新能力）

完成（2026-05-28；後端 383 / 前端 83 全綠；PR #34）。
動機：admin 想臨時關閉一把（無限額）憑證、之後原樣恢復，而非配額=0；現有 active / revoked（終局換 token）/ quarantined（僅自動）湊不出可逆、保留 token 的暫停。

**成功標準：**
- [x] `AllocationStatus` 加 `paused`、`CallOutcome` 加 `rejected_paused`、`AuditEventType` 加 `allocation_paused`/`allocation_resumed`（皆 `native_enum=False` → 無 migration）
- [x] `AllocationService.pause()`/`resume()`：只切 status、**保留 token、不建 reclaim lock**（與 revoke 終局的關鍵差異）；狀態機 pause 僅 active、resume 僅 paused，其餘 `InvalidAllocationState` → 409
- [x] proxy 對 paused 回 `allocation_paused`(403)、計 `rejected_paused`，可與 revoked/quarantined/quota 區分（沿用既有「先 lookup 後檢查」執法點，即時生效）
- [x] `POST /admin/allocations/{id}/pause`｜`/resume`（比照 unquarantine）
- [x] admin UI：分配列 + 成員詳情暫停/恢復鈕，文案與「撤回（終局）」區分

**明確排除：**
- ❌ 排程自動暫停 / 恢復（首版手動）
- ❌ 成員自助暫停自己的憑證（首版只 admin）

## 階段 10：使用體驗打磨（成員端為主）

完成（2026-05-28；後端 385 / 前端 96 全綠；PR #30/#34/#37/#38）。前置：階段 6（自助領取）、階段 7（價目顯示）。
源於 2026-05-27 真實使用者實測盤點出的摩擦：資訊要逐張點開、技術 slug 不好讀、新手無引導、端點顯示、admin 原生彈窗、token 文案；另含一個能力缺口（憑證暫停/恢復，獨立為階段 019）。

**成功標準：**
- [x] 「我的分配」卡片顯示 display_name（slug 為輔）+ 現價（每 1M，未定價標示）+ 本月已用/配額進度條（配額部分 PR #30）
- [x] `/me/allocations` additive 加 `display_name`（orphan→null）
- [x] 可自助領取卡片可點進 `/catalog/{slug}`；領取鈕 stopPropagation 不誤觸導頁
- [x] 無分配成員見三步上手引導（① 領取 ② 複製 ③ 貼進 Authorization）
- [x] 呼叫端點單一來源 `lib/api-base.ts` 的 `apiBaseUrl()`，dashboard 與 ApiUsageExample 共用；dev `BASE_URL` :8000 → :47822 修正
- [x] admin 調整配額改 shadcn Dialog（預填、驗證、空白=無限額）取代原生 `prompt()`
- [x] token 提示文案涵蓋自助領取（`<strong>` 強調，非 markdown）
- [x] 憑證暫停/恢復（見階段 019）

**明確排除：**
- ❌ 全面視覺改版 / 換 design system
- ❌ 3b.7 Playwright E2E（獨立 test-infra，暫緩）

## 階段 11：Responses API / Agent 工具（Codex）相容

完成（2026-05-29；Codex CLI 真機驗證）。前置：階段 5（多 provider）、階段 7（價目）、階段 9（用量總覽）。

**動機：** 延伸「單一入口」到主流 agent 開發工具。OpenAI Codex 等 CLI 預設講 Responses API
（`wire_api = "responses"`），全程依賴 SSE streaming。支援後組織開發者可把 Codex 的 base URL
指向本平台、填入分配憑證即用，用量／成本仍統一歸戶——不必各自申請 OpenAI 帳號。
**第一版即交付完整能力，不留半成品。**

**成功標準：**
- [x] Codex CLI 指向 `https://<平台>/v1` + 平台憑證後，能完成含工具呼叫的多輪 agent 任務
  （含 reasoning model 的加密 reasoning 跨輪 replay）；該次用量精確歸戶並計費（reasoning /
  cached token 分項可見）
- [x] 所有已上架 provider（Azure / OpenAI / Anthropic / Gemini）皆可經 `/v1/responses` 呼叫
  （OpenAI-family 全保真，其他家 litellm 橋接，進階語意等效降級）
- [x] 用 `store=true` 的第三方 client 能以 `previous_response_id` 跨輪鏈接

**核心設計（plan R1 精煉後實作）：**
- **統一 litellm 路由**：所有 provider 走 `litellm.aresponses()`——OpenAI/Azure 原生高保真
  （等同 pass-through）、其他家自動橋接（含 streaming）。實測 `aresponses` 已涵蓋完整 Responses
  介面（`include`/`reasoning`/`store`/`previous_response_id`），故不需另寫 raw pass-through（YAGNI）；
  保留為 fallback 若真機發現失真
- 與 `/chat/completions` **共用** `proxy/preflight.py` 前置 pipeline，auth／配額／計費不複製

**Checklist 完整版：**
- [x] 抽出共用 pre-flight pipeline；`/chat/completions` 一併改用
- [x] `POST /v1/responses` 端點：請求驗證 + 套用共用 pipeline
- [x] OpenAI/Azure 高保真（litellm 原生 responses，保留 encrypted reasoning / tool calls 透傳）
- [x] 其他 provider 經 `upstream.aresponses()` litellm 橋接（`stream=True`）
- [x] catalog `capabilities: ["responses"]` 路由 gate
- [x] SSE streaming 串流轉發（FastAPI `StreamingResponse`）：完整事件序列
- [x] 串流時 tee `response.completed` 取 usage；正常結束 / client 斷線都記帳
- [x] nginx / ingress SSE 不緩衝驗證（`proxy_buffering off`）
- [x] `CallRecord` 加 `reasoning_tokens`、`cached_tokens`（Alembic migration）
- [x] 價目表加 cached input 折扣價；`calculate_cost` 納入 reasoning（含於 output）與 cached（折扣）
- [x] usage 對應：`input_tokens→prompt`、`output_tokens→completion`、details.reasoning_tokens、
  details.cached_tokens 分項落帳
- [x] `store=true` 持久化（新表 + TTL + 清理 cronjob）
- [x] `previous_response_id` 跨輪鏈接 + 嚴格歸屬檢查
- [x] Gateway 真機驗證（curl 對真實 Azure）
- [x] Codex CLI 真機煙霧測試（2026-05-29 使用者端 Windows codex-tui 跑通，含 reasoning/cached）
- [x] 多 provider responses 驗證
- [x] 測試：契約 + 計費正確性 + SSE mock 上游 + 斷線處理 + store/previous_response_id

**額外 UX 延伸：**
- 用量總覽顯示 reasoning/cached 分項
- 「如何呼叫」加 responses/Codex 範例 + **config.toml 下載 + 各 OS 白話步驟**
- 一般使用者**自助暫停/恢復**自己的憑證（沿用 Phase 019 service，端點層加 ownership check）
- 分配/管理員表格命名統一（友善名 + 標籤化 model 代號/憑證）

**明確排除：**
- ❌ 非 OpenAI provider 模擬 OpenAI 專屬語意（加密 reasoning replay）的完全對等
  ——屬協定物理限制，等效降級可接受（基本對話／工具呼叫仍完整）

## 階段 12：存取設計重組 + 維運可視性

完成（2026-05-30）。前置：階段 2（auth）、階段 5（tag-based access）、階段 11（Codex / agent 工具上線）。

**動機：** Phase 11 上線後幾天浮現的三類非預期狀況：
1. Codex 流量被 anomaly detector 自動隔離（agent CLI 本就 bursty，不是異常）
2. 既有設計把白名單同時當「bootstrap」與「日常管理機制」，admin 進來後白名單與成員管理重疊、
   admin-created member 在 OIDC gate 仍被白名單擋下
3. quarantined 分配既無首頁可見性也無解除 UI；既有後端 API（`/admin/access/rules` 等）對應的
   前端頁面缺位，使用者得求助工程師才能管理
4. 順勢專案公開化（MIT、neutralize 命名、Docker image 公開、GitHub Star 連結）

**成功標準：**
- [x] anomaly detector 在 `is_service_allocation=True` 時跳過（`services/anomaly.py`）；
  新增整合測試 `test_us4_anomaly_detector.py::test_service_allocation_is_exempt_from_quarantine`
- [x] `auth/policy.py::is_email_allowed` 重寫為兩模式：bootstrap（無 admin）= whitelist OR rule；
  admin mode = rule OR active member by email（whitelist bypassed）
- [x] `/admin/access` 頁通用化：admin 自己設定自動註冊規則與來源限制（IP/網段），不再 hard-code
  任何網域；側 nav 新增「存取」入口
- [x] admin 首頁加 quarantined/paused 數量卡（紅 / 琥珀邊框），點擊跳 `/admin/observability/allocations`
- [x] 分配列加紅色「🚨 已隔離」/ 琥珀色「⏸ 已暫停」徽章；新增「解除隔離」dropdown 操作呼叫
  `POST /admin/allocations/{id}/unquarantine`
- [x] 既有「切換服務型」操作即 anti-anomaly 永久豁免入口（不再需要新 UI）
- [x] MIT License + README 重寫（badges、Mermaid 架構圖）；scrub 內部命名（CCSH 中性化）；
  GHCR Docker image 公開；app-shell header 加 GitHub icon + Star tooltip

**明確排除：**
- ❌ 黑名單設計（封鎖某 email/IP）——當下無需求，保留純白名單心智模型
- ❌ 異常偵測規則可設定化（首版 service flag 即足夠豁免；門檻值仍寫死）

## 階段 13：管理員突發狀況通知（Email）

完成（2026-06-03；spec 022-admin-email-notifications）。前置：階段 2（auth/audit）、
階段 12（quarantine 可視性）。以 speckit 全流程（spec → plan → tasks → 78 任務 TDD 實作）。
設計細節（元件圖、決策表、觸發來源對照）見 [`../design/admin-notifications.md`](../design/admin-notifications.md)。

**動機：** Phase 12 把 quarantine/paused 做進 admin 首頁卡片，但 admin 只有「開著 UI 才看得到」。
分配被自動隔離、upstream 短時間大量失敗、provider 憑證失效等事件**離線時無感**，等使用者回報才知道。
台灣學校環境 Slack/Discord/Google Chat 都不友善、LINE Bot 設定過重，**Email 是「最容易安裝」的選擇**
（admin 用既有學校 email；server 端只需 4 個 SMTP value）。

**核心設計（research 13 條決策）：**
- **立即寄 + DB 去重 gate**（不引入排程器 / retry / Jinja2）：滿足 30s SLO 與「每事件型別每 5 分鐘 ≤1 封」
- **SMTP 密碼沿用 `PROVIDER_KEY_ENC_KEY` Fernet**，不新增加密基礎建設
- **audit.record() hook + `asyncio.create_task` fire-and-forget**：寄信失敗不影響 audit 寫入（FR-025）
- **`aiosmtplib`（async）+ `aiosmtpd`（測試 server）** 新依賴
- **`Notifier` ABC + `EmailNotifier`** 第一版單一 channel；LINE Bot / Web Push 為平行 adapter

**交付（依 user story）：**
- **US1**：`/admin/notifications` 設定頁（SMTP 表單 + 收件人 + status badge）+ test-send（一次性收件人，
  不打擾正式清單，FR-007 選 A）；4 endpoints（GET/PUT/DELETE config、POST test-send）
- **US2**：`allocation_quarantined` 觸發 email（含原因具體數字、UTC+8 時間、admin 連結）；per-recipient
  失敗不互相阻斷；未設定/停用/憑證無效皆靜默 skip
- **US3**：另 3 種事件——`upstream_burst_detector`（cronjob 每分鐘，5 分鐘窗 ≥10 次 upstream_error）、
  proxy 401/403 → `provider_credential_auth_failed`（原預埋的第 4 種 `allocation_daily_cap_exceeded`
  已於 2026-06-03 隨 daily cap 撤案移除）
- **US4**：`NotificationDedupBucket` 5 分鐘窗去重；primary record 連結 bucket；per-event-type 獨立
- **US5**：`/admin/notifications/history` keyset 分頁 + event_type/outcome filter + bucket_event_count；
  前端歷史區含合併標示與逐收件人失敗原因

**資料表（migration 0014）：** `notification_config`（singleton CHECK id=1）、
`notification_dedup_bucket`、`notification_record`。新 helm cronjob：`upstream-burst`（每分鐘）、
`notification-cleanup`（每日，30 天 GC）。新 `AuditEventType` ×3。

**測試：** 39 個（10 contract + 25 integration + 11 unit 中與本功能相關者；含 SMTP 真握手 via aiosmtpd、
dedup 窗、hook fire、failure 不破 audit）。全套件 409 passed（54 error 為既有 PG/Docker 整合，無關）。
mypy/ruff 全綠。

**明確排除（第一版）：** Web Push / PWA、LINE Bot、Slack/Discord/Google Chat webhook、自架 SMTP server。

**已知限制：** multi-replica 真同時事件可能各寄一封（上限 = replica 數）——SQLite/cross-connection
row lock 無法序列化；research R3 接受此限（真同時跨 replica 機率近 0）。

**待真機驗證：** 用真實 Gmail App Password 在 live cluster 跑 quickstart 情境 1 + 3（尚未部署）。

## 階段 15：Tag-based 群組成本 rollup

完成（2026-06-03；spec 023-tag-group-rollup）。前置：階段 5（MemberTag）、階段 3a/9（aggregate_usage）。
以 speckit 全流程（spec → plan → tasks → 37 任務 TDD）。設計細節見
[`../design/tag-rollup.md`](../design/tag-rollup.md)。

**動機：** 學校／團隊推廣 AI 時「按班級／群組看用量」比「按個別成員」更接近 admin 真實心智
（預算按班級給、報告按專案寫）。原本 `/admin/usage` 只能切 member/allocation/model，admin 得自己
把同一班成員加總出 Excel。外部回饋也一致指向此為剛需。

**核心設計：** 在 `aggregate_usage` 加 `group_by="tag"` 分支，JOIN
`call_records → allocations → member_tags`、`GROUP BY member_tags.tag`。重疊**自然產生**：
成員掛 N tag → join 出 N 列 → 其每筆 call 計入 N 個 tag，這正是「tag 總額 = 該 tag 成員各自相加」
的定義。**無新表、無 migration、無新依賴。**

**交付（依 user story）：**
- **US1**：`GET /admin/usage?group_by=tag` 回各 tag 聚合（token/cost/call + 區間）；既有
  `/usage.json`、`/usage.csv` 自動支援；service_only filter 有效
- **US2**：`GET /admin/usage/tag/{tag}/members` 下鑽（重用 member 分支 + tag 成員過濾）；前端
  `/admin/usage` 加「依 Tag」視圖——可點列展開成員明細、常駐重疊提示「各 tag 加總可能重複、不等於平台總額」
- **US3**：CSV/JSON 以 tag 維度匯出（零改動，回傳同 `UsageItem` 形狀）
- 隔離：admin-only；成員無法透過任何端點取得跨成員 tag 聚合

**關鍵設計抉擇：**
- tag **不做時間版本化**——採查詢當下歸屬（班級穩定、YAGNI）
- 重疊**不去重**——刻意語意，UI 標示而非試圖去重
- 下鑽**重用 member 分支** + tag 過濾，不重寫聚合邏輯

**測試：** 11 個（6 contract + 5 integration，含「tag 聚合 = 成員各自相加」「多 tag 重疊計入每個 tag」
「service_only」「時間區間」「下鑽」「匯出」「admin-only 隔離」）；既有 251 usage+contract 測試零退化。
ruff/mypy/前端 lint+typecheck+build 全綠。

**明確排除：** nested tags / tag hierarchy、per-tag quota（quota 仍以 allocation 為單位）、
首頁 Top 5 tags 卡（依賴階段 14 圖表基建，延後）。

**已知限制：** 各 tag 加總 > 平台總額（重疊成員多算，by design、UI 標示）；tag 採查詢當下歸屬
（學期中轉班會讓歷史用量跟著新 tag 走）。

## 階段 14：Admin 視覺化強化

**完成：** 2026-06-03（spec 024-admin-visualization）

**交付：** 導入全平台第一個 charting 依賴 recharts（gzip 增量 ~100KB，< 150KB 預算），
共用 `<Chart>` wrapper（`components/ui/chart.tsx`，封裝 ResponsiveContainer + 固定高度 +
統一空狀態/載入 skeleton）+ 單一色盤統一全平台。

- **首頁三圖 + Top 5 tags 卡**（`components/admin-home-charts.tsx`）：daily spend bar（token/花費
  可切）、Spend by Model donut（top 5 + 其他，click slice 跳 model 詳情）、Top 5 allocations bar
  （click 跳分配維運頁）、Top 5 tags by spend 卡（卡片非圖表）。圖表區一律放 quarantine/paused
  警示 + 系統資訊**之下**，首頁最多 3 張圖（FR-008）。
- **用量頁 provider donut + heatmap**（`components/admin-usage-charts.tsx`）：provider 占比 donut；
  24×7 用量熱度圖用 **CSS grid（非 recharts）**，UTC+8 分桶。
- **統一時段選擇器**（`components/time-range-select.tsx` + `lib/time-range.ts`）：本週／本月／本季／
  自訂；首頁以 state、用量頁以 URL searchParams 持有；切換一起 refetch，載入時顯 skeleton 不空白閃。
- **隔離原因顯眼化**（`components/quarantine-reason-badge.tsx`）：分配列徽章 click → popover 就地顯示
  觸發數據（過去 1 小時 N calls、baseline X/hr），lazy fetch；不必點進稽核紀錄。

**後端：** `services/usage.py` 加 `group_by="provider"` 分支（JOIN model_catalog）、`HeatCell` +
`usage_heatmap`（dialect-aware、UTC+8）、`usage_timeseries` 的 `allocation_id` 改 `str | None`
（None = 平台級加總）；`api/usage.py` 加 `/usage/timeseries`、`/usage/heatmap`、
`/allocations/{id}/quarantine-reason`。**無新表、無 migration、僅 recharts 一個新依賴。**

**測試：** `tests/contract/test_usage_viz.py`（平台時序 + provider + 隔離原因 + admin-only）、
`tests/integration/test_usage_viz_agg.py`（heatmap UTC+8 分桶，Postgres）、
`frontend/src/__tests__/home-charts.test.tsx`（≤3 圖、警示在圖之前、空狀態）、
`time-range-select.test.tsx`（preset 換算）。全套 487 後端 + 109 前端測試綠、ruff/mypy 零警告。

**設計細節：** [`design/admin-visualization.md`](../design/admin-visualization.md)。

**明確排除（第二版再評估）：** Allocation 詳情 30 天 line + 配額燃燒投影、Member 跨 allocation
donut、月底支出投影虛線、PNG export、>3 張首頁圖、3D/radar/treemap 花俏圖型、多 charting lib。

## 階段 16：行動裝置（手機）體驗強化（RWD）

**完成：** 2026-06-03（spec 025-mobile-rwd）

**動機：** 後台桌機優先設計，手機上「擠」。真實回饋指出最痛的是**導覽列與資訊密度**——header 塞不下、
寬表格左右滑、長字串撐破卡片，且**中文被壓窄會字字斷行變直條**。經三路平行 RWD 稽核（殼層／admin／成員端）
歸納根因與重複反模式。

**交付（零新 npm 依賴、零後端/DB 變更、桌機零回歸）：**
- **根因①** `tailwind.config.ts` 的 `container.padding` 加手機斷點（`{ DEFAULT: "1rem", sm: "2rem" }`）——
  360px 手機有效寬從 ~296 增加，放大全站擠壓的根因解除。
- **US1 手機導覽**（`app-shell.tsx` + `hooks/use-mobile.ts` + `ui/sheet.tsx`）：以 `useIsMobile()`（matchMedia）
  切換——`< md` 顯示漢堡 + `Sheet` 抽屜（含全部主導覽 + 管理員子導覽 + email + 登出），`≥ md` 維持 inline 橫排。
  `Sheet` 基於既有 `@radix-ui/react-dialog`。子導覽補 `shrink-0 whitespace-nowrap`。
- **US2 內容不溢出**：全站機械式套既有 Tailwind 工具——多欄 `grid-cols-1 sm:grid-cols-N`、工具列 `flex-wrap`、
  長字串 `truncate`（配 `min-w-0`）/`break-all`、CJK `whitespace-nowrap`。涵蓋約 19 個檔。
- **US3 寬表格卡片化**：`index.css` 新增單一 `.responsive-table` 機制（`< md` 每列變卡片、`data-label` 顯示欄名），
  以 **child combinator** 限定只作用頂層表（巢狀表如 tag 下鑽不受影響）。套用至 usage/allocations/members/
  providers/prices/tag-rules/access（兩表）/member-detail 內層表；allocation-detail 五欄呼叫紀錄改 `overflow-x-auto`。

**測試分工（憲章 TDD 之 jsdom 可測邊界）：** 有 DOM 行為（導覽 Sheet 開合並列出全部目的地、表格每格帶
`data-label`）以 vitest 先 Red 後 Green（`mobile-nav.test.tsx`、`responsive-tables.test.tsx`）；純視覺溢出/折行
jsdom 無版面引擎，以 `quickstart.md` 的 360px 手動清單驗收。113 前端測試綠（既有 109 零回歸 + 4 新）。

**設計細節：** [`design/frontend.md`](../design/frontend.md) 的「RWD 規範」一節。

**經驗：** CJK 無空格，flex 子項被壓窄會逐字換行成直條；凡橫排含中文需 `whitespace-nowrap` + `min-w-0` 或父層
`flex-wrap`。寬表格手機策略用「單一 CSS 機制 + data-label」比「每表寫兩套版面」低 drift（呼應「同一概念兩份必 drift」）。

**明確排除：** 不為手機重做獨立 UI、不導入額外 UI lib、不追求像素級精緻；provider 動作欄 DropdownMenu 重構列為
可選增益（卡片式堆疊已讓 3 按鈕全寬可達，滿足 SC-007）。

## 階段 17：成員自助用量視覺化（成員端圖表）

**完成：** 2026-06-04（spec 026-member-usage-charts）

**動機：** 成員 dashboard 已有純數字用量總覽，但管理員端已有視覺化圖表、成員端沒有。源於使用者回饋
「想讓不是管理員的人也看得到一些圖表」。對應原則 6 可達性（成員自助掌握消耗）+ vision「成員自己掌握
自己的消耗，不必等 admin 報數」。

**鐵律（資料隔離，原則 1 憑證隔離 / 2 可追蹤性）：** 成員**只能看自己的**——範圍 100% 取自登入 session
（`current_member`），端點**無任何參數**可指定他人，回傳**絕不含**跨成員聚合。隔離以 Postgres 整合測試
固化（`test_my_timeseries_excludes_other_member`：成員 A 打 `/me/usage/timeseries` 不含 B 的呼叫）。

**交付（零新依賴、無新表、無 migration、桌機 + admin 既有圖零回歸）：**
- **每日趨勢 bar**（成員跨所有自己憑證加總，token/花費可切）+ **各 model 花費 donut**。
- 唯一新後端：`services/usage.py` 的 `usage_timeseries` 加 `member_id` 過濾參數（設定時 JOIN Allocation），
  + `api/me.py` 新增 `GET /me/usage/timeseries`（`current_member`、bucket=day、範圍只取自 session）。
- **donut 零新後端**——複用既有 `GET /me/usage?group_by=model`（階段 018 已 member-scoped）。
- 前端 `components/member-usage-charts.tsx`（複用 `<Chart>`/`CHART_COLORS`/`<TimeRangeSelect>`，query key
  在 `["me","viz",...]` 命名空間避免與 admin 撞），接進 `routes/dashboard.tsx` 用量區 + 時段選擇器。
- RWD 沿用階段 16：base `grid-cols-1 md:grid-cols-2`、`<Chart>` 的 `w-full min-w-0`。

**測試（TDD）：** contract `test_me_usage.py`（自己當日和、401、from≥to 400）先 Red；integration
`test_me_usage_isolation.py`（Postgres 隔離）先 Red → `usage_timeseries +member_id` + 新端點 → Green。
前端 `member-usage-charts.test.tsx`（資料映射 + 空狀態）。491 後端 + 115 前端測試綠（零回歸）。

**經驗：** 沿用「把 admin 能力下放成 self-service = 同一聚合邏輯（actor-agnostic 的 `member_id` 參數）+
端點層用 session 嚴格擁有者把關」——服務層加一個過濾參數即達成，不另寫 member 版函式（避免 drift）。
donut 直接複用既有 member-scoped 端點，再次印證「新需求先找既有 member-scoped 能力」。

---

## 階段 18：憑證模型重構（每分配多 per-device 憑證）

**完成：** 2026-06-04（spec 028-per-device-credentials）

**動機：** 單一共用 token 的多裝置與輪替體驗很差——rotate 連坐全部裝置、忘記複製就卡死。業界做法
（GitHub PAT、AWS IAM 雙鑰、gh/gcloud/Claude Code 的 OAuth device flow）皆「每台/每用途一把獨立憑證」。
源於使用者「唯一性的不是 token，而是分配是唯一的（可容許同一 model 不同方式的分配），一分配可有多 token」。
對應原則 1（憑證隔離——「撤銷單一憑證不影響其他」於此名副其實）+ 原則 2 可追蹤性。

**核心 schema 變更（1:1 → 1:N，migration `0015`）：** `Credential` 主鍵由 `allocation_id`（強制 1:1）改為
獨立 ULID `id`；`allocation_id` 改一般 FK + 索引（非唯一）；新增 `name`（裝置名）/`last_used_at`/`revoked_at`；
`token_fingerprint` 維持唯一（token→credential 仍 1 對 1 命中）。`Allocation.credential`（scalar）→ `credentials`（list）。

**零回歸保證（最高優先固化）：** migration `0015` 以「建新表 + 複製 + swap」（SQLite/Postgres 皆同），
既有每列原樣搬 `token_fingerprint`/`token_prefix`/`created_at` + 補新 ULID `id` + `name="預設"`——**既有 token 不失效**。
Postgres 整合測試 `test_credential_migration.py`：seed 舊式單憑證 → `alembic upgrade head` → 該舊 token 仍
`lookup_by_token` 解析到同分配、且有一把「預設」憑證。額度/用量/歸戶仍綁 `allocation_id` → 計費零回歸。

**交付（零新依賴）：**
- service `allocations.py`：`add_credential`/`list_credentials`/`get_credential`/`revoke_credential`（軟撤回 `revoked_at`，
  idempotent）；`lookup_by_token` 加 `revoked_at IS NULL` + 節流更新 `last_used_at`（>5 分鐘才寫，tz-naive 安全）；
  `create`/`rotate_token` 適配 list（建第一把「預設」/輪替第一把 active）；顯示點（`me.py`/`allocations.py`）取
  「代表性憑證」prefix（首把 active）。
- member 端點 `/me/allocations/{id}/credentials`（GET 不含明文 / POST 回明文一次 / DELETE 軟撤回；CSRF + 擁有者隔離 403）。
- admin 端點 `/admin/allocations/{id}/credentials`（GET / DELETE 留稽核 `credential_revoked`；未認證 401）。
- 前端 `components/device-credentials-card.tsx`（可複用：member 新增/撤回 + 一次性遮罩複製 dialog；admin 唯讀清單 + 撤回）
  接進 `routes/allocation-detail.tsx`（member, allowAdd）與 `routes/admin/allocations.tsx`（dropdown「查看裝置憑證」→ dialog）。
  沿用階段 16 `.responsive-table` + `data-label` RWD。

**為何不設「軟上限」：** 額度/歸戶/異常偵測都在分配層，多把 token 共用同一配額 → 多裝置不繞過任何限制，
故無需對 token 數量設限（與原則 1 一致：限制的單位是分配，不是 token 數）。

**測試（TDD）：** 後端 `test_me_credentials.py`（5：add show-once+可呼叫、多把皆歸同分配、list 無明文、撤一把不連坐、
owner-isolation）+ `test_admin_credentials.py`（3：admin list/revoke+稽核、未認證 401）+ 整合 2（migration 零回歸、
多憑證 lookup/revoke）先 Red → 實作 → Green。**501 後端 + 117 前端測試綠，ruff/mypy 零警告。**

**收尾增補（上線同批，PR #54/#55）：**
- **per-device 就地 rotate**（PR #54）：每把裝置憑證可一鍵「重新產生」——`service.rotate_credential`（保留
  `name`/`created_at`、換 fingerprint/prefix、`last_used_at` 歸零、舊 token 立即失效）+ `POST /me/allocations/{id}/credentials/{cid}/rotate`。
  使用者回饋「合併之後仍要能為裝置重新產生憑證，不用刪了再加」。
- **憑證 UI 合併**（PR #54）：移除與裝置清單重疊的舊「你的憑證」卡（同一個代表性 prefix + 舊 rotate-token），
  裝置清單成為唯一憑證介面；暫停/恢復（分配層、與逐把撤回不同概念）移到頁首狀態徽章旁。對應原則 5/6（單一介面、少混淆）。
- **每個分配的用量圖表**（PR #55）：分配詳情頁加 `AllocationUsageCharts`（每日時序折線 + 週x時用量熱度圖 +
  時段選擇器）——後端 `usage_heatmap` 加 `allocation_id` 過濾、新增 `/me/allocations/{id}/usage/{timeseries,heatmap}`
  （擁有者隔離 403；`usage_timeseries` 本就支援 allocation scope）；熱度圖抽成共用 `<UsageHeatmap>`（admin 用量頁
  改用）；新增 `fmtCompact`（K/M/B）修掉被裁切的大數字軸。對應原則 6（成員逐分配自助掌握消耗，延伸階段 17 整體總覽）。
- 測試累計 **504 後端 + 121 前端綠**（+rotate contract、+per-allocation usage contract×2、+fmtCompact/charts 前端）。

**部署：** rev 49 · `sha-5274f0d`（2026-06-04），含階段 18 全部三批（核心模型 + UI 合併 + 用量圖表）。

**經驗：** ① 改主鍵在 SQLite 不能 in-place ALTER → migration 用「建新表+複製+swap」一招吃兩種 DB。
② Postgres migration 整合測試要驅動真 alembic（test DB 平時用 `metadata.create_all`），且測試結束要 `DROP SCHEMA
public CASCADE` 還原，否則 alembic 建出的具名約束會讓後續 `metadata.drop_all` 踩雷。③ class 內若有名為 `list` 的
method，其後 method 的回傳註解 `list[X]` 會在 class scope 解析成那個 method → 用 `Sequence[X]`。④ SQLite 的
`DateTime(timezone=True)` 讀回是 naive，跨 now(aware) 相減會炸 → 比較前補 `tzinfo=UTC`。

---

## 階段 19：成員一鍵安裝 Codex + device-flow（後端/前端完成，待真機 + 部署）

**完成（程式）：** 2026-06-05（spec 029-codex-easy-install）。**待辦**：三平台真機驗收（SC-006）+ 部署。

**動機：** 讓非技術成員「複製一行指令 + 在瀏覽器按一次授權」就裝好 Codex、零參數零環境變數、切 model 不脫鉤，
**全程不複製貼上 token**。對應原則 6 可達性 + 原則 1 憑證隔離（每台一把 per-device 憑證、可單獨撤回）。

**device-flow（RFC 8628 改寫）：** 新表 `device_authorizations`（migration `0016`）。三公開 + 三 member 動作：
`POST /device/authorize`（CLI 起手，回 device_code + 人類可讀 `XXXX-XXXX` user_code + verification_uri + expires/interval）；
`POST /device/token`（CLI 輪詢，RFC 8628 風格回 `authorization_pending`/`slow_down`/`expired_token`/`access_denied`，
成功單次交付明文）；`GET /me/device/{user_code}`、`POST .../approve`（body allocation_id，`current_member` + 擁有者把關 →
`AllocationService.add_credential` mint）、`POST .../deny`。以**既有 session 登入**當「已認證」來源——不自建 OAuth server（YAGNI）。

**明文單次交付（hash-only 有界例外）：** mint 仍只存 fingerprint；明文以 **Fernet 加密暫存**於 `device_authorizations.encrypted_token`
（復用既有 `encrypt_str`/`decrypt_str`），輪詢成功時交付一次後**立即清 NULL**。短時效（600s）+ 單次 + 節流（`slow_down`）。

**安裝腳本（不脫鉤，真機已驗的設定）：** 端點 `GET /install/codex.{sh,ps1}` 回純文字、注入平台 `base_url`；腳本抓 Codex
獨立 binary（GitHub Releases，免 Node）→ **merge-style** 寫 `~/.codex/config.toml`（`model_provider="ccsh"` 預設 +
`[model_providers.ccsh]` `wire_api="responses"`/`requires_openai_auth=true`/`supports_websockets=false`）→ 跑 device-flow →
`codex login --with-api-key` 寫 auth.json → 測試呼叫。**不採**唯讀 config / wrapper / alias（切 model 重寫後仍保留 `ccsh`）。

**前端：** `routes/device-authorize.tsx`（`/device` 授權頁，`?code=` 預填、選自己的分配、approve/deny）+
`components/codex-install-card.tsx`（dashboard 依 OS 一行指令 + 一鍵複製）。

**測試（TDD）：** 後端 `test_device_flow.py`（service + 端點 + US4 憑證可見可撤回）、`test_device_owner_isolation.py`、
`test_install_endpoint.py`、整合 `test_device_migration.py`（Postgres 0016 + 零回歸）先 Red → Green；前端 device-authorize +
install-card vitest。**519 後端 + 124 前端綠，ruff/mypy/typecheck/lint/build 全綠。** 確認 `.tmpl` 進 hatchling wheel（部署可達）。

**經驗（補）：** ① device-flow 的明文必須跨「CLI ↔ 瀏覽器」兩 channel 交付 → 用「加密暫存 + 單次 + 即清 + 短時效」把
hash-only 的例外面積壓到最小，勝過明文存 DB 或同步阻塞等待。② mutating member 端點的 `require_csrf`（decorator）在
`current_member`（param dep）**之前**evaluate → 未登入打 approve 得 403（CSRF）而非 401；契約測試對未登入的 mutating
端點要接受 401/403（讀取端點才穩定 401）。③ `.bat`/PowerShell 中英混排易亂碼 → 安裝腳本訊息以英文為主。
