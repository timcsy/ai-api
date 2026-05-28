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

**2026-05-28：階段 9（成員自助用量總覽）完成。**
後端 375 tests + 前端 80 tests 全綠；upstream 用 `litellm` library form 支援
4 家 provider（Azure / OpenAI / Anthropic / Gemini）；admin UI 經階段 5.1 從
11 個入口整併為 6 個（journey-oriented）；階段 5.2 起新成員首次註冊可依 admin
規則自動貼 tag；階段 6 起被允許的成員可對 admin 開放的 model 自助領取憑證；
階段 7 起 admin 在 Model 區管理價目（point-in-time），會員/管理員的模型目錄與
分配詳情皆顯示現價；階段 8 起首位管理員可經 CLI / helm Job 自動佈建，bootstrap
token 退為 break-glass，正式環境帶預設/空 token 即拒絕啟動；階段 9 起成員在
儀表板看到自己的整體用量總覽（token / 估算花費 / 次數 + model 拆分 + 區間 +
分配配額），嚴格只看自己。ProviderCredential Fernet 加密落 DB，K8s Secret 提供
金鑰，pod 啟動時即驗證。3b.7 Playwright E2E 仍未開。

下一步：階段 10（使用體驗打磨）、3b.7（Playwright E2E）。

## 架構

- **底層**：自製 FastAPI gateway；上游接入採 `litellm`（library only，
  不啟用其 Proxy server form）作為多 provider 抽象層——library form 的
  CVE 集中度遠低於 Proxy form，且涵蓋 100+ provider 不必逐家自寫 adapter
- **Provider credential 儲存**：DB（Fernet 加密 at rest），加密金鑰由 K8s
  Secret 提供；建立時一次性顯示明文（同 allocation token 模式），事後僅
  顯示 fingerprint
- **路由**：`model_catalog.provider` 指明每個 model 走哪家；呼叫時依 model
  查 catalog → 取對應 `ProviderCredential` → 經 litellm 發送
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

> 已完成階段（1–8）只列標題、完成標記與「交付」一句；**細部成功標準 / 核心原則 /
> 明確排除已封存於 [`knowledge/history/completed-phases-detail.md`](history/completed-phases-detail.md)**。
> 規劃中 / 未完成的階段（3b.7、9、10）保留完整細節於下方。

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

### 階段 10：使用體驗打磨（成員端為主）⏳（規劃中）
- [ ] 待開

> **問題**：本機真實使用者實測（2026-05-27）走通後，盤點出數處摩擦——端點顯示
> 不一致、資訊要逐張點開才看得到、新手缺引導、admin 局部用瀏覽器原生對話框。
> 多為把既有流程做得更直觀、資訊更易消化的打磨；另含一個小能力缺口：admin 想
> **臨時暫停一把憑證再恢復**（非用限額），目前無乾淨做法。
> **交付**：一批成員端為主的 UX 打磨 + 憑證暫停/恢復。
> **前置條件**：階段 6（自助領取）、階段 7（價目顯示）

**更直觀 / 正確：**
- [ ] **呼叫端點單一可信來源**：儀表板（`dashboard.tsx` 用 `window.location.origin`）
      與「如何呼叫」範例（`ApiUsageExample` 用 `gateway_base_url`）仍各自取值；統一為
      後端正規化的 gateway base URL。（dev `BASE_URL` :8000 → :47822 已先修，2026-05-28）
- [ ] **可自助領取卡片可點進模型詳情**（`dashboard.tsx`）：領取前能先看能力 / 價格 / 說明
- [ ] **首次登入極簡引導**：空狀態加「① 領取憑證 ② 複製 ③ 貼進 Authorization」三步，
      降低 LLM 新手門檻（呼應「讓不會寫程式的人也能用」）

**資訊更豐富 / 易消化：**
- [x] ~~**「我的分配」卡片帶用量**~~：本月已用 / 配額 + 進度條已於階段 9（PR #30）完成；
      尚缺卡面直接顯示**現價**（不必逐張點開）
- [ ] 卡片以 `display_name` 為主、slug 為輔（比照「可自助領取」卡片），不再只給技術 slug

**一致性 / polish：**
- [ ] **admin 調整配額改用 shadcn Dialog**（`admin/allocations.tsx` 現用原生
      `prompt()`/`confirm()`）：風格一致、可驗證輸入、可加單位提示
- [ ] token 提示文案補上自助情境（`dashboard.tsx` 現文案偏 admin 視角）

**新能力：憑證暫停 / 恢復（管理員）：**
> **動機**：admin 對無限額（或任何）憑證想「臨時關閉、過陣子再開」，而非用配額=0。
> 現有狀態只有 active / revoked（終局，且 rotate 會換新 token）/ quarantined（僅異常偵測器自動設），都湊不出「可逆、保留同一 token」的暫停。
- [ ] `AllocationStatus` 加 `paused`；proxy 將 `paused` 納入拒絕（回明確 `allocation_paused`，比照 revoked）
- [ ] `AllocationService` 加 `pause()` / `resume()`：**只切 status，不動 token、不建 reclaim lock**（與 revoke 的關鍵差異 = 可逆、保留憑證）
- [ ] admin UI（分配列 / 詳情）加「暫停 / 恢復」鈕；稽核 `allocation_paused` / `allocation_resumed`
- [ ] ⚠ 開工先確認 `status` 欄位儲存型別：Postgres native enum 需小 migration（`ALTER TYPE ... ADD VALUE`）；存字串則免

**明確排除（暫擬）：**
- ❌ 全面視覺改版 / 換 design system（只在既有 shadcn 內打磨）
- ❌ 成員端用量總覽（屬階段 9，不重複）
- ❌ 排程自動暫停 / 恢復（首版手動，未來可加）
