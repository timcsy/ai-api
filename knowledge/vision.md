# 願景

## 問題陳述

組織內目前沒有統一的 AI API 存取方式。想用 AI 的人各自申請、各自付費、
各自管理 API key，無法盤點用量、無法管控成本、也無法把資源安全地分享
給其他團隊或讓「不會寫程式的同事」也享受到 AI。

## 核心想法

自製 OpenAI 相容的組織內 AI API gateway，作為**單一分流入口**：

- **多 provider**：Azure OpenAI、OpenAI cloud、Anthropic、Gemini 等
  各家統一以 OpenAI 相容介面對成員開放；後續可加 self-hosted（Ollama / vLLM 等）
- **Provider credential 由 admin 在 UI 管理**：API key 加密落 DB，不再
  只靠 env / K8s Secret；可新增、rotate、停用、稽核
- **動態 catalog 可見性**：成員只看得到 admin 已加 key 且授權給自己的 model
  （兩道過濾：credential gate + access policy）
- **存取規則以 Tag 為主**：admin 為 member 打 tag（組織 / 角色 / 試用群 ...），
  每個 model 設定允許 / 禁止的 tag；改規則 = 改 tag，不必逐一指定
- 開發者透過分配到的憑證直接呼叫 API
- **主流 agent 工具開箱即用**：以 OpenAI Responses API（業界正在收斂的事實
  入口標準）對外開放，讓 OpenAI Codex 等 agent CLI 只要把 base URL 指向本平台、
  填入分配到的憑證即可使用——成員不必各自申請 OpenAI 帳號，用量／成本仍統一
  歸戶到平台。背後仍走多 provider 抽象（OpenAI/Azure 原生高保真，其他家自動橋接）
- 不會寫程式的成員透過外部的「行政輔助服務」間接享受 AI——這些服務以
  管理員授予的高額度憑證呼叫本平台
- 認證以彈性為本：Google Workspace SSO 最方便，但管理員也可以用白名單、
  自動註冊條件、來源限制等方式管控誰能進來
- 所有分配、用量、撤回，在同一個管理介面看得到
- 成員除了逐張憑證的明細，也能看到自己的**整體用量總覽**（跨所有分配的
  token、估算花費、趨勢、各 model 佔比），自己掌握自己的消耗，不必等 admin 報數
- 平台額外提供「**使用情境目錄**」，讓不熟悉 LLM API 的人能依需求
  （文生圖、語音轉文字、文件摘要……）找到該用哪個 API、怎麼開始

## 現狀

**2026-05-28：階段 10（使用體驗打磨）完成——含階段 9 用量總覽、階段 019 暫停/恢復。**
後端 385 tests + 前端 96 tests 全綠；upstream 用 `litellm` library form 支援
4 家 provider（Azure / OpenAI / Anthropic / Gemini）；admin UI 經階段 5.1 從
11 個入口整併為 6 個（journey-oriented）；階段 5.2 起新成員首次註冊可依 admin
規則自動貼 tag；階段 6 起被允許的成員可對 admin 開放的 model 自助領取憑證；
階段 7 起 admin 在 Model 區管理價目（point-in-time），會員/管理員的模型目錄與
分配詳情皆顯示現價；階段 8 起首位管理員可經 CLI / helm Job 自動佈建，bootstrap
token 退為 break-glass，正式環境帶預設/空 token 即拒絕啟動；階段 9 起成員在
儀表板看到自己的整體用量總覽（token / 估算花費 / 次數 + model 拆分 + 區間 +
分配配額），嚴格只看自己；admin 另可**暫停/恢復**一把憑證（可逆、保留 token，非配額=0；
階段 019 / PR #34）；階段 10 把成員儀表板打磨到「好懂」（卡片顯示模型名稱+現價、可自助領取
卡片可點進詳情、新成員三步引導、呼叫端點單一來源、admin 配額改站內對話框）。ProviderCredential
Fernet 加密落 DB，K8s Secret 提供金鑰，pod 啟動時即驗證。3b.7 Playwright E2E 仍未開（暫緩）。

下一步：**階段 11（Responses API / Agent 工具相容）**、3b.7（Playwright E2E）。

## 架構

- **底層**：自製 FastAPI gateway；上游接入採 `litellm`（library only，
  不啟用其 Proxy server form）作為多 provider 抽象層——library form 的
  CVE 集中度遠低於 Proxy form，且涵蓋 100+ provider 不必逐家自寫 adapter
- **Provider credential 儲存**：DB（Fernet 加密 at rest），加密金鑰由 K8s
  Secret 提供；建立時一次性顯示明文（同 allocation token 模式），事後僅
  顯示 fingerprint
- **路由**：`model_catalog.provider` 指明每個 model 走哪家；呼叫時依 model
  查 catalog → 取對應 `ProviderCredential` → 經 litellm 發送
- **對外 API 介面**：OpenAI 相容端點共用同一條前置 pipeline（憑證 / 分配 /
  狀態 / 配額 / model binding / 存取政策 / 計費記錄）——
  - `/v1/chat/completions`（既有，非串流）
  - `/v1/responses`（agent 工具如 Codex 需要；**支援 SSE streaming、tool calls、
    server-side 對話狀態**）。路由**統一經 litellm `aresponses`**：
    - **OpenAI / Azure**：litellm 直呼原生 responses，加密 reasoning 跨輪 replay
      等專屬語意高保真
    - **Anthropic / Gemini 等**：litellm 自動橋接（含 streaming）；OpenAI 專屬語意
      為協定物理限制而等效降級，基本對話／工具呼叫完整可用
  - **對話狀態**：支援 `store=true` 與 `previous_response_id`——gateway 端持久化
    response 供跨輪鏈接（含 TTL／清理），服務不自帶 context 的 client；Codex 走
    `store=false` 自帶 context 則不經此路徑
- **部署**：以 Kubernetes 為部署目標；資源以宣告式（Helm chart 或 Kustomize）
  管理。本機開發走輕量路線（直接執行 uvicorn + Vite），不要求本機跑 K8s。
- **相依套件追蹤**：以 Renovate / Dependabot 自動監看 `litellm`、`openai`
  等關鍵上游，安全性修補不滯後；任何更新若行為異常，可透過容器映像 tag
  在分鐘內回滾。
- **首批供應商**（階段 5）：Azure OpenAI / OpenAI cloud / Anthropic / Gemini；
  後續 self-hosted（Ollama / vLLM 等）
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

詳細設計文件放在 `knowledge/design/`。

## 路線圖

> 已完成階段只列標題、完成標記與「交付」一句；**細部成功標準 / 核心原則 /
> 明確排除已封存於 [`knowledge/history/completed-phases-detail.md`](history/completed-phases-detail.md)**。
> 唯一未完成項為 **3b.7 Playwright E2E**（見階段 3b）。

### 階段 1：分流核心可運作 ✅
- [x] 完成（2026-05-21；本機 + k3s-tew 叢集全 SC 達標）— 自製 gateway 可代理 Azure OpenAI、可發行可撤回的憑證。

### 階段 2：身份驗證與成員管理 ✅
- [x] 完成（2026-05-22）— 彈性身份驗證（Google SSO + Local password）上線；admin API 可分配憑證給成員（UI 留階段 3）。

### 階段 2.5：安全加固 (Hardening) ✅
- [x] 完成（2026-05-22）— provider allowlist、K8s NetworkPolicy、CI Trivy、per-allocation quota + 異常警報、distroless、per-IP 登入鎖。

### 階段 2.6：供應鏈 / Scanner 加固 ✅
- [x] 完成（2026-05-22）— workflow SHA pinning、排程重掃自動開 issue、SBOM、lockfile fail-fast。

### 階段 3a：用量觀測與費用計算（後端）✅
- [x] 完成（2026-05-22）— 多維度用量切分、月度配額、point-in-time 計費、CSV/JSON 匯出。

### 階段 3b：管理員 Web UI ⏳（3b.0–3b.6 ✅；3b.7 待開）
- [x] 3b.0 Stack + 基礎建設（React 19 + Vite + shadcn/ui + Helm Ingress 分流）
- [x] 3b.1 Member view（dashboard / allocation detail / catalog）
- [x] 3b.2–3b.6 Admin suite（members / allocations / usage / quota-pool / rebalance-log；`Member.is_admin` 雙軌認證）
- [ ] **3b.7 Playwright E2E + final polish** — 唯一未完成子階段

### 階段 3c：自適應配額池（馬太效應 + 能量守恆）✅
- [x] 完成（2026-05-22）— 每月自動再分配 quota（用量高拿更多、總量守恆 `Σq=T`），含保底、`quota_locked`、服務型豁免、`RebalanceLog`。

### 階段 4：模型目錄 + 多面向 Filter ✅
- [x] 完成（2026-05-23）— 以「模型」為第一公民的目錄；modality / capability / cost_tier / recommended_for 多 facet filter + faceted counts；CLI 載入 idempotent 不刪未列模型。

### 階段 5：多 Provider + Credential 管理 + Tag-based 存取規則 ✅
- [x] 完成（2026-05-25；PR #12）— 4 家 provider；admin UI 管理 provider key + 存取規則；catalog 可見性 = credential gate ∩ access policy；tag 為主批次授權。

### 階段 5.1：管理員 UX 整併 ✅
- [x] 完成（2026-05-25；PR #13）— sub-nav 11 → 6 條（journey-oriented），舊連結 redirect 相容，抽出 `VisibilityDiagnose`。

### 階段 5.2：規則自動標籤 ✅
- [x] 完成（2026-05-26；PR #14）— admin 定有序規則，新成員首次註冊 first-match-wins 自動貼 tag（4 種 matcher，regex 防 ReDoS）。

### 階段 6：自助領取憑證 ✅
- [x] 完成（2026-05-26；PR #15）— admin 逐 model 開放，被允許的成員在儀表板一鍵領取；資格 = 可見性 ∩ 開放旗標；撤回後鎖定需 admin 解鎖。

### 階段 7：價目表管理 UI ✅
- [x] 完成（2026-05-27；PR #16/#17/#20）— admin 在 Model 區檢視 / 新增價目版本（append-only point-in-time）；模型目錄 + 分配詳情顯示現價，缺價目標「未定價」。後續 polish 見 #22–#25。

### 階段 8：部署強化 / 首位管理員 bootstrap ✅
- [x] 完成（2026-05-27；PR #26）— `create_admin` CLI（idempotent，helm hook Job 佈建首位 admin）+ 預設/空 token 在 production 啟動防呆 + `docs/deployment.md`；bootstrap token 退為 break-glass。

### 階段 9：成員自助用量總覽 ✅
- [x] 完成（2026-05-28；後端 375 / 前端 80 全綠；PR #30）— `aggregate_usage` 加 `member_id`（admin 路徑零退化）+ `GET /me/usage`（summary + model/allocation 拆分 + 區間 + `has_unpriced`，嚴格 `current_member` 隔離）；儀表板 `<UsageSummary>` + 分配卡片「本月已用/配額」。依據原則「可追蹤性」的使用端透明化。

### 階段 10：使用體驗打磨（成員端為主）✅
- [x] 完成（2026-05-28；PR #30/#34/#37/#38）— 分配卡片顯示 display_name + 現價 + 本月已用/配額；可自助領取卡片可點進詳情；新成員三步上手引導；呼叫端點單一來源 `apiBaseUrl()`；admin 配額改 shadcn Dialog；token 文案涵蓋自助；admin 可暫停/恢復憑證（階段 019）。dev `BASE_URL` 修正。細節見 `history/completed-phases-detail.md`。

### 階段 11：Responses API / Agent 工具（Codex）相容 ⏳（後端完成，待真機驗證）

**動機**：延伸「單一入口」到主流 agent 開發工具。OpenAI Codex 等 CLI 預設講
Responses API（`wire_api = "responses"`），且全程依賴 SSE streaming。支援後，
組織開發者可把 Codex 的 base URL 指向本平台、填入分配憑證即用，用量與成本
照常統一歸戶——不必各自申請 OpenAI 帳號。**第一版即交付完整能力，不留半成品。**

**成功標準**：
- Codex CLI 指向 `https://<平台>/v1` + 平台憑證後，能完成含工具呼叫的多輪
  agent 任務（含 reasoning model 的加密 reasoning 跨輪 replay）；該次用量
  **精確**歸戶並計費（reasoning / cached token 分項可見）。
- 所有已上架 provider（Azure / OpenAI / Anthropic / Gemini）皆可經 `/v1/responses`
  呼叫（OpenAI-family 全保真，其他家 litellm 橋接，進階語意等效降級）。
- 用 `store=true` 的第三方 client 能以 `previous_response_id` 跨輪鏈接。

**核心設計**（plan R1 精煉後實作）：
- **統一 litellm 路由**：所有 provider 走 `litellm.aresponses()`——OpenAI/Azure 原生
  高保真（等同 pass-through）、其他家自動橋接（含 streaming）。實測 `aresponses` 已涵蓋
  完整 Responses 介面（`include`/`reasoning`/`store`/`previous_response_id`），故不需
  另寫 raw pass-through（YAGNI）；保留為 fallback 若真機發現失真
- 與 `/chat/completions` **共用** `proxy/preflight.py` 前置 pipeline，auth／配額／計費不複製

**Checklist**：

*基礎 / 路由*
- [x] 抽出共用 pre-flight pipeline（bearer / allocation / 狀態 / 配額 / model binding / access），`/chat/completions` 一併改用
- [x] `POST /v1/responses` 端點：請求驗證（`input` / `instructions` / `tools` / `reasoning` / `include` …）+ 套用共用 pipeline
- [x] OpenAI/Azure 高保真（經 litellm 原生 responses；保留 encrypted reasoning / tool calls 等透傳）
- [x] 其他 provider 經 `upstream.aresponses()` litellm 橋接（`stream=True`）
- [x] catalog `capabilities: ["responses"]` 路由 gate——標記哪些 model 開放 responses

*Streaming*
- [x] **SSE streaming 串流轉發**（FastAPI `StreamingResponse`）：完整 SSE 事件序列（`response.output_text.delta` / `function_call_arguments.*` / `output_item.done` / `response.completed` …）
- [x] 串流時 tee `response.completed` 事件取 usage；串流結束 / client 斷線兩路徑都 `record_call`
- [x] nginx / ingress **SSE 不緩衝**驗證（`proxy_buffering off`；實測過往 Codex+proxy 常踩 SSE 502/timeout）

*精確計費（需 migration）*
- [x] `CallRecord` 加 `reasoning_tokens`、`cached_tokens` 欄位（Alembic migration）
- [x] 價目表加 cached input 折扣價；`calculate_cost` 納入 reasoning（含於 output）與 cached（折扣）
- [x] usage 對應：`input_tokens→prompt`、`output_tokens→completion`、`output_tokens_details.reasoning_tokens`、`input_tokens_details.cached_tokens` 分項落帳

*Server-side 對話狀態*
- [x] `store=true` 持久化：新表存 response payload（`response_id` / `allocation_id` / payload / `created_at` / `expires_at`），含 TTL 與清理
- [x] `previous_response_id` 跨輪鏈接 + 嚴格歸屬檢查（只能鏈接自己分配的 response）

*驗證*
- [ ] Codex **真機驗證**（`config.toml`：`base_url` + `wire_api=responses` + `env_key` 帶平台憑證；多輪 + 工具 + reasoning）
- [x] 多 provider responses 驗證（Azure pass-through、Anthropic/Gemini 橋接）
- [x] 測試：契約 + 計費正確性（reasoning/cached 分項）+ SSE mock 上游 + 斷線處理 + store/previous_response_id 鏈接與歸屬隔離

**明確排除**：
- 非 OpenAI provider 模擬 OpenAI 專屬語意（加密 reasoning replay）的**完全對等**
  ——屬協定物理限制，等效降級可接受（基本對話／工具呼叫仍完整）

> **未完成項**：階段 11（Responses API / Agent 工具相容，規劃中）、3b.7 Playwright E2E（獨立 test-infra，暫緩）。
