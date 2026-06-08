# 經驗

> 較早期、與目前架構關聯較弱的工具坑（TS composite、Vitest 嵌套 Vite、ESLint no-undef、
> Alpine apk upgrade、httpx URL quote、SQLAlchemy 多分支 select）已移至
> [`history/lessons-archive.md`](history/lessons-archive.md)。

## 教訓

### React Query：兩個 query 共用 key 但回傳形狀不同 → 讀到別人的快取

- **理論說**：用資源名當 queryKey（如 `["me","allocations"]`）很直覺，反正都在打同一個端點。
- **實際發生**：dashboard 列表用 `useQuery(["me","allocations"])` 回**陣列**；分配詳情頁也用
  `["me","allocations"]` 但 queryFn 回**單筆**（`list.find(...)`）。從 dashboard 點進詳情時，
  React Query 認為 key 已有新鮮資料 → 詳情頁直接讀到快取的**陣列**，沒跑自己的 find。
  `alloc.resource_model` 變 undefined → 標題退回 ULID、curl 顯示 `<model-slug>` 佔位。
- **解決方式**：給語意/形狀不同的 query **不同的 key**——詳情頁改 `["me","allocation-detail", id]`，
  並在會變動它的 mutation（rotate）一併 invalidate。
- **教訓**：queryKey 是「快取身分證」，不是「端點名」。**回傳形狀不同 → key 必須不同**；
  同一端點的 list 與 detail 衍生視圖要各自獨立 key，否則會互相污染且難以察覺。
- **來源**：`frontend/src/routes/allocation-detail.tsx`，修正於 PR #19

### 同一概念的 UI 做兩份一定會 drift → 抽共用元件

- **理論說**：兩頁都要「怎麼呼叫 API」的範例，各自寫一份比較快。
- **實際發生**：分配詳情與型錄詳情各做一套——標題（如何使用 vs 使用範例）、分頁數（3 vs 4）、
  有無複製鈕、佔位符（`$YOUR_TOKEN` vs `$TOKEN`）全都不一樣，型錄那份還用了去前綴的 model
  （proxy 其實吃完整 slug）→ 範例跑不動。使用者一眼就覺得「兩邊很割裂」。
- **解決方式**：抽 `<ApiUsageExample model={slug}/>` 共用元件，兩頁都用；統一文案/分頁/佔位符，
  model 一律用完整 slug。各頁只保留真正該不同的部分。
- **教訓**：同一個概念在兩處呈現，第一次就抽共用元件——複製出來的兩份**必然**隨時間 drift，
  且會累積成「割裂感」與隱性 bug（如錯誤的 model 範例）。
- **來源**：`frontend/src/components/api-usage-example.tsx`，PR #18

### UI 錯誤封包 shape 不一致會默默吃掉全 app 的錯誤訊息

- **理論說**：前端 `api-client` 統一讀 `body.error.{code,message}` 就能顯示後端錯誤。
- **實際發生**：Phase 5.2 在規則頁送惡意 regex，後端正確回 422 + 具體訊息
  （`nested quantifier (ReDoS risk)`），但 UI 只跳「建立失敗」沒下文。追查發現
  兩種錯誤封包並存：proxy 回 `{error:{...}}`，但 FastAPI `HTTPException(detail=...)`
  包成 `{detail:{error:{...}}}`。api-client 只認前者，於是**所有走 HTTPException
  的 admin 錯誤訊息**都被降級成空的 `statusText`——不只規則頁，是全 app 潛伏已久的 bug。
- **解決方式**：api-client 改成 `body.error ?? body.detail?.error`，兩種 shape 都吃；
  一行修復讓全 app 的 admin 錯誤訊息恢復可讀。
- **教訓**：錯誤訊息的「封包形狀」要當成跨層契約。前後端若有兩種 error envelope，
  client 必須都解析；否則使用者只看到無資訊的通用錯誤，且這種 bug 潛伏很久
  （成功路徑不受影響，沒人發現）。新端點上線時順手驗一次「錯誤路徑」訊息真的有顯示。
- **來源**：`frontend/src/lib/api-client.ts`；Phase 5.2 PR #14

### 對稱加密金鑰要在 pod 啟動時就驗證，別等 runtime

- **理論說**：app 沒人呼叫加密路徑時，金鑰存不存在不影響運行；惰性檢查就好。
- **實際發生**：Phase 5 加 `ProviderCredential` 用 Fernet 加密 API key。一開始
  把 `get_fernet()` 設成 lazy；偵錯時很快發現問題——pod 看似 healthy，第一次
  admin 按「建立 credential」才炸 500，且訊息隱晦（`InvalidToken`）。
- **解決方式**：`create_app()` 內無條件呼叫 `get_fernet()`，缺 key 或格式錯
  立即 raise `CryptoConfigError`。K8s 偵測到 CrashLoopBackOff，event log
  顯示明確訊息「PROVIDER_KEY_ENC_KEY is not set」。Helm chart 用
  `required` 同步擋掉 deploy。tests 也補一份「缺 key → create_app 噴」的整合測試。
- **教訓**：對安全相關的設定，「啟動時就拒絕」比「等到第一次使用才壞」CP
  值高 10 倍——前者誤觸範圍是 0，後者可能造成資料半寫狀態或員工試半天搞不
  懂為何按下去就 500。同樣原則套用 K8s Secret、外部 KMS、TLS 憑證。
- **來源**：`src/ai_api/services/crypto.py` + `main.py` `create_app()` +
  `tests/integration/test_startup_crypto.py`

### Tag 設計：先用 distinct 推導，先別建 Tag 表

- **理論說**：M:N 關聯通常需要 Tag entity + MemberTag join table，把 tag
  metadata（color / description / created_at）放在 Tag 表。
- **實際發生**：Phase 5 一開始想建 Tag 表，後來盤點需求：admin 只想知道「這
  個 tag 有幾個 member」、「member 有哪些 tag」、「批次貼標」，**沒任何
  metadata 需求**。建 Tag 表多一個 entity，每次新 tag 要先 INSERT Tag 再
  INSERT MemberTag，加倍 race 條件。
- **解決方式**：只有 `MemberTag(member_id, tag, added_by, added_at)`；
  tag 名稱集合 = `SELECT DISTINCT tag FROM member_tags`。新增 tag = 直接
  INSERT MemberTag；刪除 tag = `DELETE WHERE tag = ?`。零 race。
- **教訓**：M:N 不一定要先建 entity——若一邊只是「字串集合」沒有 metadata，
  直接讓 join table 自己當 source of truth；需要 metadata 時再加 entity，
  也只是純 schema 增量。YAGNI 在 schema 設計階段很值得。
- **來源**：`src/ai_api/models/member_tag.py`、`services/member_tags.py`
  的 `list_distinct()`

### build vs adopt 評估要在 specify 之前做

- **理論說**：vision 寫「以 LiteLLM 為核心」就代表會用 LiteLLM。
- **實際發生**：Phase 1 一開始只用了 `litellm.acompletion()` 一個函式
  （library mode），自製了 FastAPI gateway、認證、配額、UI、計費 — 直到
  Phase 3b 收尾使用者才發現「我以為你在 LiteLLM 上加邏輯，沒想到是自幹
  並行版」。多花了大量工，且揹了 LiteLLM 依賴卻沒享受其好處。
- **解決方式**：在 spec / plan 階段就要明確分辨**LiteLLM 是「library」
  還是「Proxy service」**——前者只是函式呼叫，後者才提供 UI / 認證 / 配額
  / 計費。並要主動向 user 確認預設選擇，而不是隱性決定。Phase 011 先改用
  官方 `openai` SDK（Azure mode）直連、drop `litellm`；**Phase 5 因要支援
  多 provider（Azure / OpenAI / Anthropic / Gemini），又以 library form
  重新採用 `litellm`**（只呼叫 `acompletion`，不啟用 Proxy server）。
- **教訓**：vision 提到的工具，要先確認**它的形態**（lib vs service vs
  framework）和**我們打算用哪個形態**；任何「build vs adopt」決策必須
  在 specify 之前明確問 user，不要在 plan 階段才隱性決定。形態選對之後，
  「採用」與「自製」可以並存、也能隨需求進退（litellm 一進一出再進就是例子）。
- **來源**：`src/ai_api/proxy/upstream.py`（Phase 011 改 `AsyncAzureOpenAI`、
  Phase 5 又回 `litellm.acompletion` 以支援多 provider）；PR #11 / #12

### 在 async SQLAlchemy 中禁止 lazy-load

- **理論說**：SQLAlchemy 的關聯欄位 (`relationship`) 在用到時自動 lazy-load。
- **實際發生**：在 async handler 裡存取 `allocation.credential.token_prefix`
  噴出 `MissingGreenlet: greenlet_spawn has not been called`。lazy-load 會
  在屬性存取時偷偷做同步 IO，在 async 邊界無法執行。
- **解決方式**：所有會跨越 async 邊界的查詢，都用 `selectinload()` 顯式預載
  關聯；`get()` 改寫成 `select(...).options(selectinload(...))`。
- **教訓**：async ORM 沒有「自動 lazy-load」這回事 — 預載是規則，不是優化。
- **來源**：`src/ai_api/services/allocations.py` 的 `revoke()` / `lookup_by_token()`

### datetime 一律 tz-aware

- **理論說**：SQLAlchemy 的 `Mapped[datetime]` 預設行為跨資料庫相容。
- **實際發生**：本機 SQLite 跑得好好的，到 testcontainers Postgres 立刻炸：
  `can't subtract offset-naive and offset-aware datetimes`。Postgres 拒絕
  混用 naive 與 aware。
- **解決方式**：所有時間欄位 `mapped_column(DateTime(timezone=True), ...)`；
  Python 端一律 `datetime.now(UTC)`，不用 `datetime.utcnow()`。
- **教訓**：當開發與生產用不同資料庫後端時，「能跑」不等於「正確」；明確
  寫出時區語意是 DB-portability 的底線。
- **來源**：`src/ai_api/models/{allocation,credential,call_record}.py`

### 拒絕路徑必須在 raise 前綁定上下文

- **理論說**：例外捕捉時，附近的變數狀態足以重建情境。
- **實際發生**：撤回後再呼叫應該記為 `rejected_revoked` 並帶 `allocation_id`，
  但實際紀錄 `allocation_id=null` — 因為 `allocation` 變數在 `resolve_allocation()`
  raise HTTPException 前還沒被 assign，closure 仍指向 None。
- **解決方式**：把「查找」與「狀態檢驗」拆開：先 lookup_by_token 取得 allocation
  並 bind 到 closure，再判斷狀態並 raise。
- **教訓**：拒絕／錯誤路徑跟成功路徑一樣需要審計資訊；要先把 context bind
  好，再做會 raise 的檢查。
- **來源**：`src/ai_api/proxy/router.py` 的「3. Allocation」段

### 部署完成 ≠ 跑得起來：可登入的首位管理員是部署的一部分

- **理論說**：image 部署上去、migration 跑完、pod healthy，部署就完成了。
- **實際發生**：使用者問「部署上去後管理員會是誰？」一查才發現：全新 DB 沒有任何
  admin member，後台 UI 又只吃 session、從不送 bootstrap token（前端刻意如此），
  OIDC 自助註冊的新成員一律非 admin → **部署完成卻沒有任何人進得了後台**。唯一能
  動的是預設值為公開已知 `local-dev-admin-only` 的 bootstrap token，沒覆蓋還是後門。
- **解決方式**：補 `create_admin` CLI（idempotent）以 helm pre-upgrade hook Job 在
  migrate 之後佈建首位 admin（OIDC 預建，首次登入比對綁定）；把「正式環境帶預設/空
  token」做成啟動防呆，複用「對稱加密金鑰要在 pod 啟動時就驗證」那條的 fail-fast
  模式，並重用既有 `COOKIE_SECURE` 當 production 訊號（不新增 `APP_ENV`）。
- **教訓**：「部署成功」的驗收條件要包含「指定的人真的能登入並操作」，不只是 pod
  healthy。凡是「session-only 後台 + 不自動 seed 管理員」的系統，首位 admin 的佈建
  必須是部署流程的一等公民；安全相關預設值（金鑰、後門 token）一律啟動時 fail-fast，
  誤觸範圍才是 0。沿用既有環境訊號比新增旗標更省心（YAGNI）。
- **來源**：`src/ai_api/cli/create_admin.py` + `main.py` 啟動防呆 +
  `deploy/helm/ai-api/templates/bootstrap-admin-job.yaml` + `docs/deployment.md`，PR #26

### 採用前先驗證 SDK 的能力邊界，別憑印象決定「自寫 vs 套件」

- **理論說**：要支援 Codex 的 Responses API（加密 reasoning、store、完整 SSE 事件），
  litellm 這種抽象層八成會 normalize 掉進階欄位，所以「保險起見」要對 OpenAI/Azure 自寫
  raw pass-through，其他 provider 才走 litellm——一個混合雙路徑架構。
- **實際發生**：plan 階段實測 `inspect.signature(litellm.aresponses)`，發現它的參數已涵蓋
  完整 Responses 介面（`include`/`reasoning`/`store`/`previous_response_id`/`extra_headers`…）。
  「litellm 會閹割進階欄位」純屬臆測。混合雙路徑會憑空多一條 raw code path（正中「同一概念
  兩份必 drift」），且與既有 litellm 架構不一致。
- **解決方式**：統一走 `litellm.aresponses`——OpenAI/Azure 原生高保真、其他家自動橋接。
  把 raw pass-through 降為「真機驗證若發現失真才啟用」的 fallback，而非預設。spec 的
  Assumptions 與 plan R1 明文記錄此抉擇。
- **教訓**：呼應「build vs adopt 評估要在 specify 之前做」——但更進一步：決策前先用 5 分鐘
  `inspect.signature` / 讀 SDK 源碼**驗證**能力邊界，別用「抽象層大概會失真」的臆測去論證
  自寫。臆測導向的「保險」往往是 YAGNI 違反。真正的不確定（litellm 對 Codex 串流是否
  逐欄保真）用真機驗證收尾，不用預先自寫整條替代路徑。
- **來源**：`src/ai_api/proxy/{responses,upstream,preflight}.py`、`specs/021-responses-api/research.md` R1；階段 11

### proxy 存取政策要求「該 provider 有 active ProviderCredential」，env fallback 不算

- **理論說**：Azure 有 env key fallback（`AZURE_OPENAI_API_KEY`），所以 proxy 對 Azure 模型
  一定走得通；測試只要 seed catalog + allocation 即可打 `/v1/responses`。
- **實際發生**：`/v1/responses` 測試一直回 `model_forbidden`。追下去發現
  `ModelAccessService.is_accessible` 第一關是 `get_providers_with_active_credentials()`，
  它只查 `provider_credentials` 表、**不認 env fallback**。env key 能讓「upstream 呼叫」成功，
  卻不能讓「存取政策」放行。既有 `/chat/completions` 測試沒踩到，只因它們不 seed catalog
  → `model_row is None` → 整個存取檢查被跳過。
- **解決方式**：凡是需要 catalog row 的 proxy 測試（responses 因 capability gate 必須 seed
  catalog），一律也 seed 一筆該 provider 的 ProviderCredential（經 `/admin/providers`）。
- **教訓**：「能呼叫上游」≠「通過存取政策」——兩者的 credential 來源不同（env fallback vs
  DB ProviderCredential）。新增任何「先查 catalog 再做存取判斷」的端點時，測試的前置資料要
  同時備齊 catalog **與** provider credential，否則會被 `model_forbidden` 誤導去查錯方向。
- **來源**：`src/ai_api/services/model_access.py` `is_accessible`；`tests/contract/test_responses*.py`；階段 11

### 新增一個資料欄位，要追到「所有讀寫與顯示點」，不是只加 model

- **理論說**：加個 `cached_input_per_1k` 欄位 + 計費公式，功能就完成了。
- **實際發生**：欄位與 `calculate_cost` 都加了，但使用者「看不到也設不了」——漏接了
  admin 價目 API（建立/列表/歷史）、`current_price_map`（會員目錄/分配/儀表板的價格來源）、
  `load_prices` 批次匯入，以及**五個**前端顯示頁（目錄列表/詳情、儀表板卡片、分配詳情、
  管理員模型詳情）。靠使用者逐頁回報 + 一次完整 grep 盤點才補齊。
- **解決方式**：新增欄位後立即 `grep` 既有姊妹欄位（如 `input_per_1k`/`output_per_1k`）的
  **所有**出現點，逐一決定要不要帶上新欄位：序列化（多個端點）、彙總、CLI 匯入、每個前端
  type + 渲染。把「資料流的端到端清單」當成 DoD。
- **教訓**：欄位的成本不在 schema，而在「它要在多少地方被讀出來」。加欄位時先列出
  source（寫入）+ 所有 sink（API 序列化、彙總、匯入、各前端顯示），一次補完，否則會像這次
  分多輪擠牙膏。**`grep 既有同類欄位` 是找出所有 sink 最快的方法。**
- **來源**：`services/pricing.py` `current_price_map`、`api/usage.py`、`cli/load_prices.py`、
  `frontend` 多個 route；階段 11

### CSS grid 內要 `truncate`，該格必須 `min-w-0`

- **理論說**：給格子加 `truncate` 就會把過長文字截斷加省略號。
- **實際發生**：「最近呼叫」表用 `grid-cols-5` 等寬，但一條不可斷行的 request UUID 把該欄
  撐到比分配寬度還寬，`truncate` 也沒生效——結果「總 tokens」與「請求 ID」視覺上黏成一團。
- **解決方式**：grid/flex 子項預設 `min-width:auto`（不會縮過內容），要讓 `truncate` 作用必須
  加 `min-w-0`；並用比例欄寬（`grid-cols-[...fr]`）+ 欄間距，長 ID 加 `title` tooltip。
- **教訓**：`truncate`（`overflow:hidden`）在 grid/flex 子項裡幾乎都要搭配 `min-w-0` 才有效，
  這是排版「欄位互相擠爆」最常見的根因。
- **來源**：`frontend/src/routes/allocation-detail.tsx` 最近呼叫表；階段 11

### 把 admin 操作開放給 member：沿用同一 service + 嚴格擁有者檢查

- **理論說**：要讓使用者自助暫停/恢復憑證，得另寫一套 member 版的邏輯。
- **實際發生**：直接重用 Phase 019 的 `AllocationService.pause/resume`（admin 用的同一個），
  member 端點只多做一件事——`allocation.member_id == current_member.id` 的擁有者檢查（沿用
  既有 `/me/allocations/{id}/rotate-token` 的 404/403 模式），其餘狀態機/稽核全免重寫。
- **教訓**：把既有 admin 能力下放成 self-service，價值幾乎全在「授權邊界」（擁有者檢查）而非
  業務邏輯——服務層保持 actor-agnostic，端點層各自把關身分，就能一份邏輯兩種入口、不 drift。
- **來源**：`api/me.py` `/me/allocations/{id}/pause|resume`；`tests/contract/test_me_allocations.py`；階段 11

### 串流端點的「事後記帳」要在 client 還連著時做，別放 finally（CancelledError 是 BaseException）

- **理論說**：串流回應的計費/稽核放在 generator 的 `finally`，無論正常結束或 client 斷線都會記到。
- **實際發生**：Codex 收到 `response.completed` 事件後**立刻斷線**——Starlette 取消串流任務，
  `finally` 是在 `CancelledError` 情境下執行。`CancelledError` 在 Python 3.11 繼承自
  **`BaseException`**（不是 `Exception`），所以 `except Exception` 接不到；`finally` 內的
  `await session.commit()` 被取消中斷，那筆用量**默默消失、連 error log 都沒有**。curl 因為會
  讀到串流結尾才關連線，generator 正常 exhaust，所以「測得到、Codex 卻記不到」，極難察覺。
  （前一個坑是 request-scoped session 在 StreamingResponse body 執行時已關；那個修好後才浮現這個。）
- **解決方式**：在解析到 `response.completed`（client 必定還連著、還在收事件）的**當下就立刻**
  用 fresh session 記帳，不要拖到 `finally`；`finally` 只留作「串流在 completed 前被中斷」的
  best-effort 後援，且 `except BaseException`（含 CancelledError）並 log，不靜默吞掉。
- **教訓**：串流端點的副作用（計費/稽核/持久化）要綁在「資料已到且連線仍在」的那個事件點，
  不要綁在 generator 生命週期結尾——結尾很可能在 client 斷線的 cancellation 下執行，DB await 會被
  打斷。凡 `try/except` 想涵蓋「被取消也要善後」，記得 catch `BaseException` 而非 `Exception`。
- **來源**：`src/ai_api/proxy/responses.py` `event_gen` / `_record_fresh`；階段 11（Codex 真機才暴露）

### anomaly detector 必須對「by-design 爆量」的服務型分配豁免

- **理論說**：baseline + ratio 偵測能抓出真正異常的用量爆衝，覆蓋所有 active allocation 即可。
- **實際發生**：Phase 11 上線後，自己（admin）的分配在用 Codex 一個下午後就被自動 quarantine
  ——Codex 是 agent CLI，連續 tool-call 推進的尖峰流量原本就是 10× baseline 以上，這對 ratio
  detector 看起來就是異常。模型／規則沒錯，是「被偵測的對象」分布有兩類：給人用的 chat 憑證
  （爆量是真異常）和給 agent/服務用的（爆量是 by-design）。一視同仁就會誤殺。
- **解決方式**：`Allocation` 既有 `is_service_allocation` 旗標（Phase 3c 自適應配額池為
  rebalance 豁免用的），在 `detect_and_quarantine` 的 active query 直接加
  `is_service_allocation.is_(False)`；admin UI 用既有「切換服務型」操作切換。新增整合測試
  `test_service_allocation_is_exempt_from_quarantine` 把 baseline+spike 情境跑一遍，確認
  service 分配不會被隔離。
- **教訓**：自動化執法（quarantine、rate limit、deactivate）的覆蓋範圍要看「被治理對象的分布」，
  別假設一條規則適用所有 actor。給 agent/服務憑證一個「by-design 例外」旗標比動門檻好——
  門檻調寬會放掉真正的 chat 異常，旗標只放掉那一類。同類旗標（service flag）也可重用：
  Phase 3c 已用它豁免 rebalance，Phase 12 順手豁免 anomaly，**一個語意旗標多個治理用途**比
  個別新增 `exempt_from_anomaly`、`exempt_from_rebalance` 等專用旗標乾淨。
- **來源**：`src/ai_api/services/anomaly.py` `detect_and_quarantine`；
  `tests/integration/test_us4_anomaly_detector.py`；階段 12

### 白名單只在「沒有 admin」時生效，admin 進來後由 admin 管理機制接手

- **理論說**：白名單是穩定的 access control 機制，admin UI 提供新增/刪除頁面持續維護即可。
- **實際發生**：階段 2 設計時把白名單當「日常管理機制之一」與自動註冊規則、來源限制並列。
  Phase 11 上線後實測：(1) admin 在 `/admin/members` 新增的成員，OIDC 登入時被白名單擋
  （白名單漏放）—— admin 自己以為加完成員就 OK；(2) 學校老師回報「this account is not
  allowed」，根因是白名單機制與成員管理機制重疊、心智模型雙軌、靠 admin 兩邊同步維護不現實。
- **解決方式**：把白名單退為 **bootstrap-only**：`auth/policy.py::is_email_allowed` 改成
  「DB 有任何 admin → admin mode」「DB 無 admin → bootstrap mode」。admin mode 下白名單
  不生效（active member by email 即放行），日常存取改由「成員清單（admin 加的人或自動註冊
  進來的人）+ 自動註冊規則 + 來源限制」管。bootstrap mode 才查白名單，讓首位 admin 還能用
  helm Job + bootstrap email 進來。
- **教訓**：access control 機制若有兩條路徑能管同一件事（白名單 vs 成員清單），admin 必然
  忘了同步其中一條 → 使用者被無聲擋下。設計時就要回答「**誰是該機制的最終 source of truth**」，
  並讓其他機制要嘛 derive 自它、要嘛只在它不存在時生效。「bootstrap-only fallback」是把這個
  原則寫進程式碼的好模式——平時不在路徑上、不會 drift，緊急時還在。
- **來源**：`src/ai_api/auth/policy.py` `is_email_allowed`；`frontend/src/routes/admin/access.tsx`；階段 12

### backend 有 API 卻沒對應 UI = 隱性債，會被使用者「靠工程師」掩蓋

- **理論說**：backend endpoint 寫好、admin 透過 API/curl 操作即可；UI 慢點補沒關係。
- **實際發生**：Phase 12 才發現一連串「後端有、前端沒」的隱性債：
  - `POST /admin/allocations/{id}/unquarantine` 早就存在，但 quarantined 分配在分配列只是
    一個字串狀態、沒徽章也沒按鈕——admin 不會察覺可以恢復、得求工程師下 SQL
  - `/admin/access/rules`、`/admin/source-restrictions` CRUD endpoints 全有，但沒有任何
    admin 頁面操作它們——「不要 hard-code 我的網域」這類請求變成工程師要進 DB 加 row
  - 「服務型分配」的切換按鈕被當成普通操作放著，但其實是 Phase 12 推出後**就是** anti-anomaly
    永久豁免的入口——使用者不知道按下去意味著什麼
- **解決方式**：Phase 12 補上三個 UI 缺口（首頁 quarantine alert + 分配列徽章 + 解除操作；
  通用 `/admin/access` 頁；「切換服務型」操作加說明文案）。事後盤點：每個 backend endpoint
  在 PR 中都該回答「使用者怎麼觸發這件事」，如果答案是「靠 admin 打 curl」或「靠 SQL」，
  就是 UI 缺位、應列為「未完成」而非「後端 done」。
- **教訓**：admin endpoint 沒對應 UI 不是「待 polish」，是**功能未完成**——使用者實際取得
  該能力的成本是「找工程師」，等於這條能力對非工程師 admin 等於不存在。Phase boundary 的
  DoD 要包含「目標 actor 不需另一個 actor 協助即可完成」，否則就是把工程師當成 production
  dependency。同樣警訊：log 裡常見「admin 來問怎麼 X」，X 就是 UI 缺位的索引。
- **來源**：`frontend/src/routes/admin/{allocations,home,access}.tsx`；階段 12

### infra 上限類設定：admin UI **顯示**、不要 admin UI **可編輯**

- **理論說**：admin 抱怨「100MB 不夠 / 我想自己調」，就把 nginx `client_max_body_size`、
  proxy timeout、CORS origins 等通通做成 UI 表單，admin 想改就改。
- **實際發生**：使用者出現 413，調整完 Helm value 後問「這個能放進 admin UI 管嗎」。仔細推一下
  做成可編輯 UI 的成本：(1) 這條設定**在 backend 前面**（frontend nginx pod），admin UI 是 backend
  出的——「被擋住的人想去動擋自己的東西」chicken-and-egg；(2) nginx 改完要 reload／重啟 pod，
  admin UI 得有 K8s API 權限或一個 reloader sidecar，過大或過度工程；(3) 誤觸後果不對稱——
  admin 不小心輸 `1k`，下一個 request 包括他自己的下個動作都 413；(4) 一年動一次的東西
  蓋 CRUD + 驗證 + audit 不划算。但「**完全不出現在 UI**」也不對——使用者上傳前不知道上限是多少，
  撞到才知道。
- **解決方式**：把 Helm value（`requestBodyLimitMB`）當 single source of truth，**同時**注入
  frontend nginx (`CLIENT_MAX_BODY_SIZE` envsubst 進 `client_max_body_size`) 與 backend env
  (`REQUEST_BODY_LIMIT_MB` → settings → `/admin/system/info`)；admin 首頁加 read-only「系統資訊」
  卡片顯示這個值並標注「超過會在邊緣回 413」。**顯示而非編輯**：admin 知道機器能吃多大、能對使用者
  說「目前上限 100MB」、需要調再找維運改 Helm。
- **教訓**：admin UI 的功能集合不是「所有後端設定」的鏡像——「**可見性**」與「**可編輯性**」要分開
  判斷。infra 類設定（body size / timeout / replica / resource limit / DB pool / cookie 屬性）
  通常**可見性高、可編輯性低**：admin 需要知道現值才能與使用者溝通／除錯，但改動成本（reload、
  誤觸範圍、權限擴張）讓「config-as-code + read-only UI」幾乎總是優於「runtime mutable UI」。
  反之，業務類設定（access rules、tag、價目、配額）可見可編輯都該高。判準：**改錯的爆炸半徑**
  與**改動頻率**——半徑大且低頻 → read-only；半徑小或高頻 → 可編。
  附帶：用同一個 Helm value 同時注 nginx 與 backend env 確保「顯示值 = 執法值」不 drift，
  避免「UI 寫 100MB 但 nginx 還是 1MB」這種更糟的情況。
- **來源**：`deploy/helm/ai-api/values.yaml` `requestBodyLimitMB`；
  `src/ai_api/api/admin_system.py` `/admin/system/info`；
  `frontend/src/routes/admin/home.tsx` 系統資訊卡片；階段 12

### proxy 把上游錯誤透明 relay 給 client 之餘，自己也要 log——不然 debug 等於猜謎

- **理論說**：gateway 是 transparent proxy，上游發什麼事件就忠實 relay 給 client；client 自己會
  解讀 error，gateway 不需要插手。
- **實際發生**：使用者回報「stream disconnected before completion: `response.failed` event received」。
  訊息是 Codex 解析 SSE 後自己生的；gateway 沒留任何 log——只看得到 nginx access log 200 OK 與
  最後一個截斷的 SQL 參數（`'azure', 'gpt-5.4'`）。要回答「為什麼上游失敗」唯一線索就是「呼叫的
  model 是 gpt-5.4」，到底是 DeploymentNotFound、content filter、rate limit、capacity 全靠猜。
  admin 看不到 = admin 無法支援使用者。
- **解決方式**：在 `event_gen` 攔截 `response.failed`，把 `response.error.{code,message}` 提
  `logger.error` 並帶 model/provider/allocation 上下文；同步寫一筆 `CallRecord(outcome=upstream_error,
  error_message=...)`，讓使用者用量視圖也看得到這次失敗（而不是「該次呼叫像沒發生過」）。事件本身
  仍透明 relay，不影響 client 行為。
- **教訓**：**透明 relay 與本地觀測是兩件事**——前者是對 client 的承諾（協定正確性），後者是對
  維運的承諾（可診斷性）。proxy 對任何「終局事件」（completed / failed / cancelled / 任何
  protocol-level error）都該**至少 log 一行帶足夠上下文**並落一筆稽核 row，否則一旦上游出狀況，
  你只剩 client 的二手錯誤訊息。判準：「使用者問 admin 為什麼，admin 不打 upstream API 也能答嗎？」
  答不出來 → log 缺位。
  附帶：把上游錯誤分到既有 `outcome=upstream_error` 而不是新增 enum，沿用既有 usage view 的
  渲染路徑就能看到——**新事件類型優先映射到既有語意**比加 enum + 改 UI 簡單一輪。
- **來源**：`src/ai_api/proxy/responses.py` `event_gen` 對 `response.failed` 分支；階段 12

### fire-and-forget 副作用要配一個 drain()，否則整合測試無法 deterministic 驗證

- **理論說**：通知這種「不能阻塞主流程」的副作用，用 `asyncio.create_task` 丟出去就好，測試
  直接斷言結果。
- **實際發生**：`audit.record()` 觸發 `asyncio.create_task(notifier.notify(...))` fire-and-forget
  後立即 return；整合測試在 task 還沒跑完時就去查 `notification_record` / aiosmtpd 收件匣 → 查到空、
  flaky。`await asyncio.sleep(0.1)` 之類的「猜時間」既慢又不可靠（CI 慢機器照樣 race）。
- **解決方式**：在 hook 模組保留一個 module-level `set[Task]`（task 完成時自我 discard），並提供
  `drain_notifier_tasks()` test helper——`while pending: await gather(*snapshot)`（snapshot 因為
  drain 過程可能再生 task）。測試流程變成「觸發 → `await drain_notifier_tasks()` → 斷言」，完全
  deterministic、零 sleep。production 不呼叫 drain，task 自然背景完成。
- **教訓**：任何 fire-and-forget 副作用（通知、背景寫入、cache warm）要 testable，就得在「射出去」
  的同一個模組提供「等它落地」的 hook。別在測試裡 sleep 猜時間。pattern：module-level pending set
  + 自我 discard callback + drain helper。production 路徑不變、測試路徑可同步。
- **來源**：`src/ai_api/services/notifier_hook.py` `fire()` / `drain_notifier_tasks()`；
  `tests/integration/test_notification_hooks.py`；階段 13

### 採用 SDK 前先印一次真實回傳值——`aiosmtplib.send` 回 `(errors_dict, message)` 不是 `(code, dict)`

- **理論說**：SMTP send 成功回 250，所以 `aiosmtplib.send()` 大概回 `(code, per_recipient_errors)`。
- **實際發生**：照印象寫 `code, errors = await aiosmtplib.send(...)`，測試 `assert code == 250` 直接
  炸 `assert {} == 250`——實際回傳是 `(errors_dict, response_message_str)`：成功時 errors 是空 dict、
  response 是 `"OK"` 之類字串，**根本沒有 250 這個數字**（要靠 `errors == {}` 判斷成功）。
- **解決方式**：實作前先寫 3 行 script 真的呼叫一次、`print(type(result), repr(result))`，看清楚
  shape 再寫解析。本案最後用「`errors` 空 = 成功，非空 = 各 recipient 的 `(code, msg)`」。
- **教訓**：呼應「採用前先驗證 SDK 能力邊界」——但更基本：**連回傳值的 shape 都要先印一次**，不要
  靠「SMTP 應該回 250」的領域直覺去猜 library 的 Python 介面。一次 `print(repr(...))` 省下一輪
  red-herring 的 debug。
- **來源**：`src/ai_api/services/notifier_email.py` `_smtp_send`；階段 13

### 新增「需要對外連線」的功能，要同步檢查 NetworkPolicy egress——本機測不出來

- **理論說**：通知功能在本機 + CI 全綠（39 測試 + aiosmtpd 真握手），SMTP 邏輯正確就能上線。
- **實際發生**：部署到 live cluster，admin 按「發測試信」回 `test_failed_connect`——backend pod
  連不到 `smtp.gmail.com:587`。根因是 Phase 2.5 安全加固的 K8s NetworkPolicy egress 只放行
  443(HTTPS給provider) / 5432(PG) / 53(DNS)，**當初沒料到未來會需要 SMTP 587**。本機、CI、
  單元/整合測試**全都用 loopback 或 in-cluster，碰不到那條 egress 規則**，所以一路綠燈，只有真
  cluster 的 NetworkPolicy 才會擋。
- **解決方式**：在 chart 的 NetworkPolicy egress 加 587/465（values 可調 `smtpPorts`）；用
  `kubectl exec <pod> -- python3 -c "socket.create_connection(('smtp.gmail.com',587))"` 在 pod 內
  實測連線確認。
- **教訓**：任何新增「對外連線」的功能（SMTP、webhook、新 provider host、外部 API、新 port）都要
  問一句「**這條 egress 在 NetworkPolicy 開了嗎？**」——這類問題本機/CI 一定測不出來（測試環境沒有
  egress 限制），只有真 cluster 才暴露。呼應「加欄位要追到所有 sink」：**加對外功能要追到所有
  網路層約束**（NetworkPolicy egress、防火牆、proxy allowlist）。把它列進該功能的部署 checklist。
- **來源**：`deploy/helm/ai-api/templates/networkpolicy.yaml` `smtpPorts`；階段 13

### 遮罩/指紋值要基於「有辨識度的來源」——拿固定前綴的密文當 fingerprint 等於沒 fingerprint

- **理論說**：要在 UI 顯示「密碼已存」又不洩漏明文，取 Fernet 密文的前 4 + 後 4 bytes 當 fingerprint
  就好——密文看起來夠亂。
- **實際發生**：admin 存了不同密碼，UI 顯示的 fingerprint 開頭**永遠是 `67414141`**，看起來「跟我存的
  沒關係、每次都一樣」。根因：**每個 Fernet token 都固定以 `gAAAAA...` 開頭**（version byte 0x80 +
  timestamp 結構，base64 後固定前綴），所以密文前 4 bytes 對所有 token 都是 `67 41 41 41`（= "gAAA"
  的 hex）——零辨識度，根本無法用來核對「我存對了嗎」。
- **解決方式**：fingerprint 改成 `sha256(明文)[:12]`（沿用 `ProviderCredential.fingerprint` 同模式）：
  不同密碼 → 不同 fingerprint、同密碼 → 同 fingerprint（可核對），且不洩漏明文。singleton config
  在 `to_response` 時解密一次算，成本可忽略。UI 文案也從「目前儲存」改成「密碼指紋」+ 說明它是雜湊
  非密碼本身（admin 一開始誤以為會顯示密碼）。
- **教訓**：任何「遮罩/指紋/摘要」要顯示給人核對，必須**基於有辨識度且因輸入而異的來源**——通常是
  **明文的 hash**，不是「加密後的密文 bytes」。加密格式常有固定 header（Fernet `gAAAA`、JWT `eyJ`、
  PEM `-----BEGIN`），取其前綴當指紋會讓所有值看起來一樣。判準：「兩個不同輸入，這個遮罩值會不同嗎？」
  若否，這個遮罩沒有意義。附帶 UX：遮罩值要明確標示「這是指紋/雜湊，不是原值」，否則使用者會誤判。
- **來源**：`src/ai_api/services/notifications.py` `_password_fingerprint_from_plain`；階段 13

### 本機 SQLite 寬鬆、CI/prod Postgres 嚴格——互相 FK 循環只在 Postgres 炸

- **理論說**：39 個通知測試（含整合）本機全綠，schema 設計沒問題。
- **實際發生**：merge 到 main，CI 的 Postgres 整合測試**幾乎全 error**：`CircularDependencyError:
  Can't sort tables`。根因：`notification_dedup_bucket.primary_record_id` ↔ `notification_record.
  dedup_bucket_id` 互相 FK 形成循環，`metadata.create_all`/`drop_all` 需要 topological sort 排不出來。
  本機測試用 SQLite in-memory，**對 FK 排序寬鬆**（甚至預設不強制 FK），所以 create_all 過得去；
  Postgres 嚴格做 topological sort 才炸。「本機 SQLite 過 ≠ Postgres 過」又一例（前面已有 datetime
  tz-aware 那條同源）。
- **解決方式**：互相 FK 的其中一個加 `use_alter=True` + 明確 name，讓 SQLAlchemy 以獨立
  `ALTER TABLE ADD CONSTRAINT` 發出、打破建表時的循環。本機重現：`Base.metadata.sorted_tables`
  會噴 `SAWarning: ...unresolvable cycles`（用 `warnings.simplefilter('error')` 可逼成硬錯提早抓）。
- **教訓**：dev 與 prod 用不同 DB 後端時，**結構性約束（FK 排序、循環、enum、tz、JSON 欄）要用
  prod 後端驗一次**，別只信 SQLite 綠燈。互相 FK（mutual FK）是經典陷阱——SQLite 容忍、Postgres
  topological sort 直接拒。設計到「A 指 B、B 也指 A」時，當下就標 `use_alter=True`。本機快速自檢：
  `python -c "import warnings; warnings.simplefilter('error'); from ai_api.db import Base; import ai_api.models; Base.metadata.sorted_tables"`。
- **來源**：`src/ai_api/models/notification.py` `primary_record_id` `use_alter=True`；階段 13

### Tailwind `grid` 沒給 base `grid-cols-1` → 手機用「內容寬」欄，recharts/寬內容溢出畫面

- **理論說**：`grid gap-6 md:grid-cols-2` 在手機（< md）沒指定欄數，預設就是單欄、會自己填滿寬度。
- **實際發生**：階段 16 RWD 後，使用者回報用量頁的圖在手機「超出去」。根因：Tailwind `grid` 若**沒有
  base `grid-cols-*`**，CSS 預設 `grid-template-columns: none` → 隱式欄用 `auto`（**內容寬**）撐開；recharts
  `ResponsiveContainer width="100%"` 量到的是這個被內容撐大的欄寬，於是圖比 viewport 還寬、整頁水平溢出。
  `lg:grid-cols-2` 只在 ≥lg 生效，手機那段等於沒有欄定義。同類問題也潛伏在 catalog/dashboard 的卡片 grid。
- **解決方式**：一律補 base `grid-cols-1`——Tailwind 的 `grid-cols-1` 是 `repeat(1, minmax(0, 1fr))`，
  關鍵是 **`minmax(0, ...)` 允許欄縮到 0**（不被內容撐開），所以 `grid grid-cols-1 gap-6 md:grid-cols-2`
  手機就乖乖滿版單欄、不溢出。另給 recharts 的 wrapper 加 `w-full min-w-0`（ResponsiveContainer 在 grid/flex
  子項要能縮，父層必須允許 `min-width: 0`，呼應「grid/flex 子項要 truncate 必須 min-w-0」同源）。
- **教訓**：**`grid` 一定要寫 base 欄數**（`grid-cols-1`），不要只寫 `md:grid-cols-N` 就以為手機是單欄——
  沒 base 欄 = `auto` 內容寬欄 = 寬內容（圖表、寬表、長字串）會撐爆 viewport。判準：任何 `grid` class
  若 `grid-cols-*` 只出現在斷點前綴（`md:`/`lg:`）而無裸 `grid-cols-1`，就是這個坑。recharts 尤其明顯，
  因為它用量到的容器寬反推圖寬，形成「容器被內容撐大 → 圖更大」的放大迴圈。
- **來源**：`frontend/src/components/{admin-usage-charts,admin-home-charts,ui/chart}.tsx`、
  `routes/{catalog,dashboard}.tsx`；階段 16 收尾（手機真機才暴露）

### 改主鍵的 migration 要「建新表+複製+swap」；驗它的整合測試要 DROP SCHEMA 還原

- **理論說**：改一張表的主鍵，`op.alter_column` 之類就能搞定。測試 DB 平常用 `metadata.create_all`，跑得過就行。
- **實際發生**（階段 18，`Credential` 由 `allocation_id` PK 改獨立 `id` PK）：①SQLite **不能** in-place 改 PK，
  唯一可攜（SQLite + Postgres 同碼）的做法是「create 新表 → `bulk_insert` 搬舊資料（補新 `id`/`name`）→ drop 舊 →
  `rename_table`」。②要固化「migration 後既有 token 零回歸」必須驅動**真 alembic**（`command.upgrade(cfg, ...)`），
  但整合測試平常靠 `Base.metadata.create_all` 建 schema、根本不跑 migration → 得另寫一支 sync 測試：
  `DROP SCHEMA public CASCADE; CREATE SCHEMA public` 清乾淨 → `upgrade` 到前一版 → 用 raw SQL seed 舊式列
  （ORM 已是新 schema、欄位對不上）→ `upgrade head` → 斷言。③**這支測試結束一定要 finally 再 DROP SCHEMA**——
  否則 alembic 建出的具名約束（如 `fk_xxx`）會讓後續吃 `metadata.drop_all` 的 `app_client` 測試噴
  `constraint ... does not exist`（metadata 用自己的命名慣例去 drop，名字對不上）。alembic-built schema 與
  metadata-built schema **不能共用同一個 Postgres**而不清場。
- **教訓**：碰到改 PK / 重建表的 migration——(a) 一律 build-new-table + swap，別指望 in-place ALTER 可攜；
  (b) seed 舊資料用 raw SQL（ORM 反映的是 head schema，會跟舊欄位打架）；(c) 任何「自己跑 alembic」的整合測試
  要把 schema 當共享資源，跑前清、跑後也清（try/finally DROP SCHEMA），免得污染 metadata-based 測試。
- **來源**：`alembic/versions/0015_per_device_credentials.py`、`tests/integration/test_credential_migration.py`；階段 18

### 前置 client 自帶模型目錄時，gateway 的命名空間要能被它的 picker 看見

- **理論說**：我們的 model 用 `provider/slug` 命名（`azure/gpt-5.4`）區分多 provider，client（Codex）把 base_url
  指過來、填好 key 就能用——預設模型 pin 好就收工。
- **實際發生**（Windows 真機，階段 19 收尾）：三個接連的坑。①安裝腳本只寫 `model_provider` 沒寫 `model`
  → Codex 用**它自己內建的預設模型**（gpt-5.5），不是成員分配的 `azure/gpt-5.4`。②就算 pin 了 `azure/gpt-5.4`，
  Codex 的 `/model` 選單列的是**它內建 catalog 的 bare slug**（`gpt-5.4`、`gpt-5.5`…），**完全沒有** `azure/gpt-5.4`
  → 成員的模型不在選單、選不到、也切不回來；選單裡的 `gpt-5.4` 送出後又跟 `azure/gpt-5.4` 對不上 → mismatch。
  ③`/model` 是 client 本機切換，選的當下不連伺服器，無法「選到就擋」，只能下一個指令才報錯。
- **解決方式**：(a) device-flow 回傳代表模型、安裝腳本 pin 進 config；(b) **bare-slug alias**——proxy 對無前綴
  請求找「去前綴後在 scope 內唯一相符」的分配，且 provider/catalog/upstream 一律改用**分配的正規 slug**（不是請求原字串），
  litellm 仍收 `azure/gpt-5.4`；歧義（一把 key 同時有 `azure/X`+`openai/X`）就不 alias；pin 時也優先 bare slug（唯一才用），
  讓預設模型同時「能用」且「在 picker 可選」；(c) 擋不住的誤選改回**可操作的錯誤訊息**（點名 bare slug + 提示 /model）。
- **教訓**：當你的 gateway 前置一個**自帶模型目錄**的 client（Codex、未來其他 agent CLI），你的模型命名空間若和它的
  catalog slug 不一致，它的 picker 就看不到你的模型——光 pin 預設不夠。對策是**在 proxy 層做雙向對齊**（接受 client 的
  bare slug、對外仍用你的正規 slug），而**正規 slug／provider 前綴是 litellm 路由必需、不能為了好看拿掉**（它決定打哪家 API）。
  另記：client 端的本機切換（`/model`）伺服器管不到，凡「選的當下無法擋」的互動，退而求其次給清楚錯誤訊息。
- **來源**：`src/ai_api/proxy/preflight.py`（canonical_model 對齊）、`services/allocations.py` `resolve_scope_allocation`（alias）、
  `services/device_flow.py`（pin bare slug）、`src/ai_api/install/codex.{sh,ps1}.tmpl`；階段 19 收尾（Windows 真機暴露）

### UI 文案一致性：grep 抓不到獨立標籤、列舉值要過 label()、改字串要同步測試

- **理論說**：要把中英混雜的 UI 統一成繁中，grep 出夾雜英文的字串、逐一翻掉就好。
- **實際發生**（rev 71→73 用語一致性梳理）：分三輪才掃乾淨，每輪使用者都再截圖出漏網的。三個根因：
  ①**用「中文相鄰」當 grep 條件會漏掉沒有中文緊鄰的獨立英文標籤**——導覽列 `label: "Model"`、表頭 `<span>Model</span>`、
  頁面標題 `Catalog 管理`、`<Badge>active</Badge>`，這些前後沒中文，grep 一律抓不到。②**後端列舉/資料原始值直接 render**
  （`{m.cost_tier}`→medium、`{m.default_access}`→open、`{r.event_type}`→anomaly_detector_run、`{m.family}`→general）
  在畫面上就是裸英文，但在程式裡看不出來是「顯示字」。③改完 UI 字串後 **`frontend/src/__tests__` 仍斷言舊英文**
  （mobile-nav 的 SUBNAV、各空狀態文案），導致 **Frontend CI 紅**——而 Image build 是獨立 workflow、照樣綠照樣能 deploy，
  所以「畫面上線了但 CI 沒綠」很容易被忽略。
- **解決方式**：(a) 不靠「中文相鄰」grep，改**逐檔讀 JSX**（必要時派 subagent 逐檔掃）才抓得到獨立標籤；
  (b) **所有列舉/狀態值顯示一律過 label 函式**——集中一個 `frontend/src/lib/status-label.ts`（statusLabel/actorLabel/accessLabel/
  familyLabel/eventLabel）+ 既有 `catalog-labels.ts` 的 `facetLabel`/`facetHint`，未知值原樣回傳、原始值放 `title=` 備查；
  (c) 改顯示字串的同一個 PR 就更新對應測試斷言。
- **教訓**：i18n/文案一致性的盲點不是「夾在中文裡的英文」（那種好抓），而是**獨立英文標籤**與**後端列舉直出**——
  根治法是「**所有對人顯示的列舉/狀態都強制走 label()**」，把英文外洩變成「忘了加 label」這種編譯期就近可查的問題，
  而非散落各處的字串。呼應「加欄位要追到所有 sink」「backend 有 API 沒 UI = 未完成」（原則 6 可達性）：顯示層的
  source→sink 一樣要追全。附帶 CI 陷阱：**前端顯示字串改名要連帶改測試**，否則 Frontend CI 紅但 Image build 綠，
  紅燈會被「還是能 deploy」掩蓋。
- **來源**：`frontend/src/lib/status-label.ts`、`catalog-labels.ts`、`components/app-shell.tsx`、`src/__tests__/mobile-nav.test.tsx`
  等 ~27 檔；rev 71→73（2026-06-08，使用者逐輪截圖才掃乾淨）
