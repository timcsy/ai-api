# 經驗

> 跨 8 弧去重合併的蒸餾教訓——不是 changelog，而是會影響未來決策的**判準**。保持一頁可讀；
> 每條的完整因果軌跡放 `history/`、完整現場放 `episodes/`、早期工具坑放 `history/lessons-archive.md`。

## 教訓

### 採用外部工具前先確認「形態」並實測能力邊界；build-vs-adopt 以「領域第一公民是否同軸」判
- **理論說**：vision 寫「以 X 為核心」＝會享受 X 的完整形態；抽象層八成會 normalize 掉進階欄位。
- **實際發生**：001 research 決定用 LiteLLM **Proxy Server**、實作卻漂移成 library-only，多花工又揹依賴沒享
  好處（Phase 3b 才被使用者點破）。反之 Responses：plan 階段 `inspect.signature(litellm.aresponses)` 證實它
  已涵蓋完整介面，推翻「要自寫 raw pass-through」的臆測。realtime：litellm Proxy form 讓音訊繞過 gateway、
  失去歸戶與撤回 → 選 build 薄 relay。
- **教訓**：工具的**形態**（lib/service/framework）與**我們採哪個形態**要在 specify 前明確定；決策前用 5 分鐘
  `inspect.signature`/`print(回傳)` 驗能力邊界，別憑臆測論證自寫。功能重疊 ≠ 該 adopt——判準是「領域第一公民同
  不同軸」（litellm 是 key/user/team，我們是「分配 = member×model」）；對已兌現價值的核心，門檻再升一級。
- **來源**：`history/001-litellm形態從ProxyServer到library-only.md`、`concepts/功能重疊不等於該adopt判準是領域第一公民同不同軸.md`；Arc 1/4/5/6。

### 安全相關設定一律「啟動時 fail-fast」，誤觸範圍才是 0
- **理論說**：設定缺失或不安全，等到第一次用到才壞就好（惰性檢查）。
- **實際發生**：Fernet key 惰性化 → pod healthy、admin 第一次建 credential 才炸隱晦 500；allowlist 空、bootstrap
  token 為公開預設值都是同類定時炸彈。
- **教訓**：安全預設（金鑰、後門 token、allowlist、redirect 白名單）啟動時驗證並 fail-fast / fail-closed；
  「啟動就拒絕」比「用到才壞」CP 值高一個量級。沿用既有環境訊號（`COOKIE_SECURE`）判 production 比新增 `APP_ENV` 省心。
- **來源**：`services/crypto.py`、`main.py create_app()`；Arc 1/2。

### 「部署完成」的驗收要含「指定的人真能登入操作」，不只 pod healthy
- **實際發生**：使用者問「部署上去後管理員會是誰？」才發現全新 DB 無 admin、後台只吃 session、OIDC 註冊者一律
  非 admin → 部署完成卻沒人進得了後台。
- **教訓**：session-only 後台 + 不自動 seed 管理員的系統，首位 admin 佈建是部署一等公民（idempotent CLI +
  helm hook，排在 migrate 之後）。bootstrap token 退為 break-glass。
- **來源**：`history/004-bootstrap-admin-token從主要保護降為break-glass.md`；Arc 1。

### 串流端點的副作用要綁在「資料已到且連線仍在」的事件點，別放 `finally`
- **理論說**：計費/稽核放在 generator 的 `finally`，正常或斷線都會記到。
- **實際發生**：Codex/SDK 收到最後一個 event 後**立刻斷線** → Starlette 取消任務 → `finally` 在 `CancelledError`
  （Python 3.11 繼承 **`BaseException`**、`except Exception` 接不到）情境執行 → `await commit()` 被打斷 → 用量默默
  消失、連 log 都沒有。curl 讀到串流尾才關，所以「測得到、Codex 記不到」極難察覺。responses（Arc 4）與 chat
  completions（Arc 8）踩同款坑。
- **教訓**：收到 usage/`response.completed` 當下就用 **fresh session** 立即記帳（請求 session 在 StreamingResponse
  body 執行時已關）；`finally` 只留 best-effort 且 `except BaseException` 並 log。別假設上游 usage chunk 形狀
  （Azure/litellm 把 usage 掛在非空 choices chunk 上）；gateway 要能自己 include_usage 計費、又幫沒要的 client 過濾。
- **來源**：`proxy/responses.py`、`proxy/chat.py` `_record_fresh`；`concepts/串流的事後記帳要綁在收到usage那一刻.md`；Arc 4/8。

### 「後端有 API/欄位」≠「使用者用得到」——這是隱性債，會被使用者「靠工程師」掩蓋
- **實際發生**：unquarantine 端點早在、分配列卻無按鈕；access rules CRUD 全有卻無頁面；逐筆端點在、admin 前端沒接；
  `cost_usd` DB 有記卻沒序列化出去。使用者實際取得能力的成本是「找工程師/下 SQL」。
- **教訓**：每個 backend endpoint 在 PR 要回答「使用者怎麼觸發這件事」；答案是「靠 curl/SQL」就是 UI 缺位、
  列為**未完成**（原則 6）。可觀測性分「彙總層 vs 逐筆層」兩條線各自查；**DB 有記的欄位要確認有序列化出去**。
- **來源**：`frontend/src/routes/admin/*`、`api/records.py`；Arc 3/4/6/8。

### 新增/放寬一個欄位要追到「所有讀寫與顯示點」——grep 姊妹欄位/隱形耦合當 DoD
- **實際發生**：加 `cached_input_per_1k` 漏接 5 個前端頁 + 價目 API；config 從 env 搬 DB 漏改 `apply_rebalance`
  讀取點留平行真理；放寬 email → 帳號時，schema 驗證/字串切分/規則比對/UI 標籤全是把它當 email 的隱形耦合。
- **教訓**：欄位成本不在 schema，在「它要在多少地方被讀出來」。新增/放寬後立即 `grep` 既有姊妹欄位或所有把它
  當某型別用的地方，逐一決定要不要帶上；config 搬單一入口時**所有 sink 一次全改**，漏一個就是「顯示≠執法」的沉默 drift。
- **來源**：`services/pricing.py`、`auth/identifier.py`；Arc 4/7/8。

### dev SQLite / prod Postgres 的結構性差異會遮 bug——回歸守門要斷言結構、不能只跑值
- **實際發生**：tz-naive datetime、循環 FK（`create_all` topo sort 排不出）、額度欄 INT4 溢位、FK cascade 語意，
  **本機/CI 全綠、只有 Postgres 才炸**（SQLite 寬鬆：64-bit INTEGER、FK 排序寬鬆、未開 FK pragma）。
- **教訓**：凡「會破 21 億」的計數/額度欄預設 `BigInteger` 且**斷言欄位型別**；連帶刪除**服務層 ORM 顯式做**
  別靠 DB ondelete（可攜、可測、可插稽核）；循環 FK 加 `use_alter`；本機自檢用 `metadata.sorted_tables` 逼硬錯。
  改結構/列舉對映後**全套件重跑**（testcontainers Postgres 本機不重跑會漏）。
- **來源**：`history/lessons-archive.md`（tz-aware/循環 FK）、Arc 6 D6、Arc 8 D-BigInteger；Arc 1/4/6/8。

### 「可見性」與「可編輯性」要分開判——判準 = 改錯爆炸半徑 × 改動頻率
- **實際發生**：admin 想調 body size，做成可編輯 UI 有 chicken-and-egg（被擋的人去動擋自己的東西）+ reload 成本 +
  誤觸不對稱；但「完全不出現」又讓人撞到才知道上限。反之配額池 T/異常門檻本質是業務治理決策，該可編。
- **教訓**：infra 類（body size/timeout/replica/DB pool/cookie）改錯半徑大且低頻 → **UI 唯讀顯示、真理留 Helm**；
  業務治理類（access rules/tag/價目/**配額**/redirect 白名單）→ 搬 DB 單例讓 admin 自助編輯。用同一 Helm value
  同時注 nginx + backend env 確保「顯示值 = 執法值」。
- **來源**：`api/admin_system.py`、`concepts/env設定搬DB單例用lazy-seed保首次零行為變更.md`；Arc 4/7。

### 同一概念做兩份必 drift → 第一次就抽單一共用元件 / 單一真理
- **實際發生**：分配詳情與型錄詳情各做一套「如何呼叫」→ 標題/佔位符/去前綴 slug 全不一樣、一份還跑不動；
  混合 raw+litellm 雙路徑；「能不能測」與「怎麼測」兩處平行維護 → 靜默假成功「通過 0ms」。
- **教訓**：同一概念在兩處呈現/兩處判斷，第一次就抽共用元件（`ApiUsageExample`）或讓能力查詢**從執行定義衍生**
  （`is_testable(k) := k in RECIPES`）；複製出的兩份必 drift 並累積隱性 bug。呼應原則 5。
- **來源**：`components/api-usage-example.tsx`、`services/model_test.py`；Arc 3/5/6.

### 新增對外連線/新上游行為要真機/真 cluster/真上游才暴露——CI mock 全測不出來
- **實際發生**：SMTP 587 撞 NetworkPolicy egress（只放 443/5432/53）；`/v1/ocr` litellm 只認 `azure_ai/` 不認
  `azure/`（「壞 token→401」在進 litellm 前就被擋、遮住路由 bug）；nginx generic `/v1` 沒設 timeout → 60 秒 504；
  multipart `UploadFile` fastapi vs starlette `isinstance` False（mock 照單全收遮住型別契約）；混中文 shell `$VAR`
  接全形括號在 C locale 炸。
- **教訓**：任何新增對外連線（新 port/host/webhook）先問「egress 開了嗎」；端點驗收要「帶真憑證對真模型成功跑
  一次」（401 只證閘門在、不證閘門後路通）；**回的錯誤長什麼樣就能定位是哪一層**（nginx HTML ≠ 閘道 JSON，
  `server:` 標頭揭穿拓撲，別假設）；「我方塑形後交上游」的轉換要直接斷言塑形結果、不能只看 mock 回 200；
  本機測不出的類別（型別/溢位/locale/timeout）用**規則掃描當守門**。改前端 nginx = 重建前端 image。
- **來源**：`proxy/upstream.py`、`deploy/docker/*`、chart egress；Arc 4/5/6/8。

### 別 overload 既有欄位——新增狀態先問「這是哪條軸」
- **實際發生**：把 `responses`（gateway 端點可用性，軸③）從 litellm `mode` 推導、塞進「模型能力」（軸②，外部同步
  管轄）→ 同步一動就把 admin 設的 responses 洗掉、Codex 突然不能用（latent bug）。realtime 同理是能力軸非 mode。
- **教訓**：新增狀態先分辨軸（①原生 API 型態 ②模型能力 ③我們的端點可用性 ④客戶端工具）；把「我們的、可實測可
  覆寫」塞進「外部同步管轄」＝把易變核心綁到快變邊緣。三軸解耦，會變的能力做 runtime 實測 + admin 可覆寫。
- **來源**：`services/responses_support.py`、`concepts/模型資訊的三軸要正交不可overload一個欄位.md`；Arc 5/6。

### 相對/比例門檻需足量樣本才可信；證據不足退絕對門檻，別靠調鬆倍數
- **實際發生**：baseline 稀疏（某分配 3.65 次/hr）時比例規則荒謬——研習示範 103 次就觸發隔離、正常人吃 403。
- **教訓**：`baseline_total < baseline_min_calls` 時不套比例、改絕對量門檻（但真離譜仍照抓）；「平時判斷別那麼嚴」
  的正解是補統計脆弱點，不是無腦調鬆（會放過真濫用）。保護型自動化要給 admin 一個暫停旋鈕（含到期自動恢復），
  因硬天花板（配額）本就存在、暫停風險有界。
- **來源**：`services/anomaly.py`、`history/012-異常偵測從v1比例門檻到v2稀疏baseline退絕對.md`；Arc 7/8。

### gateway 轉發任意 client 參數給任意模型 → 反應式重試（drop / inject），別維護每模型參數表
- **實際發生**：補 chat 參數 passthrough 後，推理模型只吃 `temperature=1`（多餘要 drop）、diarization 缺
  `chunking_strategy`（缺的要 inject）——同一枚硬幣兩面。litellm `drop_params` 依賴內建模型表，對自訂 Azure
  deployment 名（任意別名）**無效**。
- **教訓**：真正 provider-agnostic 的作法是 catch 上游 400 → 從錯誤訊息 regex 出 param → drop/inject 該參數 →
  重試（每次一個、有界終止）；降級要保證不重複計費（只在成功後記帳、失敗路徑無 token 不寫 record）。
- **來源**：`proxy/chat.py`、`concepts/gateway轉發任意參數就要有drop和inject兩條降級路徑.md`；Arc 8。

### 流程：feature 級（新表+migration+auth+安全）動工前先走 speckit；auth 上 production 前停下 review
- **實際發生**：OAuth 在「做完」目標下直接做、被維護者抓到沒走 spec；補救＝回填 spec/plan/tasks（那份 spec 同時
  當 auth review 文件），並在 review gate 停下等核准才合併。使用者說「亂」時先分辨是哪種亂（概念/找不到/缺結構/
  流程），別預設要大改資料模型——帳號管理的痛其實是「一次撈全部一個個點」，通用解 = 篩選 × 全選 × 批次。
- **教訓**：小改可直接動工，但 feature 級與安全相關一律先走 speckit + review gate；本機品質關卡逐字對齊 CI
  （範圍含 `tests/`、ruff **與** mypy、前端 vitest 全套 + tsc，別讓 pipe 吃掉退出碼，直推 main 時加倍重要）。
- **來源**：`specs/057-*`、Arc 7/8 流程教訓。

## 關鍵延伸（主題觸發必讀）

| 觸發關鍵字 | MUST 讀 |
|---|---|
| litellm 形態 / build vs adopt / realtime | `history/001-litellm形態從ProxyServer到library-only.md` |
| 首位 admin / fail-fast / 部署驗收 | `history/004-bootstrap-admin-token從主要保護降為break-glass.md` |
| 串流計費 / CancelledError / usage chunk | `concepts/串流的事後記帳要綁在收到usage那一刻.md` |
| 早期工具坑（TS/Vitest/ESLint/tz/httpx） | `history/lessons-archive.md` |
| SQLite vs Postgres 差異 | `history/lessons-archive.md`、`history/006-*.md` |
| 三軸 / responses / overload | `concepts/模型資訊的三軸要正交不可overload一個欄位.md` |
| 反應式參數協商 | `concepts/gateway轉發任意參數就要有drop和inject兩條降級路徑.md` |
| 治理設定 / env→DB / 單一真理 | `concepts/env設定搬DB單例用lazy-seed保首次零行為變更.md` |
