# 願景

## 問題陳述

組織內目前沒有統一的 AI API 存取方式。想用 AI 的人各自申請、各自付費、
各自管理 API key，無法盤點用量、無法管控成本、也無法把資源安全地分享
給其他團隊或讓「不會寫程式的同事」也享受到 AI。

## 核心想法

自製 OpenAI 相容的組織內 AI API gateway，作為**單一分流入口**：

- 開發者透過分配到的憑證直接呼叫 API
- 不會寫程式的成員透過外部的「行政輔助服務」間接享受 AI——這些服務以
  管理員授予的高額度憑證呼叫本平台
- 認證以彈性為本：Google Workspace SSO 最方便，但管理員也可以用白名單、
  自動註冊條件、來源限制等方式管控誰能進來
- 所有分配、用量、撤回，在同一個管理介面看得到
- 平台額外提供「**使用情境目錄**」，讓不熟悉 LLM API 的人能依需求
  （文生圖、語音轉文字、文件摘要……）找到該用哪個 API、怎麼開始

## 現狀

**2026-05-24：階段 3b.0 + 3b.1 + 3b.2~3b.6（合併）完成；只剩 3b.7 E2E。**
後端 210 tests + 前端 50 tests 全綠；Member.is_admin 雙軌認證上線（c-β
additive，274 既有測試零回歸）；2 個 image 經 Trivy + SBOM gate。
詳細狀態見下方〈路線圖〉每個階段標記。

## 架構

- **底層**：自製 FastAPI gateway + 官方 `openai` SDK（Azure mode）；未來
  新增 provider 採用各家官方 SDK 接入（避免單一 wrapper 套件的 CVE 集中風險）
- **部署**：以 Kubernetes 為部署目標；資源以宣告式（Helm chart 或 Kustomize）
  管理。本機開發走輕量路線（直接執行 uvicorn + Vite），不要求本機跑 K8s。
- **相依套件追蹤**：以 Renovate / Dependabot 自動監看 `openai` SDK 等關鍵
  上游，安全性修補不滯後；任何更新若行為異常，可透過容器映像 tag 在分鐘內回滾。
- **首選供應商**：Azure OpenAI（其他供應商日後再加）
- **認證**：彈性身份驗證，預設提供 Google Workspace SSO（最低摩擦），
  同時支援：
  - 管理員手動加入 email（白名單）
  - 自動註冊條件（例：email 網域、特定身份屬性），符合條件即可註冊
  - 來源安全性限制（IP/網段、裝置／瀏覽器條件等）

  認證機制應抽象化，未來可新增 OIDC/SAML 等供應商而不需重寫核心邏輯。
- **管理員介面**：流量／用量觀測、憑證分配、撤回、配額調整
- **使用情境目錄**：列舉常見任務（文生圖、STT、TTS、摘要、翻譯……）
  並推薦對應 API
- **不在本專案範圍**：行政輔助服務（聊天介面、文件助理等）由其他專案
  獨立開發，作為本平台的「高額度使用者」；**生產等級 K8s 叢集本身**——
  本專案交付 K8s manifests / Helm chart，叢集營運（節點、網路、儲存）
  由組織既有 IT 流程負責。

詳細設計文件將放在 `knowledge/design/`。

## 路線圖

### 階段 1：分流核心可運作

- [x] 完成（2026-05-21：本機 + k3s-tew 叢集全部 SC 達標）

> **交付**：自製 gateway 跑起來、可代理 Azure OpenAI、可發行可撤回的憑證
> **前置條件**：無

**成功標準：**
- [x] 自製 FastAPI gateway 本機可運作（uvicorn）
- [x] K8s 部署以宣告式定義（Helm/Kustomize）並可在開發叢集驗證
- [x] 相依套件版本以自動化方式追蹤上游，且有回滾路徑
- [x] Azure OpenAI 串接成功，可代理至少一個模型
- [x] 可手動建立一筆「分配」並取得獨立憑證
- [x] 該憑證的呼叫可追溯到分配 ID
- [x] 撤回後該憑證立即失效

### 階段 2：身份驗證與成員管理

- [x] 完成（2026-05-22；UI 留階段 3，本階段為後端 + admin API + 必要 HTML）

> **交付**：彈性身份驗證上線；管理員可分配憑證給成員
> **前置條件**：階段 1

**成功標準：**
- [x] 認證機制抽象化（可擴展介面），首發實作 Google Workspace SSO + Local password
- [x] 管理員可手動加入 email 至白名單
- [x] 管理員可設定自動註冊條件（例：email 網域）
- [x] 可設定登入來源限制（IP/網段等基本控管）
- [x] 管理員可由 admin API 建立、查看、撤回成員的分配（UI 留階段 3）
- [x] 一般成員登入後可看到自己的憑證與用量

### 階段 2.5：安全加固 (Hardening)

- [x] 完成（2026-05-22；deploy artifacts 已交付，叢集端 SC-002 待人工驗證）

> **交付**：把 Phase 1 + 2 的已知攻擊面收緊到「可放心對組織內部開放」的水準，
> 不引入新功能
> **前置條件**：階段 2

**成功標準（核心三件）：**
- [x] **應用層 provider allowlist**：`Settings.allowed_providers`；未列出的
      供應商即使配置存在也拒絕（FR-001~003 + 4 contract tests 通過）
- [x] **K8s NetworkPolicy（粗粒度）**：Helm template 已交付，deny-all egress
      + allow {DNS, Postgres podSelector, 443/TCP}，封 169.254.0.0/16
      （5 個 helm-template 結構測試通過；叢集生效需 CNI 支援）
- [x] CI 整合 **Trivy**：`image.yml` workflow 加 trivy-action@0.24.0 +
      `.trivyignore`，HIGH/CRITICAL 即擋
- [x] **per-allocation quota + 異常用量警報**：anomaly_detector service +
      CronJob template；3 個 integration test 涵蓋 baseline-spike / cold-start
      under / over absolute（實測 1101 calls 觸發 quarantine）

**成功標準（次要）：**
- [x] Pod `securityContext` 強化：`readOnlyRootFilesystem` + ALL caps drop
      + `allowPrivilegeEscalation: false` + tmp/cache emptyDir
- [x] 失敗登入額外加 **per-IP** rate limit（同 IP 10 失敗 → 鎖 15 min；2 contract tests）
- [x] 切換 base image 為 **distroless**（`gcr.io/distroless/python3-debian12:nonroot`）

**明確排除（留更後階段）：**
- ❌ FQDN-aware egress (Cilium / Envoy sidecar) — 文件記錄為候選升級
- ❌ cosign image 簽章 + admission controller（需建立簽章基建）
- ❌ external-secrets + Vault/KMS 接通（需挑選 KMS 供應商）

### 階段 2.6：供應鏈 / Scanner 加固 (Supply Chain Hardening)

- [x] 完成（2026-05-22；140 tests 全綠，含 6 新 workflow-pinning tests）

> **交付**：把 Phase 2.5 引入的 Trivy 與 image build 流程從「能用」拉到
> 「能信」— 消除 mutable action / mutable scanner version、加上排程重掃、
> SBOM 與第二掃描器交叉驗證。
> **前置條件**：階段 2.5

**成功標準（核心兩件）：**
- [x] **所有 workflow `uses:` ref pin commit SHA**（包含 image.yml、ci.yml、
      scheduled-scan.yml；test_workflow_pinning.py 驗證）；Trivy CLI 版本
      `v0.70.0` pin
- [x] **`scheduled-scan.yml`**：每週一 06:00 UTC + workflow_dispatch；拉最新
      successful image build 重掃；HIGH/CRITICAL 自動以 CVE id 去重開 GitHub issue

**成功標準（次要）：**
- [x] `scan-type: fs` step 掃 lockfile（在 docker build 前 fail-fast）
- [x] SBOM (CycloneDX) artifact 上傳，retention 90 天
- [ ] 季度跑 OSV-Scanner 或 Grype 作第二意見（人工流程，docs/supply-chain.md 紀錄）

**明確排除（留後階段或不做）：**
- ❌ 自架 trivy-server + 私有 vuln DB mirror（YAGNI，小團隊不需要）
- ❌ cosign image 簽章 + admission control（仍延後；範圍同 2.5 排除項）

### 階段 3：管理員介面、用量觀測與費用計算

> 階段拆為 **3a（後端，本次完成）** + **3b（管理員 UI，待開）**。

#### 階段 3a — 後端 ✅
- [x] 完成（2026-05-22；134 tests 全綠）

**3a 成功標準：**
- [x] 可按分配對象切分查看用量（每人／每分配／每模型；團隊維度延後）
- [x] 可看每個分配的歷史請求數、token 數（含時間序列）
- [x] 可設定／調整單筆分配的配額上限（月度，UTC 月初錨點）
- [x] 可標記哪些分配是「高額度服務用」（`is_service_allocation` boolean）
- [x] 維護一份可更新的價目資料來源（YAML 人工，CLI 載入 — Azure 主要模型）
- [x] 可由分配 ID 查到該分配累積費用（按時間區間）；費用可按 Member ／ 模型切分
- [x] 價目更新時，歷史紀錄使用「呼叫當時的價目」計算（point-in-time，FR-013）
- [x] CSV / JSON 匯出
- [x] CORS 預備（為 3b SPA 鋪路；cors_origins 非空時 SameSite=None+Secure）

#### 階段 3b — 管理員 Web UI ⏳（拆 3b.0~3b.7）

> 階段拆為小子階段，每個 1 PR：
> - **3b.0 Stack + 基礎建設** ✅ — React 19 + Vite + shadcn/ui + Helm Ingress 分流 + 5 unit tests + login/home/404
> - **3b.1 Member view** ✅ — dashboard + allocation detail (cursor pagination) + catalog browse + catalog detail + copy curl；backend 199 tests + frontend 43 tests
> - **3b.2~3b.6 Admin suite** ✅（合併單一 PR）— 5 admin 視圖 (members CRUD / allocations CRUD / usage CSV+JSON / quota-pool monitor + manual trigger / rebalance-log)；Member.is_admin 雙軌認證 (c-β additive)；backend 210 tests + frontend 50 tests
> - 3b.7 Playwright E2E + final polish ⏳

> **3b.0 交付**：可登入的 SPA 骨架；2 個 image + Ingress 路徑路由；backend 195 tests + frontend 21 tests 全綠
> **前置條件**：3a / 3c / 4 後端皆已完成

#### 階段 3c — 自適應配額池（馬太效應 + 能量守恆）✅
- [x] 完成（2026-05-22；167 tests 全綠，含 11 unit + 8 integration + 7 contract + 1 proxy 即時性）

> **交付**：每月自動再分配 quota，用量高的拿更多、低的被壓縮；總量守恆。
> **前置條件**：3a（3b 可並行，但 UI 顯示池資訊建議在 3b 完成後追加）

**核心原則：**
- **能量守恆**：`Σq_i = T`（T 為池總量），rebalance 前後不變，除非 admin 動 T
- **馬太效應**：上月用量越多 → 下月 quota 越大（按比例 + 保底）

**成功標準：**
- [x] `Settings.pool_total_tokens_per_month` 與 `pool_floor_per_allocation`
      可設；資源池僅涵蓋**非服務型 active allocations**
- [x] 每月 UTC 月初由 CronJob 自動 rebalance；演算法：
      `q_i_new = floor + (T - floor*N) * (usage_i / Σ usage)`
- [x] 守恆檢核：rebalance 結束時 `Σq = T` assertion 通過（compute + apply 雙層）
- [x] **保底**：每個 allocation 即使上月零用量也至少拿到 `floor`
- [x] **`quota_locked` 旗標**：admin 手動設的 quota 不被 rebalance 覆寫；
      被鎖住的 quota 從 T 中扣除，剩餘給池內動態分配
- [x] **服務型分配豁免**：`is_service_allocation=true` 不進池、quota 由
      admin 獨立管理
- [x] 新增 `RebalanceLog` 表記錄每次再分配前後的 quota（含 algorithm_version 欄位以便未來升 v2）
- [x] Edge: 新分配加入只拿 floor 直到下次月初；`floor * N > T` 即
      `pool_exhausted_by_reserved`，rollback 並寫 audit

**明確排除：**
- ❌ 即時池容量視覺化（留 3b UI）
- ❌ 多池（按 model / Team 切池）— 首版單一全域池
- ❌ 跨月借貸 / 過期 token roll-over

### 階段 4：模型目錄 + 多面向 Filter

- [x] 完成（2026-05-23；194 tests 全綠：10 unit + 12 contract + 5 integration on top of 167 prior）

> **交付**：類 Azure Foundry 的模型目錄；以「模型」為第一公民、提供
> modality / capability / cost_tier / recommended_for 等多 facet filter；
> faceted counts API 讓 UI 直接渲染 sidebar。
> **前置條件**：階段 1（與 3b 並行不衝突）

**成功標準：**
- [x] `model_catalog` 表 + Alembic migration 0006
- [x] 首版 YAML 含 ≥ 8 個 Azure OpenAI 主力模型（實際 9：gpt-4o, gpt-4o-mini,
      o1-mini, o3-mini, text-embedding-3-small/large, dall-e-3, whisper-1, tts-1）
- [x] `GET /catalog/models` 多面向 filter，list 欄位 AND 語意
      （`?capability=vision&capability=function-calling&cost_tier=low` → 唯一命中 gpt-4o-mini）
- [x] `GET /catalog/filters` 回 faceted counts，schema 穩定（空 DB 與
      有資料 DB 回相同 dimension key 集合）
- [x] `GET /catalog/models/{slug}` 含 `example_request`（curl + JSON body）
- [x] CLI `python -m ai_api.cli.load_models <yaml>` upsert by slug；
      idempotent；YAML 未列出的 model **不刪除**（防事故 wipe，FR-005）
- [x] 棄用隔離：`status=deprecated` 不出現在預設列表，但 detail 仍可查到含
      `deprecation_note`
- [x] 任何 active member 可看（新 `require_active_member` 依賴；
      無認證 401、disabled 403）

**明確排除（留 3b 或後階段）：**
- ❌ UI / 視覺呈現（留 3b SPA）
- ❌ 整合到「建立 allocation」流程作為 model picker（留 3b）
- ❌ 從 Azure 自動同步 model 清單（YAGNI）
- ❌ 即時定價（cost_tier 而非絕對價；docs/model-catalog.md 記載未來整合 SOP）
