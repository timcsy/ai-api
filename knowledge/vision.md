# 願景

## 問題陳述

組織內目前沒有統一的 AI API 存取方式。想用 AI 的人各自申請、各自付費、各自管理 API key，
無法盤點用量、無法管控成本、也無法把資源安全地分享給其他團隊或讓「不會寫程式的同事」用到 AI。

## 核心想法

自製 OpenAI 相容的組織內 AI API gateway，作為**單一分流入口**：

- **多 provider**：Azure OpenAI、OpenAI cloud、Anthropic、Gemini 等統一以 OpenAI 相容介面對成員開放；
  後續可加 self-hosted（Ollama / vLLM）。
- **Provider credential 由 admin 在 UI 管理**：API key 加密落 DB（Fernet），可新增/rotate/停用/稽核。
- **動態 catalog 可見性**：成員只看得到 admin 已加 key 且授權給自己的 model（credential gate ∩ access policy）。
- **存取規則以 Tag 為主**：admin 為 member 打 tag，每個 model 設允許/禁止 tag；改規則 = 改 tag。
- 開發者透過分配到的**應用金鑰**（一把可用一組 model）直接呼叫 API；每次依 request 的 model 歸戶到分配。
- **主流 agent 工具開箱即用**：以 OpenAI Responses API 對外，Codex 等把 base URL 指過來即可用；
  用量/成本統一歸戶。背後走多 provider 抽象（OpenAI/Azure 原生高保真、其他家自動橋接）。
- **多端點全開**：chat / responses / embedding / OCR / 圖片 / rerank / TTS / STT / moderation / search /
  image_edit / realtime——目錄能收 ⟺ gateway 服務得了（可達性）。
- 不會寫程式的成員透過外部「行政輔助服務」（以高額度豁免憑證呼叫本平台）間接享受 AI。
- 認證以彈性為本：Google Workspace SSO 最方便；本地登入可用帳號（非強制 email）；admin 可用成員清單、
  自動註冊規則、來源限制管控。**email 白名單僅在首位 admin 進來前作 bootstrap，之後不再生效。**
- 第一方網頁 app 可走 **OAuth（Authorization Code + PKCE）** 領長期金鑰（device flow 續留給 CLI）。
- 所有分配、用量、撤回在同一管理介面看得到；成員看得到自己的整體用量總覽 + 逐筆記錄。
- 平台提供**使用情境目錄**與**應用目錄**降低非技術者的進入門檻，並對突發狀況（自動隔離、upstream
  連續失敗、provider 憑證失效）主動 email 通知 admin（SMTP 由 admin 自助設定）。
- 成本/用量可按班級/群組/專案（tag）rollup。

## 現狀

平台已對組織開放使用。**階段 1–44 均已上線**，目前唯一部署在 **ccsh 叢集（`ai.ccsh.tn.edu.tw`），
helm rev 25**（tew 已於 2026-08-07 退役，舊敘述的 rev 數字是當時 tew 計數、已失效）。知識庫本身正在
**structureVersion 遷移中**（本次由 `/knowie-migrate` 從 git 全史重建 v2 canon）。

近期以 **spec 編號**追蹤：階段 41=spec 055（帳號登入）、42=spec 056（逐筆記錄）、43=spec 057
（第一方 OAuth）、44（成員/分配批次+篩選）；另有一批**無 spec 直接動工**的維護與部署硬化
（OCR 圖片 passthrough、chat/completions 串流、STT/diarize 修正、multipart、nginx `/v1` timeout、
Dockerfile frozen-deps 慢拉治本、tew→ccsh 遷移）。**階段 35 供應鏈**（starlette/FastAPI major bump）
仍規劃中——`.trivyignore` 暫掛兩個 starlette CVE，待 FastAPI 1.x 解鎖。逐階段細節見〈路線圖〉與
`history/completed-phases-detail.md`；因果轉移見 `history/NNN-*.md`；否決選項見 `history/tombstones.md`。

## 架構

- **底層**：自製 FastAPI gateway；上游經 `litellm`（**library only**，不啟用 Proxy server form——CVE
  集中度遠低、涵蓋 100+ provider 不必逐家寫 adapter）。所有 litellm 讀取集中在單一 adapter
  （`litellm_registry` / `proxy/upstream.py`）。**刻意例外**：`/v1/realtime` 直連供應商 WebSocket
  （直接依賴 `websockets`），不經 litellm——litellm 的 realtime 是 Proxy form / client 直連、音訊繞過
  gateway，會失去「歸戶到分配」與「即時撤回」（build-vs-adopt 以領域第一公民是否同軸判）。
- **端點層**：資料驅動 registry——`proxy/engine.py`（唯一執行流程）+ `endpoint_spec.py`（IOShape × Meter ×
  上游 call 三軸）+ `registry.py`（`EndpointSpec` 註冊表）；加同形態端點＝加一筆資料。串流端點（chat/
  responses）刻意不納入 registry（串流中記帳、形態不同）。
- **計費**：`PriceList`（append-only、point-in-time）是計費唯一真理；litellm `model_cost` 只當建議價/單位
  來源。`CallRecord`/`PriceList` 從 token 中心一般化為多單位（token/page/query/character/image/second），
  **NULL ⇒ token、token 路徑零回歸**；跨端點只以**花費（USD）**為共同分母。
- **Provider credential**：DB Fernet 加密 at rest，金鑰由 K8s Secret；建立時一次性顯示明文、事後只存指紋。
- **對外 API**：OpenAI 相容端點共用同一條前置 pipeline（憑證/分配/狀態/配額/model binding/存取政策/計費）；
  `/v1/responses` 統一經 `litellm.aresponses`（含 SSE streaming、tool calls、reasoning/cached 分項計費、
  `store`/`previous_response_id` 歸屬隔離 + TTL）；`GET /v1/models` 依金鑰 scope 回可呼叫模型。
  伺服器端記憶是 per-分配，續接不上時**明確吐錯不靜默降級**。反應式參數協商：轉發任意 client 參數給任意
  模型時，多餘的 drop、缺的 inject，靠上游 400 錯誤訊息重試（litellm `drop_params` 對自訂 Azure deployment
  名無效）。
- **認證**：Google Workspace SSO（OIDC 一律 email）+ 本地登入（可用帳號，未驗證識別碼）；成員清單為 access
  單一真理，白名單/自動註冊規則/來源限制為輔；異常偵測自動隔離可疑分配（service flag 豁免 by-design 爆量者，
  admin 可自助暫停）。第一方 OAuth（Auth Code + PKCE、無 client_secret、無 refresh、redirect 白名單 fail-closed）。
- **治理設定**：業務/治理設定（配額池 T/保底、異常門檻、OAuth redirect 白名單、通知）用 `CHECK id=1` DB 單例
  + env lazy-seed，admin 可自助編輯；infra 設定（body size/timeout）UI 唯讀顯示、真理留 Helm。
- **部署**：Kubernetes + Helm；Dockerfile 依賴層（from uv.lock）與專案碼層（`/app/src`）分離以穩定快取。
  相依以 Renovate 監看，異常可分鐘級回滾。
- **不在範圍**：行政輔助服務（獨立子專案，作平台的高額度使用者）；生產等級 K8s 叢集營運（組織 IT 負責）。

## 路線圖

> 已完成階段只列標題 + 完成標記 + 交付一句；細部成功標準/明確排除封存於
> [`history/completed-phases-detail.md`](history/completed-phases-detail.md)。日期為 git 完成日。

### 階段 1：分流核心可運作
- [x] 完成（2026-05-21）— 自製 gateway 可代理 Azure OpenAI、可發行可撤回的憑證。

### 階段 2：身份驗證與成員管理
- [x] 完成（2026-05-22）— 彈性身份驗證（Google SSO + Local password）；admin API 可分配憑證。

### 階段 2.5：安全加固（Hardening）
- [x] 完成（2026-05-22）— provider allowlist、K8s NetworkPolicy、CI Trivy、per-allocation quota + 異常警報、distroless、per-IP 登入鎖。

### 階段 2.6：供應鏈 / Scanner 加固
- [x] 完成（2026-05-22）— workflow SHA pinning、排程重掃自動開 issue、SBOM、lockfile fail-fast。

### 階段 3a：用量觀測與費用計算（後端）
- [x] 完成（2026-05-22）— 多維度用量切分、月度配額、point-in-time 計費、CSV/JSON 匯出。

### 階段 3b：管理員 Web UI
- [x] 完成（2026-05-24）— React 19 + Vite + shadcn/ui；member view + admin suite（5 視圖合併 PR，`Member.is_admin` 雙軌認證）。（3b.7 Playwright E2E descope，見 tombstones）

### 階段 3c：自適應配額池（馬太效應 + 能量守恆）
- [x] 完成（2026-05-22）— 每月自動再分配 quota（Σq=T 守恆），含保底、`quota_locked`、服務型豁免、`RebalanceLog`。

### 階段 4：模型目錄 + 多面向 Filter
- [x] 完成（2026-05-23）— 以「模型」為第一公民的目錄；多 facet filter + faceted counts；載入 idempotent 不刪未列模型。

### 階段 5：多 Provider + Credential 管理 + Tag-based 存取規則
- [x] 完成（2026-05-25）— 4 家 provider；admin UI 管理 provider key + 存取規則；可見性 = credential gate ∩ access policy；tag 批次授權。

### 階段 5.1：管理員 UX 整併
- [x] 完成（2026-05-25）— sub-nav 11 → 6 條（journey-oriented），舊連結 redirect 相容。

### 階段 5.2：規則自動標籤
- [x] 完成（2026-05-26）— admin 定有序規則，新成員首次註冊 first-match-wins 自動貼 tag（regex 防 ReDoS）。

### 階段 6：自助領取憑證
- [x] 完成（2026-05-26）— admin 逐 model 開放，被允許者一鍵領取；撤回後鎖定需 admin 解鎖。

### 階段 7：價目表管理 UI
- [x] 完成（2026-05-27）— admin 檢視/新增 append-only 價目版本；目錄/分配顯示現價，缺價目標「未定價」。

### 階段 8：部署強化 / 首位管理員 bootstrap
- [x] 完成（2026-05-27）— `create_admin` CLI（helm hook Job）+ 預設/空 token 啟動防呆；bootstrap token 退為 break-glass。

### 階段 9：成員自助用量總覽
- [x] 完成（2026-05-28）— `GET /me/usage`（summary + 拆分 + `has_unpriced`，嚴格本人隔離）+ 儀表板用量摘要。

### 階段 10：使用體驗打磨（成員端為主）
- [x] 完成（2026-05-28）— 分配卡片顯示 display_name/現價/已用；三步上手引導；呼叫端點單一來源；admin 可暫停/恢復憑證。

### 階段 11：Responses API / Agent 工具（Codex）相容
- [x] 完成（2026-05-29）— `/v1/responses` 全鏈（統一 litellm 路由、SSE、工具呼叫、reasoning/cached 分項計費、store/previous_response_id 歸屬隔離 + TTL）；Codex 真機驗證。

### 階段 12：存取設計重組 + 維運可視性
- [x] 完成（2026-05-30）— 白名單退為 bootstrap-only；anomaly 對 service allocation 豁免；quarantine 徽章/解除；系統資訊唯讀卡；專案公開化（MIT）。

### 階段 13：管理員突發狀況通知（Email）
- [x] 完成（2026-06-03）— admin 自助 SMTP + 收件人 + 發測試信；3 種 audit event fire-and-forget 寄信，5 分鐘窗去重。

### 階段 14：Admin 視覺化強化
- [x] 完成（2026-06-03）— 導入首個 charting 依賴 recharts（單一色盤）；首頁最多 3 圖（隔離警示之上）+ 用量頁 donut/heatmap + 統一時段選擇器。

### 階段 15：Tag-based 群組成本 rollup
- [x] 完成（2026-06-03）— `aggregate_usage` 加 `group_by="tag"`（刻意重疊）+ 下鑽端點；admin-only。

### 階段 16：行動裝置（手機）體驗強化（RWD）
- [x] 完成（2026-06-03）— header 漢堡/Sheet、全站 grid/flex-wrap/truncate、`.responsive-table` 單一機制；零新依賴。

### 階段 17：成員自助用量視覺化（成員端圖表）
- [x] 完成（2026-06-04）— 成員 dashboard 每日趨勢 bar + 各 model donut；範圍 100% 取自 session。

### 階段 18：憑證模型重構（每分配多 per-device 憑證）
- [x] 完成（2026-06-04）— `Credential` 由 1:1 改「獨立 id + allocation FK + 裝置名 + last_used_at」（migration 0015，1:N per-device）。

### 階段 19：成員一鍵安裝 Codex + device-flow（零參數、不脫鉤）
- [x] 完成（2026-06-08，三平台真機驗收）— 一行指令 + 瀏覽器授權 mint per-device 憑證灌進 Codex；device_authorizations（migration 0016）。

### 階段 20：scoped application credentials（credential ↔ allocation 多對多）
- [x] 完成（2026-06-05）— 憑證升為可命名應用 key，scope = 一組分配；CredentialAllocation join（migration 0017）；既有 token 零回歸（scope 只含一筆的特例）。

### 階段 21：憑證 UI 術語與層級收斂
- [x] 完成（2026-06-05）— 統一「應用金鑰」、單一管理處、可改名；分配詳情頁金鑰區降唯讀 + 顯示連坐範圍。

### 階段 22：會員介面分頁化 + 金鑰/分配概念釐清
- [x] 完成（2026-06-05）— 頂部導覽拆 金鑰/分配/用量；精簡儀表板 + 一句白話解釋。

### 階段 23：模型目錄 ↔ LiteLLM 登錄表對接
- [x] 完成（2026-06-08）— LiteLLM 當建議來源（來源標記 + 匯入快照，migration 0018）；PriceList 仍是計費真理、採納 = append。

### 階段 24：模型目錄 admin 體驗整合 + 充分利用 LiteLLM
- [x] 完成（2026-06-08）— 模型詳情頁為單一中樞（每欄來源徽章、檢查更新前移、退役硬編價格範本、唯讀原始面板）。

### 階段 25：responses 支援判斷（實測 + 手動雙來源）
- [x] 完成（2026-06-08）— 移除「從 mode 推導 responses」latent bug，三軸解耦；runtime 軟化事前閘門（唯一事前擋 = admin 手動 blocked）。

### 階段 26：admin 依模型種類一鍵測試模型
- [x] 完成（2026-06-08）— 依 model_kind 打對應最小真實呼叫；會計費種類確認後才打；只寫 audit 不寫成員 CallRecord。

### 階段 27：應用分頁（應用目錄）—— Codex 為第一個應用
- [x] 完成（2026-06-09）— 應用卡（相容分配數 + 一鍵設定 + 建金鑰捷徑預過濾）。

### 階段 28：應用商店化
- [x] 完成（2026-06-09）— tile 格狀 + 詳情頁 + 主畫面智能推薦（純前端）。

### 階段 29：多端點開放 + 計費一般化
- [x] 完成（2026-06-11）— embedding/OCR/圖片/rerank/TTS/STT 逐一開；計費一般化（migration 0019 純加欄，NULL⇒token 零回歸）。

### 階段 30：管理員成員管理批次化 + 刪除人體工學
- [x] 完成（2026-06-10）— 成員安全刪除（ORM 顯式連帶、孤兒用量保留）+ 批次刪除/預建。

### 階段 31：統一端點架構（資料驅動 registry）+ 全端點覆蓋
- [x] 完成（2026-06-11）— engine/endpoint_spec/registry 三件；遷移 5 端點測試零改；補 moderation/search/image_edit。

### 階段 32：即時字幕端點 `/v1/realtime`
- [x] 完成（2026-06-12）— 直連供應商 WS 薄 relay（不經 litellm）；按秒/分計費、旁路週期 re-check 撤回。

### 階段 33：成本制配額（跨端點統一額度上限）
- [x] 完成（2026-06-13）— 每分配每月 USD 花費上限（migration 0020 加 nullable 欄），與 token 上限並存取較嚴、不進池。

### 階段 34：「如何呼叫」可發現性重設計
- [x] 完成（2026-06-27）— 金鑰為入口、應用為總站、model 下拉填 slug；`ApiUsageExample` 單一共用元件。

### 階段 35：供應鏈 — starlette / FastAPI major bump（規劃中）
- [ ] 完成 — `.trivyignore` 暫掛兩個 starlette CVE，待 FastAPI 1.x 解鎖後再升。

### 階段 36：OpenAI 相容 `/v1/models` + Copilot 上卡
- [x] 完成（2026-06-28）— `GET /v1/models`（依金鑰 scope、id = 正規 slug 原樣可呼叫）+ Copilot 卡真機驗證 + 一鍵帶出設定。

### 階段 37：會員 IA 重排——凸顯「應用」（第一刀）
- [x] 完成（2026-06-28）— 導覽序 儀表板→應用→目錄→分配→用量→金鑰（純重排、路由不變、桌機+手機同步）。

### 階段 38：Codex 安裝體驗硬化
- [x] 完成（2026-06-29，三平台真機驗收）— 既有登入殘留 `codex logout` + config 整檔覆寫 + 動檔先備份 + 桌面版關閉提醒 + 一鍵還原。

### 階段 39：配額池設定移到前端
- [x] 完成（2026-06-29，三平台真機驗收）— T/保底由 Helm 搬到 DB 單例（migration 0021）+ admin 可編輯 + 近月用量建議值。

### 階段 40：異常偵測 v2
- [x] 完成（2026-07-02）— 稀疏 baseline 退絕對門檻；偵測設定搬 DB 單例（anomaly_config，migration 0022）；admin 可自助暫停/關閉自動隔離。

### 階段 41：本地登入允許以帳號（非 email）登入
- [x] 完成（2026-07-02）— email 在本地登入只是未驗證識別碼 → 放寬成自由帳號（重用 members.email 欄、零 migration）；只放寬 local、OIDC 一律 email。

### 階段 42：用量可觀測性 v2——逐筆記錄
- [x] 完成（2026-07-03）— 逐筆輸出補 cost_usd/quantity/unit（未定價⇒null）+ admin `GET /admin/records` + 共用 `<PerCallScatter>`；零 migration。

### 階段 43：第一方網頁 app 的 OAuth（Authorization Code + PKCE）
- [x] 完成（2026-08-25，ccsh 上線）— consent → code → token 換既有 Credential；first-party、無 secret/refresh；redirect 白名單改 admin 可編 DB 單例（lazy-seed，migration 0024/0025）。

### 階段 44：帳號管理批次 + 篩選（成員 + 分配）
- [x] 完成（2026-08-25，ccsh 上線）— 篩選 × 全選（篩選後集合）× 批次（per-item 獨立交易 + 逐筆 result）；成員與分配皆套；無 migration。

## 關鍵延伸（主題觸發必讀）

| 觸發關鍵字 | MUST 讀 |
|---|---|
| 憑證模型 / M:N 演進 | `history/006-憑證分配從1比N到MxN-scoped-application-credential.md`、`concepts/憑證是應用金鑰其單位是分配而非token.md` |
| 已完成階段細節 | `history/completed-phases-detail.md` |
| 被否決的選項 | `history/tombstones.md` |
| 計費 / 多單位 / 配額 | `concepts/花費USD是跨計量單位的唯一共同分母.md` |
| 端點架構 | `concepts/加一個同形態端點應該等於加一筆資料.md` |
| 治理設定 / env→DB | `concepts/env設定搬DB單例用lazy-seed保首次零行為變更.md` |
| 叢集 / rev 編號 | `history/014-叢集拓撲從tew雙叢集到ccsh唯一.md` |
