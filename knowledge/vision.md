# 願景

## 問題陳述

組織內目前沒有統一的 AI API 存取方式。想用 AI 的人各自申請、各自付費、
各自管理 API key，無法盤點用量、無法管控成本、也無法把資源安全地分享
給其他團隊或讓「不會寫程式的同事」也享受到 AI。

## 核心想法

以 **LiteLLM** 為核心，建立組織內 AI API 的**單一分流入口**：

- 開發者透過分配到的憑證直接呼叫 API
- 不會寫程式的成員透過外部的「行政輔助服務」間接享受 AI——這些服務以
  管理員授予的高額度憑證呼叫本平台
- 認證以彈性為本：Google Workspace SSO 最方便，但管理員也可以用白名單、
  自動註冊條件、來源限制等方式管控誰能進來
- 所有分配、用量、撤回，在同一個管理介面看得到
- 平台額外提供「**使用情境目錄**」，讓不熟悉 LLM API 的人能依需求
  （文生圖、語音轉文字、文件摘要……）找到該用哪個 API、怎麼開始

## 現狀

全新專案，尚未開始實作。技術選型上已選定 LiteLLM 為底層分流引擎、
Azure OpenAI 為首選 AI 供應商；其他細節待設計。

## 架構

- **底層**：LiteLLM（OSS）負責多供應商抽象、配額、速率限制、計費追蹤
- **部署**：以 Kubernetes 為部署目標；資源以宣告式（Helm chart 或 Kustomize）
  管理。本機開發走輕量路線（docker-compose 或直接執行 LiteLLM），不要求
  本機跑 K8s。
- **LiteLLM 自動更新**：LiteLLM 鏡像版本以自動化方式定期更新（例：Renovate
  /Dependabot 監看 + GitOps 套用），確保安全性修補不滯後。更新流程必須有
  「快速回滾」機制——任何一次更新若失敗或行為異常，可在分鐘內回到上一版。
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

> **交付**：LiteLLM 跑起來、可代理 Azure OpenAI、可發行可撤回的憑證
> **前置條件**：無

**成功標準：**
- [x] LiteLLM 本機可運作（docker-compose 或直接執行）
- [x] K8s 部署以宣告式定義（Helm/Kustomize）並可在開發叢集驗證
- [x] LiteLLM 鏡像版本以自動化方式追蹤上游，且有回滾路徑
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
      供應商即使 LiteLLM 能 route 也拒絕（FR-001~003 + 4 contract tests 通過）
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

- [ ] 完成

> **交付**：把 Phase 2.5 引入的 Trivy 與 image build 流程從「能用」拉到
> 「能信」— 消除 mutable action / mutable scanner version、加上排程重掃、
> SBOM 與第二掃描器交叉驗證。
> **前置條件**：階段 2.5
> **建議排程**：可與 3b 並行（CI 工作，不阻擋 UI 開發）

**成功標準（核心兩件）：**
- [ ] `aquasecurity/trivy-action@<commit-sha>` 取代 `@master`；Trivy CLI 版本
      也 pin（呼應 experience.md「mutable tag」教訓）
- [ ] 新增 `scheduled-scan.yml`（每週一）：對 `ghcr.io/timcsy/ai-api:main`
      重跑 Trivy，發現新 CVE 自動開 issue 通知

**成功標準（次要）：**
- [ ] `scan-type: fs` 步驟掃 lockfile（在 build 前先抓出可疑依賴）
- [ ] SBOM 產出（CycloneDX 格式）並附加到 image release artifacts
- [ ] 季度跑一次 OSV-Scanner 或 Grype 作為第二意見，紀錄與 Trivy 差異

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

#### 階段 3b — 管理員 Web UI ⏳
- [ ] 完成

> **交付**：消費 3a API 的 SPA；視覺化用量、配額管理、價目查看
> **前置條件**：3a

### 階段 4：使用情境目錄

- [ ] 完成

> **交付**：成員可依需求情境查到該用哪個 API
> **前置條件**：階段 1（其他階段可並行）

**成功標準：**
- [ ] 至少涵蓋 5 種常見情境（文生圖、STT、TTS、摘要、翻譯）
- [ ] 每種情境有推薦 API、最簡使用範例、預估成本級距
- [ ] 不熟悉 LLM API 的成員看完目錄能自行開始試用
