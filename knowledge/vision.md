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
- 配額除了月額度，可另設**每日上限**——課堂場景避免單一學生短時間爆衝燒光整月
  配額；與異常偵測器互補（後者抓「不正常爆衝」、前者抓「正常但用太多」）

## 現狀

平台已對組織開放使用（k8s 叢集，公開 MIT 倉庫）。詳細階段成果見下方〈路線圖〉與
`history/completed-phases-detail.md`。本檔〈核心想法〉與〈架構〉段反映平台現行設計；
本段只記「跑在哪、目前未完成的是什麼」。

未完成：**3b.7 Playwright E2E**（獨立 test-infra，暫緩）。

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

### 階段 13：管理員突發狀況通知 ⏳（規劃中）
- [ ] 規劃中 — admin 在 web UI 設定 SMTP（Gmail App Password 即可，零外部服務），
  平台對重要 audit_events 主動寄信通知。第一版只做 Email channel；架構抽象為
  `Notifier` interface 讓 LINE Bot / Web Push 之後可平行加。

**動機**：目前 admin 只有開著 admin UI 才會看到 quarantined/paused 卡片；分配
被自動隔離、upstream 短時間大量失敗、憑證失效等事件**離線時無感**，等使用者
回報才知道。台灣學校環境下 Slack/Discord/Google Chat 都不友善，LINE Bot 設定
過重，**Email 是「最容易安裝」的選擇**（admin 用既有學校 email，server 端只
需 SMTP host/port/username/password 4 個 value）。

**成功標準**（待 spec）：
- admin UI 新 page `/admin/notifications`：SMTP 設定表單 + 收件人清單 + 「發測試信」
  即時驗證 + 最近 N 條通知歷史
- SMTP 帳密以 Fernet 加密落 DB（沿用既有 `PROVIDER_KEY_ENC_KEY` pattern）
- 事件源 = 既有 `audit_events`；用設定檔或預設值定義「值得 page」的事件型別清單
  + 去重視窗（同事件 N 分鐘內只寄一封，避免轟炸）
- 未設定 SMTP 時 = 通知停用、不擋部署、不擾現有流程
- 架構：`Notifier` interface + `EmailNotifier`，第二版 channel 可平行 add

**明確排除（第一版）**：
- ❌ Web Push / PWA notification（之後可加）
- ❌ LINE Messaging API（之後可加，但要處理 channel 註冊 + group invite 流程）
- ❌ Slack/Discord/Google Chat webhook（不符 TW 學校工作流）
- ❌ 自架 SMTP server（信幾乎進垃圾匣，IP 信譽維運非順手做的事）

### 階段 14：Admin 視覺化強化 ⏳（規劃中）
- [ ] 規劃中 — 在不破壞既有差異化（quarantine 警示、設定清單、系統資訊）前提下，
  讓首頁與用量頁的資訊密度與決策力提升一個檔次。沿用既有 `recharts`（可升級到
  shadcn charts wrapper），不導入新 lib。

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
- ❌ 導入新 chart lib（沿用 recharts；最多升級到 shadcn charts wrapper）

**設計原則**：
- 每張圖回答一個會驅動決策的問題；無此性質的圖一律砍
- 預設帶「vs 上週／上月」delta 比較
- 點圖元素能 click-through 到詳情頁，不要孤立圖
- hourly 重算為最低更新頻率，避免「美但 stale」

### 階段 15：Tag-based 群組成本 rollup ⏳（規劃中）
- [ ] 規劃中 — 沿用既有 `MemberTag` 系統，讓成本／用量可以按 tag 聚合
  （`class-101` / `project-x` 等），不新增 entity、不改 schema。對學校場景的
  「101 班這個月花了多少」「資訊社團這個月配額剩多少」這類問題，是目前
  admin 必須自己出 Excel 才能回答的 killer feature。

**動機**：使用者與外部回饋一致指出：學校／團隊推廣 AI 時，**「按班級／群組看用量」
比「按個別成員看用量」更接近 admin 真實心智**——預算是按班級給的、報告是
按專案寫的。目前 `/admin/usage` 只能切 member / allocation / model，admin 還
得自己把同一班的成員加總。

**成功標準**（待 spec）：
- 後端新增 `aggregate_usage_by_tag` 端點（或在既有 `aggregate_usage` 加
  `group_by=tag` 維度），回每個 tag 的 token / cost / call 數 + 區間
- `/admin/usage` 加 tag 視圖：tag 列表 + 各 tag 該月支出 + 點 tag 看該 tag 成員列表
- 首頁加「Top 5 tags by spend」卡片（與 Phase 14 的 Top 5 allocations 並列）
- Tag 詳情頁加「該 tag 成員列表 + 各自用量 + 加總」
- 成員可同時掛多 tag → 加總會雙重計算；UI 明確標示「by tag，可能重疊」

**明確排除**：
- ❌ Nested tags / tag hierarchy（複雜度爆炸，YAGNI）
- ❌ Cross-tag 比較圖（資料密度與決策力不對等）
- ❌ Per-tag quota（quota 仍以 allocation 為單位；tag 只做檢視聚合）

### 階段 16：每日上限（Daily Cap）⏳（規劃中）
- [ ] 規劃中 — 在現有月配額之外，可選地對 allocation 設定**每日 token 上限**，
  preflight 攔截當日已超出者並回 `rejected_daily_cap_exceeded`。給課堂場景一條
  「下節課還能用」的硬保護。

**動機**：目前單一學生在短時間爆衝會在當天就燒光整月配額，後面 29 天該分配
就完全不能用。anomaly detector 抓的是「相對基準爆衝」，daily cap 抓的是「絕對
數量過大」——兩者互補。課堂場景天然需求：「這節課 max 50K tokens，下節課重置」。

**成功標準**（待 spec）：
- `Allocation` 加 `daily_token_cap` 欄位（nullable，null = 無每日上限）
- preflight pipeline 加當日 usage 計算與比對；超出回新 outcome
  `rejected_daily_cap_exceeded` + 友善訊息
- 重置語意：UTC 00:00（或 org 可設定時區）；UI 明確標示「每日重置時間：HH:MM」
- admin 編輯 allocation 表單加欄位 + 即時提示「本日已用 X / 上限 Y」
- 成員 dashboard 該分配卡片加「今日用量進度條」與月配額並列
- 新 `AuditEventType.allocation_daily_cap_exceeded`（首次當日觸發即記，避免噪音）

**明確排除**：
- ❌ Hourly / minutely cap（過細，異常偵測器已覆蓋）
- ❌ Per-model daily cap（每分配每 model 矩陣，複雜度爆炸）
- ❌ Daily cap 自動升降（人工設定即可）

> **未完成項**：3b.7 Playwright E2E（獨立 test-infra，暫緩）、**階段 13 通知**、**階段 14 視覺化強化**、**階段 15 群組 rollup**、**階段 16 每日上限**（皆規劃中）。其餘階段均已完成並真機驗證。
