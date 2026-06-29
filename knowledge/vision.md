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
- 認證以彈性為本：Google Workspace SSO 最方便；管理員可用自動註冊規則、
  成員清單、來源限制（IP / 網段）等方式管控誰能進來。**白名單（email
  allowlist）僅在首位 admin 進來之前生效作為 bootstrap，admin 接手後即由
  上述管理機制取代，不再生效**
- 所有分配、用量、撤回，在同一個管理介面看得到
- 成員除了逐張憑證的明細，也能看到自己的**整體用量總覽**（跨所有分配的
  token、估算花費、趨勢、各 model 佔比），自己掌握自己的消耗，不必等 admin 報數
- 平台額外提供「**使用情境目錄**」，讓不熟悉 LLM API 的人能依需求
  （文生圖、語音轉文字、文件摘要……）找到該用哪個 API、怎麼開始
- 平台對**突發狀況**（分配被自動隔離、upstream 短時間大量失敗、provider 憑證
  失效等）主動通知管理員——沿用既有 audit_events 為事件源；通知設定（SMTP
  / 收件人）admin 可在 web UI 自助設定並按「發測試信」即時驗證，**不需另外
  架設外部服務**（借既有 Gmail SMTP 或學校 mail 即可）
- 成本／用量可按**班級／群組／專案** rollup——以既有 tag 為聚合單位（admin 把
  成員打 `class-101` / `project-x` 等 tag，dashboard 自動以 tag 為單位呈現支出
  與配額），admin 不必自行出 Excel 加總

## 現狀

平台已對組織開放使用（k8s 叢集，公開 MIT 倉庫）。詳細階段成果見下方〈路線圖〉與
`history/completed-phases-detail.md`。本檔〈核心想法〉與〈架構〉段反映平台現行設計；
本段只記「跑在哪、目前未完成的是什麼」。

階段 1–34、36、37（第一刀）、38 均已上線（最新 rev 104；階段 35 供應鏈規劃中）。憑證模型一路演進：階段 18（每分配多 per-device 憑證）→ 19（一鍵安裝 Codex + device-flow）→ 20（scoped application credentials，credential↔allocation M:N）→ 21（憑證 UI 術語與層級收斂：統一「應用金鑰」、單一管理處、可改名）→ 22（會員介面分頁化：頂部導覽拆 金鑰/分配/用量 + 精簡儀表板 + 一句解釋）→ 23/24（模型目錄 ↔ LiteLLM 對接 + admin 體驗整合）→ 25（responses 雙來源判定，三軸解耦）→ 26（admin 依種類測模型）→ 27/28（應用分頁 → 應用商店化，Codex 第一個應用）。**階段 19 三平台真機（Windows/macOS/Linux）已驗收完成（2026-06-08）**；驗收暴露並修掉三個 Codex 安裝坑（預設模型 pin、選錯模型可操作錯誤、bare-slug alias 讓 /model 看得到成員模型；rev 60→62）。**階段 25 後另有一輪 UI 用語一致性 polish（rev 71→73）**：中英混雜統一成繁中、後端列舉/狀態值一律過 label 函式（`status-label.ts`/`facetLabel`）中文化、facet 加白話 hover 說明、金鑰清單含已撤回開關（對應原則 6 可達性）。**階段 26–28（rev 74→80）**：依種類測模型、應用分頁/商店化、能力 facet 詞彙正規化、推理模型測試 max_tokens 修正、新增**原則 7 演進性**。**階段 29–31（rev 82→93）**：多端點全開（embedding / OCR / 圖片 / rerank / TTS / STT / moderation / search / image_edit）+ 計費一般化（migration 0019、token/page/query/character/image 單位）+ **資料驅動端點 registry**（`proxy/engine.py`＋`endpoint_spec.py`＋`registry.py`，加端點＝加一筆資料）；成員批次管理 + ORM 顯式安全刪除（階段 30）；「測試模型」從 if/elif 演化成**資料驅動 recipe 表**（`services/model_test.py`，「能不能測 ⟺ 有沒有 recipe」單一真理，rev 90–93），補齊 ocr/stt/image_edit/search 真分支、並修掉實測揭露的**生產 `/v1/ocr` provider 路由 bug**（litellm OCR 不認 `azure/`、需 `azure_ai/`）。realtime 即時字幕（**階段 32**，rev 95，直連供應商 WS、不經 litellm）+ **成本制配額**（**階段 33**，rev 96，每分配每月 USD 花費上限、跨端點統一治理）+ **「如何呼叫」可發現性重設計**（**階段 34**，rev 97，金鑰為入口、應用為總站、model 下拉填 slug）+ **OpenAI 相容 `/v1/models` + Copilot 上卡**（**階段 36**，rev 98→101，模型發現端點 + Copilot 卡真機驗證、一鍵帶出設定）皆已上線。**階段 37 會員 IA 重排凸顯「應用」第一刀（純重排，導覽序 儀表板→應用→目錄→分配→用量→金鑰）已上線（rev 102）**；後續（標籤白話化、apps-first 落地頁）另議。**階段 38 Codex 安裝體驗硬化**（既有登入殘留→`codex logout`+整檔覆寫乾淨設定、動檔前先備份、桌面版關閉提醒、一鍵還原 `/install/codex-restore.*`；rev 103→104，三平台真機驗收完成）已上線。**進行中規劃：階段 35 供應鏈／starlette+FastAPI major bump**（`.trivyignore` 暫掛兩個 starlette CVE，待 FastAPI 1.x 解鎖）。剩餘端點 video / vector_store 按需評估、多半 descope；image_edit/search 真分支待接非 Azure provider 才能實測。

## 架構

- **底層**：自製 FastAPI gateway；上游接入採 `litellm`（library only，
  不啟用其 Proxy server form）作為多 provider 抽象層——library form 的
  CVE 集中度遠低於 Proxy form，且涵蓋 100+ provider 不必逐家自寫 adapter。
  **刻意例外：`/v1/realtime`（階段 32 即時字幕）直連供應商 WebSocket（直接依賴
  `websockets`），不經 litellm**——litellm 的 realtime 是 Proxy form / client 直連、
  音訊繞過 gateway，會失去「歸戶到分配」與「即時撤回」（build-vs-adopt 以**領域第一公民
  是否同軸**判，非功能重疊度；見 experience「功能重疊 ≠ adopt」）。借其 `RealTimeStreaming`
  relay 結構自寫薄轉送，計費/分配核心仍守在我們這邊。
- **Provider credential 儲存**：DB（Fernet 加密 at rest），加密金鑰由 K8s
  Secret 提供；建立時一次性顯示明文（同 allocation token 模式），事後僅
  顯示 fingerprint
- **路由**：`model_catalog.provider` 指明每個 model 走哪家；呼叫時依 model
  查 catalog → 取對應 `ProviderCredential` → 經 litellm 發送
- **對外 API 介面**：OpenAI 相容端點共用同一條前置 pipeline（憑證 / 分配 /
  狀態 / 配額 / model binding / 存取政策 / 計費記錄）——
  - `/v1/chat/completions`（非串流）
  - `/v1/responses`（agent 工具如 Codex 需要；**已上線並真機驗證**，支援 SSE
    streaming、tool calls、reasoning/cached 精確分項計費、server-side 對話狀態）。
    路由**統一經 litellm `aresponses`**：
    - **OpenAI / Azure**：litellm 直呼原生 responses，加密 reasoning 跨輪 replay
      等專屬語意高保真
    - **Anthropic / Gemini 等**：litellm 自動橋接（含 streaming）；OpenAI 專屬語意
      為協定物理限制而等效降級，基本對話／工具呼叫完整可用
  - **對話狀態**：支援 `store=true` 與 `previous_response_id`——gateway 端持久化
    response 供跨輪鏈接（含 TTL／清理），服務不自帶 context 的 client；Codex 走
    `store=false` 自帶 context 則不經此路徑。**對外鼓勵 stateless**（客戶端自己持有並重播
    context，如 Codex `store=false`／Chat Completions）為可攜正道；server-state（`store=true`）
    是**便利選項、有固有取捨**——伺服器端記憶是 **per-分配**的，跨 model／跨分配帶脈絡得靠客戶端
    重播，續接不上時**明確吐錯不靜默降級**（無聲丟脈絡比報錯更糟，見 experience「接不上的續接請求要
    明確拒絕」+ 原則 2 可追蹤性：跨分配不串味）
- **部署**：以 Kubernetes 為部署目標；資源以宣告式（Helm chart 或 Kustomize）
  管理。本機開發走輕量路線（直接執行 uvicorn + Vite），不要求本機跑 K8s。
- **相依套件追蹤**：以 Renovate / Dependabot 自動監看 `litellm`、`openai`
  等關鍵上游，安全性修補不滯後；任何更新若行為異常，可透過容器映像 tag
  在分鐘內回滾。
- **首批供應商**（階段 5）：Azure OpenAI / OpenAI cloud / Anthropic / Gemini；
  後續 self-hosted（Ollama / vLLM 等）
- **認證**：彈性身份驗證，預設提供 Google Workspace SSO（最低摩擦），
  同時支援：
  - 管理員直接管理成員清單（新增／停用）；email 白名單**僅作為 bootstrap fallback**
    （DB 無任何 admin 時生效，admin 進來後不再生效）
  - 自動註冊條件（例：email 網域、特定身份屬性），符合條件即可註冊
  - 來源安全性限制（IP/網段、裝置／瀏覽器條件等）
  - 異常偵測自動隔離可疑分配；service flag 可標示 agent/CLI 等 by-design 爆量者豁免

  認證機制應抽象化，未來可新增 OIDC/SAML 等供應商而不需重寫核心邏輯。
- **管理員介面**：流量／用量觀測、憑證分配、撤回、配額調整、quarantine 解除、
  存取規則設定；首頁顯示關鍵維運狀態（被自動隔離 / 暫停的分配數、系統設定
  上限如 request body）——**可編輯**只開放給業務類設定（access rules、tag、價目、
  配額）；infra 類（body size、timeout 等）一律 read-only 顯示，由 Helm value 管。
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
> 階段 1–34 皆已上線（最新 rev 97）；階段 19 三平台真機驗收已完成（2026-06-08）。

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

### 階段 3b：管理員 Web UI ✅
- [x] 3b.0 Stack + 基礎建設（React 19 + Vite + shadcn/ui + Helm Ingress 分流）
- [x] 3b.1 Member view（dashboard / allocation detail / catalog）
- [x] 3b.2–3b.6 Admin suite（members / allocations / usage / quota-pool / rebalance-log；`Member.is_admin` 雙軌認證）

> **descope：3b.7 Playwright E2E** — 不做（2026-06-03）。E2E 的核心價值是「自動抓未來回歸」，
> 但本專案為 solo 維運、admin 介面已被真實使用反覆驗證，且回歸防線實際上是 contract/unit tests
> （後端）+ lint/typecheck/build（前端）+ 部署後手動煙霧。佐證：notification 上線後暴露的兩個真 bug
> （NetworkPolicy egress、密碼留白）Playwright 在 CI 都抓不到——前者需真 cluster、後者該由 contract
> test 守。維護一套 flaky/慢的 Playwright 套件，CP 值不符 YAGNI。未來若有他人 contribute、不再單一
> 驗證者時再評估。

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

### 階段 11：Responses API / Agent 工具（Codex）相容 ✅
- [x] 完成（2026-05-29；Codex CLI 真機驗證）— `/v1/responses` 全鏈上線（統一 litellm 路由、
  SSE streaming、工具呼叫、reasoning/cached 精確分項計費、`store`/`previous_response_id` 歸屬隔離 + TTL 清理）；
  附用量總覽 reasoning/cached 分項與 Codex `config.toml` 下載 + 各 OS 白話步驟、成員自助暫停/恢復憑證。
  細節見 `history/completed-phases-detail.md`。

### 階段 12：存取設計重組 + 維運可視性 ✅
- [x] 完成（2026-05-30）— **白名單退場為 bootstrap-only**：admin 進來後存取改由「成員清單 +
  自動註冊規則 + 來源限制」管理；新增通用 `/admin/access` 頁讓 admin 自己設定（不再 hard-code 任何網域）。
  **anomaly detector 對 `is_service_allocation=True` 豁免**（agent/CLI 流量是 by-design 爆量，
  不該被自動隔離）。**維運可視性**：admin 首頁卡片顯示 quarantined/paused 數，分配列加紅色「已隔離」/
  琥珀色「已暫停」徽章與「解除隔離」操作；首頁加 read-only「系統資訊」卡顯示 request body 上限
  （Helm `requestBodyLimitMB` 同時注入 nginx `client_max_body_size` 與 backend env，
  「顯示值 = 執法值」single source of truth）。`/v1/responses` 串流捕捉 upstream `response.failed`
  事件並記為 `outcome=upstream_error`，admin log/usage view 直接看得到 upstream 給的失敗原因
  （DeploymentNotFound / content_filter / rate limit 等），不必猜。**專案公開化**：MIT License、
  neutralize 內部命名、Docker image 公開、web header 加 GitHub Star icon。
  細節見 `history/completed-phases-detail.md`。

### 階段 13：管理員突發狀況通知（Email）✅
- [x] 完成（2026-06-03）— admin 在 `/admin/notifications` 自助設定 SMTP（密碼 Fernet
  加密，沿用 `PROVIDER_KEY_ENC_KEY`）+ 收件人清單 + 「發測試信」即時驗證（寄一次性
  收件人，不打擾正式清單）。平台對 3 種重要 audit event（分配自動隔離、upstream
  連續失敗、provider 憑證失效）經 `audit.record()` hook fire-and-forget
  寄信；同事件型別 5 分鐘窗去重；未設定時通知停用、不擋啟動、不影響 audit 寫入。
  通知歷史頁含去重合併標示與逐收件人失敗原因。`Notifier` interface + `EmailNotifier`
  第一版，LINE Bot / Web Push 可後續平行加。spec 022；細節見
  `history/completed-phases-detail.md`。

### 階段 14：Admin 視覺化強化 ✅
- [x] 完成（2026-06-03；spec 024）— 導入全平台**第一個** charting 依賴 recharts（gzip 增量
  ~100KB < 150KB 預算），共用 `<Chart>` wrapper + 單一色盤統一全平台。首頁加 daily spend bar /
  model donut / Top 5 allocations bar（**最多 3 圖**，全部放 quarantine 警示**之下**，FR-008）+
  Top 5 tags 卡（卡片非圖表）；用量頁加 provider donut + 24×7 heatmap（CSS grid，非 recharts）；
  全頁統一時段選擇器（本週／本月／本季／自訂）；分配列徽章 click → popover 就地顯示隔離/暫停
  觸發數據（不必點進稽核紀錄）。新端點：平台級 `/admin/usage/timeseries`、`/admin/usage/heatmap`、
  `group_by=provider`、`/admin/allocations/{id}/quarantine-reason`。**無新表、無 migration、
  僅 recharts 一個新依賴**。細節見 [`design/admin-visualization.md`](design/admin-visualization.md)。

**動機**：競品 mockup 的視覺密度顯著高於現況——首頁就有時序圖、model 占比、
top spenders 等決策圖；對外觀感「像成品」差距明顯。但**圖表多 ≠ 好**：每張圖
必須回答一個會驅動決策的具體問題，否則只是 chart-junk 把真正重要的警示淹掉。

**第一版範圍**（**首頁最多 3 張新圖**，避免視覺超載）：
- 首頁 7–14 天 daily spend/usage 條狀圖（可切 token / cost 雙模式，hover 顯示明細）
  → 答題「最近花錢節奏正常嗎？」
- 首頁 Spend by Model donut（top 5 + Other，click slice 跳該 model 詳情）
  → 答題「錢都燒在哪？」
- 首頁 Top 5 allocations by spend 橫向 bar（display_name + 數字 + click → allocation 詳情）
  → 答題「誰是重度使用者？」
- `/admin/usage` 加 Provider 比例 donut（procurement 決策）
- `/admin/usage` 加 hour-of-day heatmap（24h × 7day；對課堂場景特別有意義）
- 全頁面統一時段選擇器（本週／本月／本季／自訂，shadcn 現成）
- 視覺 polish 一輪：卡片陰影、heading scale、空狀態 illustration
- **暫停／隔離原因顯眼化**：分配列徽章 hover 顯示原因、解除頁顯示具體觸發數據
  （例：「過去 1 小時 1100 calls，baseline 100/hr，超出 11×」），目前要點進稽核
  紀錄才看得到，admin 體感差很多

**第二版可能**（之後再評估，不在第一版範圍）：
- Allocation 詳情頁加 30 天 daily token line + token 分項 stacked bar + 配額燃燒投影
- Member 詳情頁加跨 allocation donut
- 本月累積支出曲線 + 月底投影（趨勢延伸虛線）
- PNG export

**明確排除**：
- ❌ 首頁塞 >3 張圖（quarantine 警示一定要保持顯眼）
- ❌ 為每個指標都配一張圖（數字 + delta 已足夠就不要硬塞）
- ❌ 3D pie / radar / treemap 等花俏圖型（漂亮但難讀）
- ❌ 為了「像成品」犧牲我們的差異化（admin 設定清單、quarantine alert、系統資訊）
- ❌ 導入**多個**圖表 lib——僅選一個（recharts 或其 shadcn wrapper）統一全平台，
  不混用（避免 bundle 膨脹與風格不一）

**設計原則**：
- 每張圖回答一個會驅動決策的問題；無此性質的圖一律砍
- 預設帶「vs 上週／上月」delta 比較
- 點圖元素能 click-through 到詳情頁，不要孤立圖
- hourly 重算為最低更新頻率，避免「美但 stale」

### 階段 15：Tag-based 群組成本 rollup ✅
- [x] 完成（2026-06-03；spec 023）— `aggregate_usage` 加 `group_by="tag"` 維度，JOIN 既有
  `member_tags` 聚合（成員多 tag → 用量計入每個 tag，刻意重疊）；新增 `/admin/usage/tag/{tag}/members`
  下鑽端點；`/admin/usage` 加「依 Tag」視圖（可點列展開成員明細 + 常駐重疊提示）；CSV/JSON 匯出
  自動支援。**無新表、無 migration、無新依賴**。admin-only（成員拿不到跨成員聚合）。
  細節見 [`design/tag-rollup.md`](design/tag-rollup.md) 與 `history/completed-phases-detail.md`。
  （首頁「Top 5 tags by spend」卡片已隨階段 14 圖表基建一起交付。）

### 階段 16：行動裝置（手機）體驗強化（RWD）✅
- [x] 完成（2026-06-03；spec 025）— 讓桌機優先的後台與成員端在手機（最小 360px）也順手，
  桌機／平板零回歸。**零新 npm 依賴、零後端／DB 變更**。三批交付：
  (US1) header 以 `useIsMobile()` 切換——`< md` 收進漢堡 + `Sheet` 抽屜（含全部目的地），桌機維持 inline；
  (US2) 全站 `grid-cols-1 sm:`、工具列 `flex-wrap`、長字串 `truncate`/`break-all`、CJK `whitespace-nowrap`；
  (US3) 寬表格以單一 `.responsive-table` CSS 機制 + 每格 `data-label`——手機每列變卡片、桌機維持完整表格。
  關鍵根因「修一次整站受惠」：`container` padding 加手機斷點。`Sheet` 基於既有 Radix Dialog（非新依賴）。
  113 前端測試綠（既有 109 零回歸 + mobile-nav/responsive-tables 4 新測試）。
  細節見 [`design/frontend.md`](design/frontend.md) 的「RWD 規範」與 `history/completed-phases-detail.md`。

**根因（一輪系統性 RWD 稽核歸納；殼層／admin／成員端三路平行掃）**：
- `container` padding 寫死 2rem、無手機斷點 → 360px 手機有效寬只剩 ~296px，**放大全站每一頁**的擠壓。
- `header`（`app-shell.tsx`）沒有手機版收合：主導覽 + 完整 email + 登出硬擠一橫排、不換行、無漢堡／抽屜。
- 重複反模式：`grid-cols-2/3` 無 responsive 前綴、工具列無 `flex-wrap`、動態長字串無 `truncate`／`break-all`。

**範圍（分三批，由高槓桿到細修）**：
- 第 0 批（必做、改動極小、修一次整站受惠）：`container` padding 加手機斷點；header 主導覽
  手機收進抽屜（shadcn `Sheet`）、email 手機隱藏／截斷；橫向子導覽項補 `shrink-0 whitespace-nowrap`。
- 第 1 批（機械式全站掃、低風險）：`grid-cols-2/3` 一律補 `grid-cols-1 sm:`（資訊區與 dialog 表單列）；
  標題列／工具列補 `flex-wrap`（這些在表格容器外、真的會溢出）；動態長字串補 `truncate`／`break-all`
  （email、slug、指紋、端點／gateway URL）。
- 第 2 批（需先定一個設計取向）：寬表格（用量 8 欄、分配／成員／provider 7 欄）的手機策略——
  「隱藏次要欄（`hidden sm:table-cell`）」或「手機卡片式堆疊」二擇一，定了再統一套用；
  provider 動作欄 3 顆按鈕改 `DropdownMenu`（其他頁已這樣做）。最痛點：`usage.tsx` 裸 `<table>`
  下鑽未包 `overflow-x-auto`、`allocation-detail.tsx` 五欄 grid 呼叫紀錄、成員端 inline `<code>` URL 撐破卡片。

**明確排除**：
- ❌ 不為手機重做一套獨立 UI、不導入額外 UI lib（沿用既有 Tailwind + shadcn 斷點）。
- ❌ 不碰已經做對的：shadcn `<Table>` 內建 overflow、recharts `ResponsiveContainer`、heatmap 的
  `overflow-x-auto`、token `<pre>` 的 `overflow-x-auto`/`break-all`、catalog grid、成本 Badge。
- ❌ 不追求像素級手機精緻度（後台日常仍以桌機為主）；目標是「手機堪用且順」，非行動優先。

**設計原則**：
- 桌機完整、手機精簡：寧可手機收合／隱藏次要資訊，也不硬塞到字字斷行。
- 修根因優先於逐頁補丁（container padding、header 收合一次解決一大片）。
- 既有正確 pattern 不動，避免回歸。

**經驗／風險**：中文無空格，flex 子項被壓到比內容窄時會逐字換行成直條（CJK 特性）；凡橫排含中文者
需 `whitespace-nowrap` + 容器 `min-w-0`，或讓父層 `flex-wrap`，否則就會「橫的變直的」。

### 階段 17：成員自助用量視覺化（成員端圖表）✅
- [x] 完成（2026-06-04；spec 026）— 讓**非管理員成員**在自己 dashboard 看到**自己用量**的兩張圖
  （每日趨勢 bar 含 token/花費切換 + 各 model 花費 donut）+ 時段選擇器，自己掌握消耗、不必等 admin 報數。
  **鐵律：資料隔離**——範圍 100% 取自登入 session、端點無參數可查他人、絕不含跨成員聚合（隔離以 Postgres
  整合測試固化：成員 A 拿不到 B）。**最小新增**：donut 複用既有 `/me/usage?group_by=model`；唯一新後端是
  `usage_timeseries` 加一個 `member_id` 過濾 + `GET /me/usage/timeseries`。前端複用 `<Chart>`/`<TimeRangeSelect>`，
  **零新依賴、無新表、無 migration**。對應原則 6 可達性 + 原則 1/2（只看自己）。細節見
  `history/completed-phases-detail.md`。

### 階段 18：憑證模型重構（每分配多 per-device 憑證）✅（2026-06-04 上線，rev 49 · `sha-5274f0d`）
- [x] 已完成 — 把「唯一性」從 **token** 移到 **分配**：一筆分配可同時掛**多把獨立的 per-device 憑證**
  （每台裝置一把），各自可單獨撤回；額度／歸戶／可追蹤性綁在**分配**層（多把 token 共用同一額度，
  故 token 數不繞過配額與異常偵測，**無需軟上限**）。同一 model 亦可有多個分配（不同用途／方式）。
  **動機**：單一共用 token 的多裝置與輪替體驗很差（rotate 連坐全部、忘記複製卡死）；業界做法
  （GitHub PAT、AWS IAM 雙鑰、gh/gcloud/Claude Code 的 OAuth device flow）皆為「每台/每用途一把獨立憑證」。
  **範圍**：`Credential` 由 `allocation_id` 當主鍵（強制 1:1）改為「獨立 id 主鍵 + allocation_id 一般 FK +
  裝置名 + last_used_at」（1:N，需 migration）；新增「裝置/憑證清單」管理——member 自助新增裝置
  （**顯示一次** + 遮罩複製面板）/ 逐把撤回，admin 可見並撤某成員所有憑證。token 仍 show-once + 只存雜湊。
  呼叫紀錄仍以 `allocation_id` 歸戶 → 計費/可追蹤性不變。對應原則 1（憑證隔離，「撤銷單一憑證不影響其他」
  於此名副其實）+ 原則 2 可追蹤性。**惠及全平台**（任何多裝置/per-device 撤銷皆受益）。
  〔**device-flow（RFC 8628 瀏覽器授權拉 token，免複製貼上）放階段 19**，跟 Codex 安裝腳本一起做。〕
  **實際交付**：`Credential` 1:1→1:N（migration `0015`，既有 token 零回歸——Postgres 整合測試固化）；
  service 層 `add_credential`/`list_credentials`/`revoke_credential`（軟撤回 `revoked_at`）+ `lookup_by_token`
  加 `revoked_at IS NULL` 與節流 `last_used_at`；`/me/allocations/{id}/credentials`（GET/POST/DELETE，CSRF + 擁有者隔離）、
  admin `/admin/allocations/{id}/credentials`（GET/DELETE，留稽核 `credential_revoked`）；前端 `DeviceCredentialsCard`
  （member 新增/撤回 + 一次性遮罩複製、admin 唯讀清單 + 撤回；沿用階段 16 `.responsive-table` RWD）。
  **收尾增補（上線同批）**：① **per-device 就地 rotate**——每把裝置憑證可一鍵「重新產生」（保留裝置名與
  建立時間、舊 token 立即失效），不必「刪了再加」（`POST /me/allocations/{id}/credentials/{cid}/rotate`）；
  ② **憑證 UI 合併**——移除與裝置清單重疊的舊「你的憑證」卡，裝置清單成為唯一憑證介面，暫停/恢復（分配層）
  移到頁首（對應原則 5/6：單一介面、少混淆）；③ **每個分配的用量圖表**——分配詳情頁加「每日時序折線 +
  週x時用量熱度圖」（`/me/allocations/{id}/usage/{timeseries,heatmap}`，擁有者隔離），圖表 Y 軸改 K/M/B
  緊湊顯示（對應原則 6 可達性：成員逐分配自助掌握消耗，延伸階段 17 的整體總覽）。
  詳見 [history/completed-phases-detail.md#階段 18](history/completed-phases-detail.md)。

### 階段 19：成員一鍵安裝 Codex + device-flow（零參數、不脫鉤）✅（rev 52 上線；三平台真機 2026-06-08 驗收，收尾 rev 60→62）
- [x] 後端/前端完成（spec 029）— device-flow（RFC 8628 風格）+ 一行安裝腳本（sh/ps1）+ 授權頁 + dashboard 安裝卡；
  **519 後端 + 124 前端測試綠**。device-flow：`/device/authorize`、`/device/token`（公開輪詢）、`/me/device/{code}`（GET/approve/deny，
  擁有者把關），核可即 mint 一把 per-device 憑證（明文 Fernet 暫存、輪詢單次交付即清）；安裝腳本 merge-style 寫自訂 provider
  `ccsh`（`wire_api=responses`、`requires_openai_auth=true`、`supports_websockets=false`）+ `codex login --with-api-key`，
  不脫鉤、零環境變數。新表 `device_authorizations`（migration `0016`，Postgres 整合測試固化零回歸）。**三平台真機驗收（SC-006）2026-06-08 完成**——
  Windows/macOS/Linux 皆通過；過程修掉三個坑：①安裝後預設 fallback 成 Codex 內建模型 → device-flow 回傳代表模型 + 腳本 pin（rev 60）；
  ②`/model` 選單看不到成員模型（catalog 用 `provider/` 前綴 slug、Codex 用 bare slug）→ proxy bare-slug alias + pin bare slug（rev 62）；
  ③誤選範圍外模型 → 可操作中文錯誤（rev 61）。詳見 experience.md「前置 client 自帶模型目錄時，gateway 命名空間要能被它的 picker 看見」。
- [ ] 規劃（spec 029）— 成員從 dashboard 複製**一行指令**裝好 Codex 並指向本平台，
  日常純 `codex` 零參數、零環境變數、切 model 不脫鉤、無 WebSocket 紅字。**真機已驗**的設定：自訂 provider
  `ccsh`（`wire_api="responses"`、`requires_openai_auth=true`、`supports_websockets=false`、`base_url`=本平台）
  → 切 model 存活、無 405；`codex login --with-api-key`（auth.json）→ 零環境變數；抓 GitHub Rust binary → 免 Node。
  **本階段做 device-flow（RFC 8628）**：安裝腳本要 device code → 成員在 dashboard 授權 → 腳本拉一把**新 mint
  的 per-device 憑證**（建立在階段 18 的 1:N 憑證模型上）→ 灌進 Codex auth.json。使用者**不必複製貼長 token**、
  每台一把、輪替不連坐。Codex 端只看到一把普通 key（不在乎來源）。

### 階段 20：scoped application credentials（credential ↔ allocation 多對多）✅（rev 53 上線，2026-06-05）
- [x] 已完成（spec 030，2026-06-05）— 把憑證從「綁**一筆**分配」升級為「**成員建立、可命名的應用 key，指定它能用哪一組分配（model）**」；
  呼叫依 request 的 model 歸戶到對應分配。一個應用一把 token 即可用多 model、自由 `/model` 切換、可調整範圍、可單獨撤回。
  **動機**：現在「一 token 一 model」是業界少見的細粒度；一個 app（如 Codex 要 chat+embedding、agent 要多 model）需要一把
  key 跨多 model。**業界對照**：GitHub fine-grained PAT（token 選一組 repo）、service account / service principal（GCP/Azure/AWS
  IAM：應用身分被授予一組資源）、Azure APIM subscription→product（一把 key 綁一組 API、用量按 product 計量）、OAuth2 scopes。
  即 **scoped application credentials（capability-style，per-call metered to the matching allocation）**。
  **範圍**：`credential ↔ allocation` 多對多（join 表）+ `credential.member_id`；約束「一把 key 綁的分配 model 不重複」（歸戶無歧義）；
  `lookup_by_token` 回**一組**分配 → 依 model 選中歸戶/扣額度；`model_mismatch` = 「model ∉ scope」；應用憑證 CRUD（命名 + 增刪可用分配）；
  「裝置與憑證」清單**升成員層**（一裝置/應用 = 一把 key = 一組 model）；device-flow 授權頁改**勾選多筆分配**（不為 Codex 特別過濾）；
  **既有單分配 token 零回歸**（migration，Postgres 驗）。**治理**：admin 決定成員有哪些分配（model 可用性）、可管理任一成員的應用憑證；
  成員自助只能在**自己已被授予的分配**範圍內打包（無提權，對應 capability 的 attenuation）。**收尾 A**（移除舊「如何呼叫」Codex 分頁、
  全站單一 Codex 安裝說明）併入本階段。對應原則 1（憑證隔離，措辭一般化為 N:M——見 principles.md）+ 原則 2 可追蹤性 + 原則 5 集中管理。
  〔階段 18 的 1:N 是本模型的特例（一把 key 綁一筆分配）。〕
  **實際交付**：`Credential` 去 `allocation_id`、加 `member_id`；新 `CredentialAllocation`（join + `UNIQUE(credential_id, resource_model)`，
  migration `0017` in-place，**既有單分配 token 零回歸**——Postgres 整合測試固化）；proxy 熱路徑 `token→key→依 model 挑分配`
  （401/403 model_mismatch，下游 status/quota/billing 不變、仍 per-allocation）；`/me/credentials`（建/列/PATCH scope/rotate/撤回）、
  admin `/admin/members/{id}/credentials` + `/admin/credentials/{id}`（治理 + 稽核）；device-flow approve 改 `allocation_ids`（多選）；
  前端 `app-credentials-card`（成員層、多選建立、編輯 scope）+ device 授權頁多選 + **移除舊 Codex 分頁（收尾 A）**。
  **529 後端 + 125 前端測試綠。** 業界定位：scoped API key / service account / APIM subscription→product。

### 階段 21：憑證 UI 術語與層級收斂 ✅（rev 54 上線，2026-06-05）
- [x] 已完成（spec 031，2026-06-05）— 把「金鑰/應用/憑證/裝置/token」收斂成**單一名稱「應用金鑰」**、**單一管理處**
  （dashboard）；分配（model）詳情頁的金鑰區降**唯讀**（列「能用此 model 的應用金鑰」、每筆顯示**全部**可用 model、連本尊），
  **消除「撤一把無聲連坐其他 model」**（UI 與原則 1「撤一把不連坐」一致）；應用金鑰**可改名**（含自動產生的「預設」）；
  撤回確認**明示**會一起失效的 model；admin 治理移到成員詳情頁（唯讀清單 + 撤回 + 改名）；退役舊 `DeviceCredentialsCard`。
  **唯一後端改動**：既有 PATCH 多收選填 `name`（member + admin，留稽核 `credential_renamed`）；**無 schema 變更、無 migration**。
  **533 後端 + 125 前端測試綠。** 對應原則 1（UI 與隔離承諾一致）+ 原則 5（單一管理路徑）+ 原則 6（白話、降混淆）。

### 階段 22：會員介面分頁化 + 金鑰/分配概念釐清 ✅（rev 55→56 上線，2026-06-05）
- [x] 已完成（spec 032，2026-06-05）— 把會員「一頁長捲」的儀表板拆成**頂部導覽分頁**
  （我的儀表板／金鑰／分配／用量／模型目錄），每件事有單一所在地、可深連結。儀表板降為**精簡總覽**
  （活躍金鑰/分配計數 + 本月用量摘要 + 安裝 Codex 快速接入 + 待辦提示：無金鑰→去建、有可領取→去領）；
  既有自足元件（`AppCredentialsCard`、分配卡列、`UsageSummary`+圖表、`CodexInstallCard`）純搬到各自路由頁，
  既有深連結 `/dashboard/allocations/:id` 原樣保留。分配頁與金鑰頁各放一句白話解釋「**分配＝你能用哪些模型；
  金鑰＝拿來連線的鑰匙**」。金鑰卡「改名」+「編輯 model」併為**單一「編輯」**（單一 PATCH 同送 name+scope，
  後端早已支援、零改動）。admin Provider 頁「Rotate」用詞改**「重新填寫上游金鑰」**（管理員重新填入從上游
  拿到的 key，非系統產生；程式識別字不變）。**收尾微調**：管理員子導覽列改**只在 `/admin/*` 顯示**
  （會員頁面不再被那排管理選項干擾）、移除儀表板「登入方式：google_oidc」原始 provider 字串。
  **純前端、無 schema、無 migration、無新端點、無新套件**——只 bump `frontend.image.tag`，backend 維持 `sha-277b0db`。
  **133 前端測試綠**（既有零回歸 + 3 新頁測試 + 導覽/儀表板/金鑰卡/providers 更新）。對應**原則 6 可達性**
  （白話 UX、每件事有明確去處、桌機+手機堪用）+ **原則 5 集中管理**（每件事單一所在地）。細節見 `specs/032-member-ui-tabs/`。

### 階段 23：模型目錄 ↔ LiteLLM 登錄表對接 ✅（rev 64 上線，2026-06-08）
- [x] 已完成（spec 033，2026-06-08）— 把 LiteLLM 內建登錄表（`litellm.model_cost`，~2776 筆，含 context/能力/公開牌價）
  接進管理員模型目錄，**殺冷啟動**：建立時搜 LiteLLM key → 自動帶入 context/modality/能力 + 建議價、slug 預設＝key；
  自訂 deployment（查無 slug）指定「對照基礎模型」借中繼資料、價格自訂。`model_catalog.litellm_sync`（**新 nullable JSON 欄、
  migration 0018 additive**）記每欄**來源**（litellm/borrowed/manual）+ 匯入快照；手改轉 manual。**一鍵檢查更新**：線上抓最新
  （timeout → 回退 bundled）→ 逐欄 old→new + 來源 → **選擇性採納**（manual 欄不覆寫）；採納價 **append 一筆 price_list 版本**
  （`litellm@<ver>`，不蓋舊）。**價目表仍是計費唯一真理、LiteLLM 只給建議**（原則 2 可追蹤性 + 原則 5 集中管理：catalog 是唯一真理、
  litellm 是建議流非並行權威）。`litellm_registry` adapter 集中所有 litellm 讀取/對應（版本變動只改一處）。**不新增套件**。
  **556 後端 + 137 前端測試綠。** 線上抓＝對外連線，部署已驗 pod egress 可達 `raw.githubusercontent.com:443`。對應原則 6 可達性
  （admin 免冷啟動手打、一鍵維護）。細節見 `specs/033-litellm-catalog-sync/` 與 experience「前置 client 自帶模型目錄…」相關教訓。

### 階段 24：模型目錄 admin 體驗整合 + 充分利用 LiteLLM ✅（rev 66 上線，2026-06-08）
- [x] 已完成（spec 034，2026-06-08）— 階段 23 接了 LiteLLM，但體驗散在**三個世代疊出的畫面**且彼此重疊：「加入 Model」（階段 23，有帶入）、
  「編輯基本資訊」（階段 4/5，純手打、沒接 LiteLLM、沒顯示已存的來源標記）、「編輯價格」（階段 7，自帶一套「常見範本」硬編價格，
  與 LiteLLM 建議價打架）。且「檢查更新」埋在列表列、不在實際編輯的詳情頁。違反**原則 5 集中管理**（同一件事該只有一條路徑）。
  **目標**：把三畫面收斂成**詳情頁單一中樞**——每欄顯示來源徽章（LiteLLM/借用/手動）、「檢查 LiteLLM 更新」前移到詳情頁顯眼處
  （後端 `litellm-check` 本就同時回 metadata + 價格差異）、退役價格「常見範本」改用 LiteLLM 建議價（帶入＝同步同一機制）。
  **充分利用 LiteLLM**（實測 litellm 每模型 **153 欄、16 種 mode、34 個能力旗標**，階段 23 只用了 ~6 欄/2 旗標）：
  把決策相關的帶進既有欄位（能力旗標 2→~10：reasoning/pdf/prompt_caching/web_search/audio/video/structured_output…、補
  `max_output_tokens`、mode 用來推 modality）；**其餘原樣放進已存的 `litellm_sync.snapshot`，詳情頁開唯讀「LiteLLM 原始資訊」面板**
  （想深入者看得到全部、不污染主欄位）。**不升 mode 為一等公民、零 migration**（除非後續真要可篩選再評估）。對應原則 5（單一中樞）+
  原則 6（admin 幾乎零手打、資訊更完整）。計費邊界不變（價目表仍是計費唯一真理，LiteLLM 只給建議）。

### 階段 25：responses 支援判斷（實測 + 手動雙來源）✅（rev 68 上線，2026-06-08）
- [x] 已完成（spec 035，2026-06-08；無 migration、無套件）— 釐清三軸：①模型原生 API 型態（LiteLLM `mode`）②模型能力（LiteLLM 旗標：vision/reasoning/pdf…）③**我們 gateway 的端點可用性**
  （`/v1/responses` 等）。階段 24 一度把 ③ 的 `responses` 從 ① mode 推導、塞進 ② capabilities——概念混淆，且 LiteLLM 同步會洗掉它（latent bug）。
  **核心想法（採用者提案）**：「能不能走 responses，**打一次就知道**」。**目標**：responses 支援由**雙來源**判定——「**實測**」（runtime 預設先打
  litellm `aresponses`，通即支援、不通回真實 `upstream_error`；admin「測試 responses」鈕沿用既有 `test-connection` 1-token 模式記 `tested`）+
  「**手動**」（admin 直接設可用/不可用，蓋過測試）。**runtime 軟化閘門**：不再因靜態 capability 缺失誤擋，唯一事前擋＝admin 手動標「不可用」。
  目錄顯示「Agent 相容（Responses）」徽章 + 來源（測試/手動），成員可篩。**LiteLLM 完全不碰 responses**（採納改 merge-preserve，bug 根除）；
  移除 mode→responses 衍生。對應原則 6（成員看得到哪些可用於 Codex、admin 不必猜）+ 原則 5（單一清楚來源，不與 LiteLLM/mode 混）+
  experience「採用前先驗證 SDK 能力邊界」（推到極致＝實測為真理）。**零 migration、零套件、計費不變。**
  **實作**：軸③ 狀態以既有 `capabilities` JSON 的內部標記承載（`responses` / `responses:blocked` / `responses:tested` / `responses:manual`），
  集中於 `services/responses_support.py`；軟化閘門只在手動 blocked 事前擋；admin `POST .../test-responses` + `POST .../responses-support`；
  成員目錄過濾內部標記、輸出 `responses_support {state, source}`；litellm 採納 merge-preserve、移除 mode→responses 衍生。588 後端測試綠。

### 階段 26：admin 依模型種類一鍵測試模型是否可用 ✅（rev 74 上線，2026-06-08）
- [x] 已完成（spec 036，2026-06-08；無 migration、無套件）— 模型詳情頁加「測試模型」，依**種類**打對應最小真實呼叫、結果即答案（沿用 test-responses 的「結果即回應、不 5xx」）：對話（1-token completion）、embedding（短字串）、TTS（短文字→語音）、圖片生成（最小尺寸）；TTS/圖片**會計費 → 確認後才打**（前端對話框 + 後端 `acknowledge_billable` 強制雙保險）；STT/unknown（當時）顯示「尚不支援自動測試」不打（**後經 rev 90–93 演化，見下方 refinement**）。**種類判定**（`services/model_kind.py`）優先 litellm `mode`（讀既有 `litellm_sync.raw.mode`）、退 modality——因 litellm 把 embedding 映成 output `["text"]` 與 chat 撞型，光看 modality 分不出（手動 embedding 退 chat、會明確失敗，已知限制）。補 `upstream.py` 的 `aembedding`/`aspeech`/`aimage_generation`（litellm 既有函式，零新套件）。測試是真實呼叫但只寫 audit（新 `model_tested`）、不寫成員 CallRecord（無無歸屬影子用量）。與既有「測試 responses」並列不重複。對應原則 6（admin 就地知道模型能不能用、不必繞供應商頁）。618 後端 + 143 前端測試綠。
  - **後續 refinement（rev 90–93，2026-06-12）**：原 if/elif dispatch 演化成**資料驅動 recipe 表**（`services/model_test.py` 的 `RECIPES` ＝「**能不能測 ⟺ 有沒有 recipe**」單一真理，`is_testable`/`is_billable` 從表衍生——根治了「`is_supported` 說支援、卻無對應分支 → 靜默 no-op → 假『通過 0ms』」的 drift）。補齊 **ocr / stt / image_edit / search** 真分支（各送最小合法 fixture：1×1 PNG / 0.3s 靜音 WAV），現只剩 `unknown` 不可測。線上實測連帶揭露並修掉**生產 `/v1/ocr` 的 provider 路由 bug**（litellm OCR 不認 `azure/`、需 `azure_ai/`，於 `upstream.aocr` 重映——同一通道連帶修好端點本身）。**ocr / stt 已線上驗通；image_edit / search 待非 Azure provider**（FLUX/Stability 做 image_edit、Perplexity/Tavily 做 search；Azure 無此兩類模型）。對應**原則 7**（capability 從執行定義衍生＝結構上不可能 drift）。詳見 experience「能不能測這個種類與實際怎麼測必須同源」「新端點光壞 token→401 不算驗過」。

### 階段 27：應用分頁（應用目錄）—— Codex 為第一個應用 ✅（rev 78 上線，2026-06-09）
- [x] 已完成（spec 037，2026-06-09；無 migration、無套件）— 新增成員端「**應用**」分頁（`/apps`，頂部導覽），把「我有金鑰了、接到哪些工具、怎麼設定」變成單一所在地。
  **實作**：v1 單一 Codex 卡——狀態（依 `/me/allocations` 新衍生欄 `agent_compatible` 算你有幾個 Agent 相容分配；0 → 指引、不給建立鈕）+ 一鍵設定（既有 `CodexInstallCard` 從 dashboard/金鑰頁搬入）+ 建金鑰捷徑（重用 `POST /me/credentials`、picker 只列 Agent 相容、預選、名稱預設 Codex、token 顯示一次）+ 多介面（桌面 App 文案 △→✓：走 CLI 一鍵安裝後共用 `~/.codex` 即可用，實測）。唯一後端＝`/me/allocations` 加唯讀 `agent_compatible`（讀既有 `responses_support`，零 migration、無新端點）。VS Code 擴充自動裝因無法確認 extension id → v1 link-only。620 後端 + 146 前端測試綠。對應原則 6（拿到鑰匙後真的接得上工具）+ 原則 1（scoped application credential 正門化）。
- [ ] 規劃 — （原規劃內容，保留供日後加一般 OpenAI 應用參考）新增成員端「**應用**」分頁（頂部導覽），把「我有金鑰了、接到哪些工具、怎麼設定」變成單一所在地。
  本質：平台是 OpenAI 相容 → 任何會講 OpenAI API 的客戶端都能指過來；應用目錄＝**精選一批能接的客戶端 + 各自設定 + 建金鑰捷徑**。
  與三個既有概念漂亮收斂：**階段 20「應用金鑰」**（憑證本就是「一把 key = 一個應用、綁一組模型」，現在給應用一個正門）、
  **階段 25「Agent 相容（Responses）」徽章**（Codex 需要 responses 模型，捷徑可據此預過濾）、**dashboard 的 `CodexInstallCard`**（升格搬進來當第一張卡，符合階段 22 單一所在地）。
  框架：平台有**三個目錄**——模型目錄（有哪些模型）／使用情境目錄（能做哪些任務）／**應用目錄（能接哪些工具）**。
  **v1 範圍**：單一「**Codex**」應用卡。
  - **設定共用、取得程式各異**：device-flow 一鍵 → 寫好 `~/.codex`（config + auth.json），CLI / IDE 擴充 / **桌面 App** 全部讀同一份。
    **實測修正**：桌面 App 之前標「△ 不建議」（那是針對「在 App GUI 手動填 API key」會踩 openai/codex#24457）；
    但走「**先跑 CLI 一鍵安裝 → App 讀共用設定**」這條**實測可用**（2026-06-08 使用者真機），故降警告為「✓ 用一鍵安裝後桌面 App 也能用（共用設定、免再設定）」。
  - **安裝＝「能自動的盡量自動，不能的給連結」**：一個指令裝好 CLI + 設定（+ 可選偵測 `code` 順手裝 VS Code 擴充）；
    桌面 App / Cursor / JetBrains 等 GUI 安裝**無法可靠跨平台自動化**（採用前先驗證能力邊界 + YAGNI），故給下載/marketplace 連結 + 一句「裝好免再設定」。**不做萬能安裝器**。
  - **建金鑰捷徑（v1 含）**：對 Codex 就是 device-flow（本就 scope + mint 一把 key），scope 預選「Agent 相容（responses 可用）」分配，避免成員手滑挑到 Codex 接不上的模型。
    （「手動建金鑰顯示一次 → 貼進設定」這條留給未來的一般 OpenAI 應用，如 Continue / OpenWebUI / LibreChat；v1 用不到。）
  - **誠實說明**：v1 兩個介面都是 Codex 家族，「應用目錄」名稱會略空——但目的是把**架構**（清單 + 每應用設定卡 + 建金鑰捷徑）鋪好，之後加一般應用只是多塞卡。
  對應**原則 6 可達性**（拿到鑰匙後真的接得上工具、非技術者照做即可）+ 願景「主流 agent 工具開箱即用」。

### 階段 28：應用商店化（tile 格狀 + 詳情頁 + 主畫面智能推薦）✅（rev 79→80 上線，2026-06-09）
- [x] 已完成（2026-06-09；純前端、無 migration、無套件）— 把階段 27 的單張 Codex 卡進化成**應用商店**式體驗：
  `/apps` 改**格狀 tile 清單**（真實 logo + 名稱 + 一句話；靜態註冊表 `frontend/src/lib/applications.tsx`，一筆＝一張 tile + 一個詳情頁）、
  `/apps/:appId` **詳情頁**（狀態 + 一鍵設定 + 建金鑰捷徑，搬進 `components/codex-app-detail.tsx`）、
  主畫面（儀表板）**智能推薦**（有 Agent 相容模型才推「試試 Codex」+「看全部應用」連結）。Codex logo＝OpenAI mark inline SVG；不放「即將支援」placeholder。
  **rev 80** 補：官方桌面 App 裝不起來可改用社群鏡像 [codex-app-mirror](https://github.com/Wangnov/codex-app-mirror)（非官方、風險自負），共用設定仍是推薦路徑。
  對應**原則 6 可達性** + **原則 7 演進性**（註冊表＝之後加 Continue / OpenWebUI 只加一筆，不動架構）。149 前端測試綠。

### 階段 29：多端點開放（embedding / OCR / 圖片 / 語音 …）＋ 計費一般化（規劃中）
- [ ] 規劃 — **問題**：gateway 目前對成員只開 `/chat/completions` + `/v1/responses`；但模型目錄能收 embedding / 圖片生成 / 語音(TTS/STT) / OCR / rerank 等模型（litellm 認得、`supported_endpoints` 有寫），這些**成員卻呼叫不到** → 「**目錄能放，但 gateway 服務不了**」的不一致（`mistral-document-ai`〔mode=ocr、`/v1/ocr`〕暴露；Phase 26 的 embedding/tts/image wrapper 目前也只給 admin 測試、未對成員開 proxy）。
  - **核心約束（本主題的不變式）**：**目錄誠實——「能收 ⟺ gateway 服務得了」**。某端點未開之前，目錄 MUST NOT 把該類模型假裝成 chat（修掉 `litellm_registry._capabilities` 的 `or ["chat"]` 對非 chat mode 硬塞 chat），且詳情頁明確標「**平台尚未支援此類型呼叫**」。對應原則 6 可達性的反面：列了卻用不了＝名義可見、實質不可達。
    - **✅ 誠實債已還（spec 041，rev 86，2026-06-11）**：`_capabilities` 改 `return caps`、admin 詳情顯「類型」欄——下記原始問題供歷史。原**⚠️ 待還誠實債（增量 ② 刻意延後，spec 040 R5）**：`_capabilities` 的 `return caps or ["chat"]` 把「無能力旗標的非 chat 模型」（OCR / embedding / 圖片 / 語音）兜底成 `["chat"]`，且**已寫進現有模型的 DB `capabilities`**。後果：**admin 模型詳情頁的「能力」欄誤顯 chat**（如 `azure/mistral-document-ai-2512` 明明 mode=ocr / `/v1/ocr` 卻顯「能力：chat」，2026-06-11 使用者實際撞到）。成員面已用 `kind` 衍生欄修好（成員目錄顯正確類型 + `/v1/ocr` 範例），故僅 admin 面殘留。**修法（增量 ③ 前或收尾還）**：① `_capabilities` 移除 `or ["chat"]`（chat-able mode 仍 append chat，其餘無旗標→`[]`）；② 現有模型需重新「檢查 LiteLLM 更新」採納才會更新 DB；③ 順手讓 admin 詳情頁顯「類型（kind）」（能力 vs 類型分兩軸，原則 7 軸正交）。**影響面**：所有非 chat litellm 模型的能力欄會變誠實——須回歸驗 facet 計算/篩選對空 capabilities 無礙。
  - **基礎建設已就位（演進紅利）**：統一 preflight pipeline 端點無關（chat/responses 已共用）、litellm library 各端點函式（`aembedding`/`aspeech`/`atranscription`/`aimage_generation`/`aocr`/`arerank`…，Phase 26 已包三個）、`model_kind` + `supported_endpoints` 已知「模型走哪端點」。**加端點 ≈ 解析請求 → 跑同一條 preflight → 呼叫對應 litellm 函式 → 記帳**，非重寫（原則 7）。
  - **主要工作量＝計費一般化（碰核心、需 migration）**：`PriceList`/`CallRecord` 從 token 中心 → 能裝**非 token 單位**（每頁 / 每張圖 / 每秒音訊 / 每字元）。並處理 binary/multipart（音檔上傳、圖片/語音 bytes）與各端點自己的濫用上限（token-based 配額管不到「每張圖」——descope 的「每日上限」可能在此以「每天 N 張/頁」回來）。
  - **計費方法論（沿原則 7「借計算不借帳本」+ Phase 23/24「litellm 建議、PriceList 是真理」）**：litellm 的 `model_cost` / `completion_cost()` 已內建異質單位（per-token / per-page / per-image / per-second / per-character）——當**建議價/單位來源**，snapshot 進**我們自己的 `PriceList`**（append-only、point-in-time、可稽核），計費仍用 PriceList、歸戶到分配。**不採 litellm Proxy 的計費系統**（那是刻意不用的形態，且不認得我們的「分配」模型）。litellm cost 對新模型可能漏/錯 → admin 可覆寫（採用前先驗證）。
  - **增量次序（按需、別 big-bang）**：① embedding 先（需求最廣、計費仍 token、幾乎不動計費層）→ ② 計費一般化（其他端點共同前置，做一次受惠全部）→ ③ OCR / 圖片 / STT / TTS 各一個小 phase → ④ rerank / moderation 看需求。每個端點 = 一個小 phase（複用 pipeline + 既有 wrapper + 計費一般化）。
    - **✅ 增量 ② 已出貨**（spec 040，2026-06-11；rev 85，migration 0019 純加欄、無套件）：計費層一般化（`price_list` 加 `price_unit`/`price_per_unit_usd`、`call_records` 加 `quantity`/`unit`，皆 nullable、NULL ⇒ token、token 路徑 byte-identical 零回歸；`calculate_cost` 不動、新增 `calculate_unit_cost`）+ 對成員開放 **`/v1/ocr`**（按頁計費、`proxy/ocr.py` 近乎複製 embeddings、頁數=`len(OCRResponse.pages)`、`upstream.aocr` 第 4 個 wrapper）作為**第一個非 token 端點**證明一般化。admin `/prices` 加選填每頁價（litellm 僅建議、PriceList 是真理、point-in-time）；`model_kind` 加 `ocr`、目錄/前端範例帶出。**關鍵抉擇**：原訂用圖片生成證明，但實測 litellm `model_cost` 發現 Azure `gpt-image-*` 其實是 token 計費（不觸發一般化）→ 改用 OCR（`ocr_cost_per_page` 乾淨非 token、JSON 進出無 binary）。**已知限制**：非 token 呼叫此階段不被 token 配額擋下（每單位上限為後續）。659 後端 + 157 前端測試綠。**剩餘**：③ 圖片（token，似 embedding）/ TTS / STT（binary I/O）/ rerank。
    - **✅ 增量 ① 已出貨**（spec 038，2026-06-09；rev 82，無 migration、無套件）：`POST /v1/embeddings` 對成員開放——`proxy/embeddings.py` 近乎複製 chat router，走同一條 `run_preflight`（憑證/分配/存取/憑證）、**沿用 token 計費**（input token × 現價、`calculate_cost` completion=0）、結果即 embedding 回應、上游錯誤 → `upstream_error`（502），驗證 litellm `EmbeddingResponse.usage` 帶 `prompt_tokens`。成員目錄序列化加唯讀衍生 `kind`（`model_kind`）→ 前端 `api-usage-example` 對 embedding 模型顯 `/v1/embeddings`（curl/python/js）。**印證「加端點 ≈ 跑同一條 preflight + 對應 litellm 函式 + 記帳」**（原則 7）。順手修一個被 pytest-randomly 順序曝光的潛在 bug：`records.list_for_allocation` 的游標排序鍵不一致（排 `(started_at, id)` 卻只用 `id < before` 過濾，同毫秒 ULID 隨機段使分頁筆數不定）→ 改成 keyset 複合游標 + 回歸測試。628 後端 + 151 前端測試綠。
    - **✅ 增量 ③ 已出貨**（spec 041，2026-06-11；rev 86，無 migration、+1 套件 `python-multipart`）：四端點全開——`/v1/images/generations`（token，沿用 embedding）、`/v1/rerank`（**per-query** `unit="query"`，一般化第二單位）、`/v1/audio/speech`（TTS，**binary 音檔輸出** `Response audio/mpeg`，per-character，bytes 當下記帳非 finally）、`/v1/audio/transcriptions`（STT，**multipart 上傳**，token 計費；`TranscriptionResponse` 無 duration → per-second 延後）。**目錄誠實債已還**：`_capabilities` 移除 `or ["chat"]`（chat-able 仍 append chat、零回歸），非 chat 模型能力欄不再假裝 chat；admin 詳情序列化加 `kind` + 前端顯「類型」欄（與能力分兩軸）。形狀全 inspect litellm 實測（image usage / rerank per-query / TTS `HttpxBinaryResponseContent.content` / STT 無 duration）。**Constitution Deviation**：+1 依賴 `python-multipart`（FastAPI 解析 STT 上傳必需，其官方 optional dep）。680 後端 + 161 前端測試綠。**多端點主題收尾**（剩 rerank/moderation 外的端點看需求）。
  - **圖表/視覺化（計費一般化的下游）**：token / 頁 / 張 / 秒 / 字元**彼此不能相加**，唯一跨單位的共同分母是**花費（USD）**。故**聚合 / 跨端點的圖一律以「花費」為軸**——既有的 daily spend bar、各 model / provider / tag 花費 donut **本就 cost-based，新單位進來自動涵蓋、不用改**；只有明寫 token 的圖（輸入/輸出 tokens 分項、daily trend 的 token 模式）需改成 cost 預設或按端點拆。**原生單位只在「單一模型/端點」明細出現**（同單位內可加總，跨單位不加總）。`token / cost` 切換演化為「cost 永遠可用為預設、『原生單位』檔只在篩到單一單位時有意義」。資料層：`CallRecord` 帶**數量 + 單位**、`aggregate_usage` 加 `unit` 維度（跨切 `sum(cost)`、單位圖 `filter` 單一單位 `sum(quantity)`）。對應原則 6（成員看「花了多少 USD」最好懂）+ 原則 7（別硬把頁/張正規化成 token＝假統一）。
  - 對應**原則 6 可達性**（成員真能用那類模型）+ **原則 2 可追蹤性**（計費跟上、可稽核）+ **原則 7 演進性**（新端點＝adapter＋新軸＋資料，pipeline 不重寫）。

### 階段 30：管理員成員管理批次化 + 刪除人體工學 ✅（rev 84 上線，2026-06-10）
- [x] 已完成（spec 039，2026-06-10；無 migration、無套件、無新 enum）—— **安全刪除**：`DELETE /admin/members/{id}` 不再因有分配而擋下，`MemberService.delete` 在單一交易內以 **ORM 顯式**連帶（撤分配 + 刪憑證/連結 + 呼叫紀錄 `allocation_id` 設 NULL〔孤兒保留、`subject` 保住歸屬〕 + 刪成員），**不靠 DB ondelete**（SQLite 本專案未開 FK pragma，靠 DB cascade 會 dev/prod 不一致）；守衛不可刪自己（403）/ 最後一位 active 管理員（409）。**批次刪除** `POST /admin/members/bulk-delete`（多選、逐筆獨立 tx、回 per-item 摘要）。**批次預建** `POST /admin/members/bulk-create`（貼 email 清單 → 逐筆 local_password + 邀請連結、同批去重、created/exists/invalid/duplicate）。前端 `members.tsx` 多選 + 批次列 + 批次新增對話框 + 單筆刪除確認升級。646 後端 + 155 前端測試綠；integration 在 Postgres（FK 真強制）驗孤兒保留。對應原則 6（admin 真管得動大規模成員、不必靠工程師下 SQL）+ 原則 2（刪除不毀稽核史）+ 原則 7（批次＝單筆邏輯迴圈）。
  - 原規劃 — **問題**：成員規模一大（如整批導入學號帳號），現有 admin 成員管理是**逐筆**操作：一次只能新增一位、刪除一位，且**刪除常被擋下**（`delete_member` 在成員有任何分配〔active 或 revoked〕時回 `revoke and delete allocations before deleting member`，因 `Allocation.member_id` FK 為 RESTRICT、且分配連著 `CallRecord` 用量/稽核史）。管理員面對「幾百個 google_oidc 自動註冊進來的學生帳號」時非常痛。
  - **① 批次新建**：一次貼上多個 email（或 CSV）→ 後端逐筆套用既有 `create_member`（含白名單/自動標籤規則），回每筆成功/失敗摘要（哪些已存在、哪些不符白名單）。**沿用既有單筆邏輯逐筆跑**，非另寫一套（原則 7：批次＝迴圈 + 結果聚合，不是新規則）。
  - **② 批次刪除 / 批次操作**：列表加多選（checkbox）+ 批次動作列（刪除、加/移標籤）。**刪除要解決現在「被擋下」的人體工學**：提供「強制刪除」流程＝先撤回並刪掉該成員的分配（連帶處理 `CallRecord` 的保留策略：用量史不可無聲消失——分配刪除前應決定是「轉為孤兒保留供稽核」還是「明確一併清掉」，**對應原則 2 可追蹤性**），再刪成員。單筆與批次共用同一條「安全刪除」服務。
  - **核心約束（別破壞可追蹤性）**：用量/稽核史（`CallRecord`、audit）是**原則 2 的載體**，批次刪除 MUST NOT 讓它無聲蒸發。設計時先決定 orphan-retention vs explicit-purge 策略，並在 UI 明說「刪了會連帶失去這些人的用量紀錄」。每筆批次操作仍寫 audit（`member_deleted` 等）。
  - **不在此階段**：成員的權限/角色批次變更（目前只有 is_admin 旗標，量不大、逐筆即可）。
  - **已存在、不必做**：自動**標籤**規則的「@ 後網域」比對——`TagRule.MatcherType` 後端前端**早已支援** `email_domain`（網域完全比對）與 `email_suffix`（結尾比對），新增規則時從 matcher 下拉改選即可（預設是 `email_localpart_regex` 才讓人以為只有 local-part）。
  - 對應**原則 6 可達性/可用性**（管理員真的管得動大規模成員）+ **原則 2 可追蹤性**（批次刪除不毀稽核史）+ **原則 7 演進性**（批次＝既有單筆邏輯的迴圈 + 結果聚合）。

### 階段 31：統一端點架構（資料驅動 registry）＋ 全端點覆蓋 ✅（rev 87 上線，2026-06-11，重構 + moderation/search/image_edit）
- [x] 已完成（spec 042，2026-06-11；無 migration、無套件）—— **資料驅動端點架構**：5 個複製貼上的非串流 proxy handler（embeddings/ocr/images/rerank/audio，~741 行）收斂成 `proxy/engine.py`（唯一執行流程）+ `proxy/endpoint_spec.py`（三軸正交：IOShape × Meter × call）+ `proxy/registry.py`（EndpointSpec 註冊表）。**加同形態端點＝加一筆資料**。以此新增三個端點各 = 1 wrapper + 1 spec：`/v1/moderations`（token）、`/v1/search`（per-query，`call` 把 slug 對映成 `asearch` 的 `search_provider` 而非 model——證明 registry 承載各異參數對映）、`/v1/images/edits`（multipart、每張圖）。**串流端點（chat/responses）刻意排除**（串流中記帳、執行形態不同，handler 零觸碰＝零回歸）。**零回歸鐵證**：5 個既有端點 contract 測試斷言不改全綠（那些測試檔 git diff 為空）。`model_kind` 加 moderation/search/image_edit 類型。699 後端 + 164 前端測試綠。對應原則 7（資料勝於程式 + 註冊表 + 軸正交 + 適配層，四手法齊發）。**剩餘未開**：video_generation（async job）、realtime（WebSocket）、vector_store（資源管理）——各自獨立評估，多半 descope（見下原規劃）。
  - 原規劃 — **問題**：階段 29 一個個手寫了 7 個 proxy 端點（chat/responses/embedding/ocr/image/rerank/audio），結構幾乎複製貼上——這是「同一概念該抽共用」的訊號（[[experience]]）。且還有 6 種 litellm mode 未開（image_edit / video_generation / search / moderation / realtime / vector_store）。目標：**把端點做成優雅、資料驅動、易擴展的架構**，並按需涵蓋全部「適合 gateway 模型」的端點。
  - **核心洞察**：端點只差**三個正交的軸**——① I/O 形態（JSON / binary 輸出 / multipart 上傳 / 非同步 job / WebSocket）② 計量策略（token / page / query / character / second …）③ 上游函式 + 必填欄位。優雅＝讓三軸各自獨立、用**資料**描述，共用流程只寫一次（原則 7：資料勝於程式、註冊表、守住軸正交）。
  - **三層設計**：
    - **Layer 1 共用執行引擎**（寫一次）：`parse → run_preflight → 上游 → 計量 → 計費歸戶 → record_call`＋統一錯誤處理。把現在散在 7 檔的重複收斂成一條。
    - **Layer 2 I/O 形態 handler**（每種形態一個，非每端點一個）：`json` / `binary_out`（TTS）/ `multipart_in`（STT、image_edit）/（未來）`async_job`（video）/（可選）`websocket`（realtime）。
    - **Layer 3 EndpointSpec 註冊表**（每端點一筆資料）：`{path, upstream_fn, io_shape, required_fields, meter}`。**加一個同形態端點＝加一筆資料**，不碰引擎。計量抽成 `Meter`（`TokenMeter` 讀 `usage`；`UnitMeter(unit, quantity_fn)` 算數量）——②計量是與①形態正交的第二軸。
  - **端點分級（誠實面對「全部」）**：
    - **同步推論（一請求一回應一筆帳）**：chat/embedding/image/ocr/rerank/tts/stt/**moderation**/**search**/**image_edit** → 三層架構完美涵蓋；moderation 最簡單（純 JSON）。
    - **非同步 job**：**video_generation** → 破壞「同步記帳」假設（送出回 job id、要 poll、用量等 job 完成才算）；需 job 狀態子系統，**獨立子專案**、不綁進來。
    - **WebSocket**：**realtime** → ✅ **已於階段 32 上線**（即時字幕轉錄）。雙向串流、與 request/response + 計費架構不同；原評估「大投資、很可能 descope」，實作後確認以「**借 litellm `RealTimeStreaming` relay 結構、但不經 litellm**」可控成本達成（自寫薄 WS relay，計量按秒/分鐘歸戶分配）。
    - **資源管理（非推論）**：**vector_store** → 有狀態、跨多次呼叫，不符「per-call 計量歸戶」的 gateway 模型，**可能誠實地不做**。
  - **實作切法（別 big-bang）**：① 先**重構**（零新功能）——7 個既有端點收斂成「引擎 + 形態 handler + 7 筆 spec」，**硬約束：既有端點 + 計費全程零回歸**（既有 contract 測試當金鋼罩）；② 資料化補同步推論端點（moderation → search → image_edit）；③ video（async）獨立評估；④ realtime / vector_store 確認需求後多半 descope。
  - **核心約束（目錄誠實延續）**：未開的 mode 由 `model_kind` 判 `unknown` → 成員端不誤開、admin 詳情顯「未知」（誠實機制已在運作，[[reference]] 階段 29③）。
  - 對應**原則 7 演進性**（資料勝於程式 + 註冊表 + 軸正交 + 適配層，四手法齊發）+ **原則 6 可達性**（按需把全部適合的端點開給成員）+ **原則 2 可追蹤性**（每端點計量歸戶不變）。

### 階段 32：即時字幕端點 `/v1/realtime`（realtime transcription WebSocket）✅（rev 95 上線，2026-06-12）
- [x] 已完成（spec 043 + 044；無 migration、+1 直接依賴 `websockets`）—— OpenAI 相容的 realtime transcription **WebSocket** 端點：客戶端串流音訊、即時收文字，用量**按秒/分鐘**計、歸戶分配、連線中可即時撤回。**自寫薄雙向 relay**（`proxy/realtime.py`，借 litellm `RealTimeStreaming` 結構但**不經 litellm**——它的 realtime 是 Proxy form、音訊繞過 gateway，會失去分配歸戶 + 即時撤回，見 experience「功能重疊 ≠ adopt」），含旁路週期協程 re-check 撤回。**計量**自算 client `input_audio_buffer.append` 的 PCM bytes → 時長，**任何斷線路徑（正常/異常/撤回）都落一筆帳**（不漏記）；單位依 PriceList（litellm 按 `input_cost_per_second` 計 → 預設秒、亦支援分鐘），沿用 0019 的 `call_records.{quantity,unit}`，**零 migration**。
  - **realtime 是能力軸、非 litellm mode**：litellm（PR #29775）把 `gpt-realtime-whisper` 標 `mode=audio_transcription` + `supported_endpoints` 含 `/v1/realtime`；`model_kind` 據此（或 admin `realtime` 能力標記）判 realtime——與階段 25 `responses_support` 同形狀（原則 7 守軸正交）。可從 admin「測試模型」跑 **WS 煙霧**（連線即收 `transcription_session.created`）當部署後協定真打；nginx `/v1/realtime` 加 WS upgrade。
  - **Azure URL 之坑（實作真打才現）**：必須 `intent=transcription` 且**不帶 `deployment=`**（帶了會被路由成對話型 realtime、轉錄模型不支援 → 400 OperationNotSupported），api-version `2025-04-01-preview`；用真憑證在 cluster 內探測 + 把 provider 拒絕 body 帶出才定位（rev 95）。詳見 experience「realtime 能力∈supported_endpoints」「採上游 WS 協定前用真憑證探測」。
  - **測試**：744 後端 + 164 前端測試綠；契約測試以 **mock provider WS** 在 CI 跑全 relay/計量/撤回路徑（engine 綁 pytest event loop、TestClient portal 會撞 asyncpg/aiosqlite，故直接呼叫 `handle_realtime` 注入 fake WS）；真連 Azure 以部署後「測試模型」按鈕驗。
  - 對應**原則 1/2**（歸戶分配、可追蹤）+ **原則 3**（連線中即時撤回，旁路協程 re-check 非只建立時檢查）+ **原則 6**（願景「主流工具開箱即用」延伸到即時字幕）+ **原則 7**（借結構不借帳本、能力軸正交、薄 adapter 把直連 WS 鎖在邊緣）。細節見 `specs/043-realtime-transcription/`。

### 階段 33：成本制配額（跨端點統一額度上限）✅（rev 96 上線，2026-06-13）
- [x] 已完成（spec 046；migration `0020` 純加欄、無新套件）—— 每分配新增選填「**每月花費上限（USD）**」，與既有 token 上限並列、任一超過即擋。以**花費為跨單位共同分母**治理 token + 非 token（頁/張/秒/分/字元）**所有端點**，補「非 token 用量繞過 token 月配額」的治理缺口（原則 1：額度綁分配、可調整可收回，對所有端點兌現）。preflight token 後並列一道 cost 檢查（新 outcome `rejected_cost_quota_exceeded`，VARCHAR enum 無 migration）；realtime **連線中** watcher 擴充（`committed 月花費 + 本連線 in-flight` ≥ cap → 主動 close + 已累計落帳，原則 3）；**未定價** `cost_usd` NULL → 不計入、不被擋（誠實，需 admin 補價才納管）；**自適應池只動 token 額度** → cost 上限天然不被再分配（SC-005）。admin create/patch 收上限 + 稽核 `allocation_cost_quota_updated`；成員卡顯「本月花費/上限」+ 接近上限提示。759 後端 + 164 前端綠；線上實證 $0 cap 跑 preflight 回 `cost_quota_exceeded`。〔與「每日上限不做」對照：本案是 **USD 月度硬上限**，非每日 per-unit 粒度。〕對應原則 1 + 2 + 3 + 7（USD 為跨單位共同分母、cost/token 兩軸正交）。細節見 `specs/046-cost-quota/`。

### 階段 34：「如何呼叫」可發現性重設計 ✅（rev 97 上線，2026-06-27）
- [x] 已完成（spec 049，PR #92 `374ab73`；純前端為主、無 migration、無套件）—— 把「如何呼叫」從「埋在分配/模型詳情兩個詳情頁」改成**金鑰為入口、應用為總站**：① 金鑰卡加「**如何使用這把金鑰**」對話框（base URL + `$TOKEN` + **model 下拉** → curl/Python/JS 範例即時填好；下拉來源＝該金鑰實際 scope 內分配的 model〔`/me/credentials` 的 `allocation_ids`〕，語意貼「**這把**金鑰」、順手教會 `model` 該填的 slug，根治「`id` 空白 → 模型不在範圍」的 Copilot 坑）；② 應用商店擴成「怎麼用」總站——新增「**直接用 API / SDK**」應用卡（複用 `ApiUsageExample`）與工具整合卡（Codex…）並列，靜態註冊表加一筆＝一張卡（原則 7）；③ 儀表板·分配·模型詳情 cross-link 指過來（「怎麼開始呼叫 →」「想接工具 → 看應用」）。新共用元件 `usage-explorer`（下拉 + 單一範例）+ `catalog-models` hook + `direct-api-detail`；`ApiUsageExample` 維持單一共用元件各處重用不複製（原則 5 + 「同一概念兩份必 drift」）。6 新前端測試綠。前後端同 `sha-374ab73` 一起部署（rev 97）。對應**原則 6 可達性**（怎麼用在拿到金鑰的當下、白話、不鑽）+ **原則 5 集中管理**（內容單一真理、他處連結）+ **原則 7 演進性**（應用商店＝註冊表）。**剩 SC-007 真人驗收**（成員「拿到金鑰 → 不問人完成第一次呼叫」）留維護者。細節見 `specs/049-usage-discoverability/`。
- [ ] 原規劃 — **問題**：成員（學生）回報「**如何呼叫**」找不到。現況 `ApiUsageExample`（curl/Python/JS + 各端點範例）**只埋在分配詳情、模型目錄詳情兩個詳情頁**，要先鑽進某個分配/模型才看得到；頂層（金鑰/分配 清單頁）沒有任何「怎麼用/開始」的字眼，資訊氣味（scent）斷掉。**對應原則 6 可達性的反面**：能力發了卻找不到怎麼用 ＝ 名義可達、實質難用。
  - **設計方向（方案 C：金鑰為入口、應用為總站）**：
    - **內容單一真理放「應用」**（原則 5 + 「同一概念兩份必 drift」教訓）：應用商店從「只有 Codex」擴成兩類卡——① **工具整合**（Codex、Copilot、Continue / OpenWebUI… 每張卡＝設定步驟，註冊表 原則 7「加一筆資料」）② **直接用 API / SDK**（複用 `ApiUsageExample`，curl/Python/JS）。`ApiUsageExample` 維持共用元件、各處重用不複製。
    - **入口錨在「金鑰」+ 儀表板**（原則 6：在「我拿到金鑰」的當下）：金鑰頁/卡加顯眼「**如何使用這把金鑰**」（base URL + `$TOKEN` + **model 下拉** → 範例即時填好）；儀表板待辦「有金鑰了 → 怎麼開始呼叫」連到應用對應卡。
    - **下拉來源＝這把金鑰 scope 內的 model（已定，方案 b）**：讀該應用金鑰實際被授予的分配（`/me/credentials` 的 `allocation_ids`，非成員全部 model），語意才貼「如何使用**這把**金鑰」；多串一點資料換正確性。
    - **model 下拉填 slug 是關鍵加值**：順手教會「`model` / 客戶端的 model `id` 該填這個 slug」，把「`id` 空白 → `模型 '' 不在範圍`」那類 Copilot 設定坑變成不會再踩。
    - 分配/模型詳情**維持模型專屬的 `ApiUsageExample`**（該情境是對的），加一句「想接工具 → 看應用」。
  - **做法（一個 spec，不切多刀）**：整包做成**單一 spec**——US1 金鑰頁「如何使用」+ model 下拉 / US2 應用商店擴成「怎麼用」總站 / US3 儀表板·分配·模型詳情 cross-link 指過來。內部用 user story 漸進交付，但**一次 specify→implement→一個 PR**（依維護者偏好「不要切這麼多」）。
  - **明確排除**：① 不把 curl 範例複製到多頁（drift，只放一處 + 連結）；② **Copilot 卡要等驗證**——Copilot 非主驗客戶端（會打 embeddings / 模型清單），確認在我們 gateway 能日常用再正式上卡，免得列了卻處處紅字；③ 標籤要喊得出「怎麼用/開始」，別只靠「應用」這個詞撐 scent。
  - 對應**原則 6 可達性**（怎麼用要在使用者拿到能力的當下、白話、不鑽）+ **原則 5 集中管理**（內容單一真理、他處連結）+ **原則 7 演進性**（應用商店＝註冊表，加工具＝加一筆資料）。

### 階段 35：供應鏈 — starlette / FastAPI major bump（規劃中）
- [ ] 規劃 — **問題**：`.trivyignore` 目前暫掛兩個 starlette CVE（CVE-2026-48818 SSRF+NTLM via UNC、CVE-2026-54283 ASGI advisory），兩者皆只在 starlette 1.x 修復，而 starlette 0.50.x 被 FastAPI 0.124.x 釘住（`starlette<0.51`）→ 需 **FastAPI major bump** 才能解鎖。兩個 CVE 在本服務皆**不可達**（Linux distroless、後端不解析使用者路徑/UNC、且在 frontend nginx + NetworkPolicy 之後），故**非阻塞**，刻意延後、不夾帶進無關 PR。
  - **範圍**：升 FastAPI 至帶 starlette 1.x 的版本，回歸驗 ASGI 行為（middleware、`UploadFile`/multipart、SSE streaming、WebSocket relay〔階段 32〕皆吃 starlette）；綠後移除 `.trivyignore` 兩條 starlette 條目。
  - **觸發條件（按需，非排程）**：FastAPI 釋出穩定支援 starlette 1.x 的版本、或該 CVE 之一在本環境變得可達時提前做。對應原則 7（快變的外部依賴鎖在邊緣、安全修補不滯後）+ 架構「相依套件追蹤（Renovate/Dependabot）」。

### 階段 36：OpenAI 相容 `/v1/models` ＋ Copilot 上卡 ✅（rev 98→101 上線，2026-06-27→28）
- [x] 已完成（spec 050，PR #93/#94/#95/#96；無 migration、無套件）—— 補上 OpenAI 相容**模型發現**端點，讓任何「連線時會列模型」的客戶端（Copilot、Continue、OpenWebUI、官方 SDK `models.list()`、curl）能指向本平台；以此真機驗證後把 **GitHub Copilot** 加為應用商店第二張工具卡。對應願景「**任何會講 OpenAI API 的客戶端都能指過來**」。
  - **`/v1/models` + `/v1/models/{id:path}`**（rev 98，backend `sha-d104990`）：Bearer 認證，回**呼叫金鑰 scope 內 active 分配**的模型，OpenAI list/model 形狀，`id`＝正規 slug（preflight 路由鍵、原樣可呼叫）；**scope 來源＝金鑰授權本身**（非 catalog 瀏覽過濾，原則 1），未定價仍列、paused/revoked 排除；**唯讀、不碰上游**（`proxy/models.py` + `AllocationService.list_active_scope_allocations`，掛既有 nginx `/v1`）。
  - **Copilot 應用卡**（rev 99→101，純前端）：設定步驟 + 一鍵建金鑰 + **一鍵帶出 `chatLanguageModels.json` 的 `models`**（填好全部 scope 模型、免手打 id）。**真機驗證**（SC-004）：維護者在 VS Code 跑通「列模型 → 對話」，校正出 `url` 填 base `…/v1`（Copilot 依 `apiType` 自己接端點）、bare slug 可用（catalog 目前全 azure、無歧義）。續接維持 **fail-loud**、卡上載明 per-分配對話限制（原則 2 +「接不上的續接要明確拒絕」教訓）。
  - 767 後端 + 176 前端測試綠。**教訓**：CI mypy 漏網（本機關卡要逐字對齊 CI）、第三方客戶端設定要**真機驗證**（文件對 `url` base-vs-完整端點會騙人）——皆入 `experience.md`。對應**原則 6 可達性**（任何 OpenAI 客戶端真接得上）+ **原則 1/2**（金鑰 scope、可追蹤）+ **原則 7**（應用商店＝註冊表）。細節見 `specs/050-openai-models-copilot/`。

### 階段 37：會員 IA 重排——凸顯「應用」（第一刀 ✅ rev 102 上線，2026-06-28）
- [x] 第一刀已完成（spec 051，PR #98；純前端、無後端/migration/套件）— **問題**：會員頂部導覽原為 **儀表板 / 金鑰 / 分配 / 用量 / 模型目錄 / 應用**——最實用、面向「我要拿來用」的**「應用」被排在最後**，躲在金鑰/分配等 plumbing 之後。與**原則 6 可達性**（能力要在使用者真正取用的當下、好找）+ 階段 34 自己定的「**應用為總站**」自相矛盾。心智模型：**應用＝結果**（在 VS Code/Cursor/直接 API 用 AI），**金鑰＝水管**（連線憑證）、**分配＝被准用什麼**（admin 給、會員多半只看）——水管不該排在結果前面。
  - **第一刀（已上線）＝純重排**：`MAIN_NAV` 改為 **儀表板 → 應用 → 模型目錄 → 分配 → 用量 → 金鑰**（應用提到第 2、發現性的「目錄」緊接其後、金鑰降到最後）；**標籤保持「應用」**（經維護者確認、不改字）、**路由不變**、桌機+手機同步（皆 map 單一 `MAIN_NAV` 來源，改一處兩面生效）。TDD：既有 nav 測試只斷言「存在」、不斷言「順序」→ 新增嚴格順序斷言（重排前先紅）。178 前端綠、零回歸。spec 051。
  - **後續另議**（不在第一刀）：① 標籤白話化——「應用」scent 是否足夠（出自**階段 34** 的設計取向「標籤要喊得出怎麼用、別只靠『應用』撐 scent」，屬 vision 取向、非 experience 教訓）；② apps-first 落地頁（評估與精簡儀表板的關係，階段 22）；③ 建金鑰捷徑更往「應用脈絡」收。
  - **明確守則**：**凸顯應用 ≠ 埋掉金鑰**——金鑰是真實憑證，troubleshooting / 多裝置輪替仍要找得到（降序但不隱藏、路由不變）。
  - 對應**原則 6 可達性**（最常用的入口最該被看見、降低非技術成員進入門檻）。風險：改 nav 順序要**連帶更新 nav 測試斷言**（呼應 experience「改 UI 顯示字串／結構要同步改測試，否則 Frontend CI 紅」）。

### 階段 38：Codex 安裝體驗硬化（既有登入殘留 + 桌面版 + 一鍵還原）✅（rev 103→104 上線，2026-06-29）
- [x] 已完成（spec 052 + 還原 small-change；PR #100 + 直推 main；無 migration、無套件；三平台真機驗收完成 2026-06-29）—— 讓「已經有 Codex 登入/設定」的使用者也能一鍵裝起來、且能一鍵切回。**問題**：殘留登入（ChatGPT 帳號）會搶優先權、舊 config 殘留會卡住連線、預裝/執行中的桌面版會蓋掉腳本寫入——裝了卻不能用（原則 6 反面）。
  - **安裝硬化（rev 103，spec 052）**：動 `~/.codex/{config.toml,auth.json}` 前**先帶時間戳備份**（fail-loud）；config.toml 由 merge 改**整檔覆寫**乾淨平台設定（消未知殘留、備份可還原）；`codex login` 前先 **`codex logout`**（清殘留登入優先權、用 Codex 自身 CLI 不手寫 JSON）；安裝卡 + 腳本**提醒先完全關閉 Codex 桌面版**（含 Windows 工作列常駐）。
  - **一鍵還原（rev 104，small change 直推 main）**：`/install/codex-restore.{sh,ps1}` 還原最近一次 `*.bak-<ts>`（還原前另存 `*.prerestore-<ts>`、無備份則 fail-loud）；安裝卡展開區提供還原一行指令。
  - **真機驗收（SC-006）完成**：既有 ChatGPT 登入 → 一鍵安裝**不清檔即連上本平台**、桌面版提醒可見、**還原可切回原設定**（維護者 2026-06-29 確認）。
  - 對應**原則 6 可達性**（既有使用者也能不靠工程師裝起來/切回）。教訓入 experience：寫共用設定前先備份 + 用工具自身 CLI 重設登入（別硬編格式）+ 長駐 GUI 會搶寫設定要提醒關閉；以及「直推 main 前要完整跑 CI 關卡（含前端 vitest/tsc、看真退出碼）」。細節見 `specs/052-codex-install-hardening/`。

### 階段 39：配額池設定移到前端（admin 可編輯 T／保底 + 建議值）（規劃中）
- [ ] 規劃 — **問題**：自適應配額池的總額 **T（`POOL_TOTAL_TOKENS_PER_MONTH`）與保底（`POOL_FLOOR_PER_ALLOCATION`）目前是 Helm／env 的 infra 設定**，要調就得工程師改 value 重部署；admin 也無從得知「該設多少」。但 T／保底本質是**業務/治理決策（配額類）**，不是 infra（body size／timeout 那種）——違反**原則 6 可達性**（admin 該能自助、不必靠工程師）。
  - **決策（維護者定）**：**T／保底直接移到前端讓 admin 設、不再用 Helm 設定**。
  - **做法**：
    - **DB 為單一真理**（原則 5）：把 T／保底搬進 DB 的 admin 設定（比照階段 13 通知設定 `notification_config` 的 singleton 模式），`apply_rebalance` 改讀 DB；**Helm value 退成 bootstrap 預設（DB 無值時才用）或移除**——**不留 Helm + UI 雙可改入口**（避免「顯示值≠執法值」drift，呼應白名單／body-size 教訓）。需 migration（新 config 表/欄；遷移時把現行 Helm 值帶入當初始值）。
    - **配額池監控頁加編輯表單**：設 T／保底，含驗證（**T ≥ 保底 × 池內成員數 N**、≥0、低於近月用量時警告會開始擋人）、顯示 N、註明「**下次再分配才生效**」（或提示按手動再分配）。
    - **同頁顯示「建議值 + 原因」**（資料用既有 `aggregate_usage` + 成員數）：近月用量、**建議 T ≈ 2× 近月**（留成長空間又封住總量上限）、**建議保底**讓零用量成員有可用基本額（否則上月沒用的人這月被卡到下次月初）、約束 T≥保底×N；可一鍵套用。
  - 對應**原則 6 可達性**（admin 自助調配額、不必 Helm／工程師）+ **原則 5 集中管理**（DB 單一真理、退 Helm 為 bootstrap）+ experience「配額類業務設定可見可編輯都該高」「同一 Helm 值同注確保顯示=執法、不 drift」。前例：階段 13 通知設定（DB singleton、admin UI 自助）。

> **不做：每日上限（Daily Cap）** — 曾於 2026-06-03 列為候選（源於外部回饋的延伸推導，
> 非核心需求），後評估認為現有「月配額 + 異常偵測器自動隔離 + 暫停機制」已足夠覆蓋「單一使用者
> 吃掉共享配額」的風險，每日粒度的硬上限非必要，故撤下不做。階段 13 通知系統當時預埋的
> `allocation_daily_cap_exceeded` event type 與 email 範本也一併移除（2026-06-03），未來若真需要再重建。

> **狀態**：階段 1–34、36、37（第一刀）、38 皆已上線（最新 rev 104；逐階段 rev / 細節見〈現狀〉與 `history/completed-phases-detail.md`）。近期：**階段 36 OpenAI 相容 `/v1/models` + Copilot 上卡**（模型發現端點 + Copilot 卡真機驗證；rev 98→101）+ **階段 37 會員 IA 重排凸顯「應用」第一刀**（純重排；rev 102）+ **階段 38 Codex 安裝體驗硬化**（既有登入殘留→logout+乾淨覆寫+備份、桌面版提醒、一鍵還原；rev 103→104，三平台真機驗收完成）。
> 規劃中：**階段 35 供應鏈／starlette+FastAPI major bump**（`.trivyignore` 暫掛兩個 starlette CVE，待 FastAPI 1.x 解鎖；非阻塞）+ **階段 39 配額池設定移到前端**（T／保底由 Helm 移到 admin 可編輯 + 建議值；DB 單一真理、退 Helm 為 bootstrap）+ **階段 37 後續**（標籤白話化、apps-first 落地頁——另議）。剩餘端點 video/vector_store 按需評估、多半 descope；image_edit/search 真分支待接非 Azure provider 才能實測。下一步見 `/knowie-next`。
> 已 descope：3b.7 Playwright E2E、每日上限（見上方各自的「不做」說明）。
