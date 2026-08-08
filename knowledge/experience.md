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

### 健康探測別把「最小測試參數」寫死——模型一變就過時（max_tokens / image size …）

- **理論說**：連通性／健康測試只要打一個極小回覆即可，`max_tokens=1`（或 16）省錢又快。
- **實際發生**（階段 26 真機）：admin 對 `azure/gpt-5.4` 按「測試模型」回紅字
  `litellm.BadRequestError: ... Could not finish the message because max_tokens or model output limit
  was reached. Please try again with higher max_tokens.`——模型其實**完全是通的**（auth/路由/deployment 全對），
  只是 gpt-5/o-series 是**推理模型**：推理 token 計入 completion 預算，極小的 cap 全被推理吃光、產不出任何輸出就撞上限，
  Azure 直接回 BadRequest。既有「測試連線」用 `max_tokens=16` 有**同一個 latent bug**（只是還沒人拿 gpt-5 測到）。
- **解決方式**：兩個健康探測的 cap 都調到 **2048**。一般（非推理）模型回「ping」很短就因 EOS 停下、**不會**真的吐 2048
  token，所以實際成本仍極小；推理模型有足夠空間跑完推理 + 短答。
- **教訓**：對「會推理」的模型（gpt-5、o1/o3/o4…）做任何**最小呼叫**（health probe、連通測試、warm-up）時，
  `max_tokens` 不能設成「我只要一點輸出」的小值——它是 **completion（含 reasoning）總預算**，太小會讓可用的模型
  誤報失敗。給一個「夠推理跑完」的寬上限（非推理模型不會真用到、成本不變），或別設 cap。判準：**這個 cap 是否
  含 reasoning？** 含 → 不能用「期望輸出長度」當值。附帶：BadRequest 說「raise max_tokens」其實證明模型可達，
  是「探測設定」而非「模型壞」。
  **更一般的版本（同根、原則 7 演進性）**：別把「最小測試參數」寫死——模型一變就過時。同類再現：圖片測試寫死
  `size="256x256"`，新模型（`gpt-image-2`）有「最低 pixel budget」直接回 `Invalid size … below minimum`。
  對策：**能不指定就用模型預設**（預設值對該模型必定有效），非用不可時給「夠寬、跨版本安全」的值，別用「我以為的最小」。
- **來源**：`src/ai_api/api/admin_catalog.py`（model test：max_tokens=2048、image 不指定 size）、
  `admin_providers.py`（test-connection）；階段 26（gpt-5.4 max_tokens、gpt-image-2 size 真機暴露）

### 連帶刪除要在服務層顯式做，別靠 DB ondelete——SQLite 測試環境不強制 FK

- **理論說**：FK 都標了 `ondelete`（CASCADE / SET NULL / RESTRICT），刪父 row 時子 row 自動連帶處理，靠 DB 就好。
- **實際發生**：階段 30「安全刪除成員」要刪分配（連帶把 `CallRecord.allocation_id` 設 NULL 保留用量史、cascade 憑證）。schema 的 ondelete 都齊全，但 `db.py` **沒設 `PRAGMA foreign_keys=ON`** → **SQLite（dev/CI）不強制** ondelete，Postgres（生產）卻會。若靠 DB cascade：contract 測試（SQLite）會「看似通過」但連帶根本沒發生，到生產才以不同行為炸開——正是「dev/prod 用不同 DB 後端時『能跑』≠『正確』」（見 datetime tz-aware 那條）的同類陷阱。
- **解決方式**：在 `MemberService.delete` 內以 **ORM 顯式**逐步處理整條連帶（`UPDATE call_records SET allocation_id=NULL` → 刪 credential_allocations → credentials → allocations → member），單一交易，**完全不依賴 DB ondelete**。並把這條的驗證寫成 **integration 測試（跑真 Postgres，FK 真強制）** 而非只在 SQLite contract 測，雙重保險。
- **教訓**：凡「刪一個東西要連帶處理子資料」的邏輯，**在服務層顯式寫出每一步**，別把正確性託付給 DB 的 ondelete——只要測試 DB 與生產 DB 的 FK 強制行為不同（SQLite 預設關、Postgres 開），靠 DB cascade 就會 dev/prod drift 且測試測不出來。顯式做＝可攜、可測、可在每步插稽核。需要驗 DB 端真實行為時，補一支 Postgres integration 測試。
- **來源**：`src/ai_api/services/members.py` `delete`；`tests/integration/test_member_safe_delete.py`；階段 30

### 本機品質關卡要逐字對齊 CI——`ruff check .`（含 tests/）**與** `uv run mypy src/ai_api`，別只檢 src 也別漏 mypy

- **理論說**：實作前 `ruff check src/ai_api` 綠（或只跑 pytest）就代表品質關卡過了。
- **實際發生**：三次同根：① 階段 29② 本機只檢 `src/ai_api`，但 CI `test` job 跑 **`ruff check .`**（整個 repo、含 `tests/`），測試檔註解一個 `×`（乘號）被 `RUF003` 擋下，CI 22 秒就紅、白等一輪。② **階段 36**（`/v1/models`）本機跑了 ruff + pytest 全綠就推，但 CI 還跑 **`uv run mypy src/ai_api`**——`proxy/models.py` 三個型別錯又吃一輪紅。③ **Codex 還原 script（直推 main）**：本機只跑了「單一卡測試檔 + `tsc | tail && echo OK`」就推，結果 **Frontend CI 連兩紅**——改文案的另一支卡測試斷言舊字（沒跑全套 vitest 漏掉）、新增的「複製」鈕讓 `getByRole("複製")` 變歧義、`getAllByRole(...)[0]` 的 `HTMLElement | undefined` 沒過 `tsc`。更慘的是 **`npx tsc --noEmit | tail -1 && echo "tsc OK"` 的 `&&` 綁的是 `tail` 的退出碼、不是 `tsc` 的**——pipe 把 tsc 的非零退出碼吃掉，我一度誤判 tsc 通過。
- **解決方式**：推之前把 CI 的**所有關卡逐字、完整跑一遍**——後端 `ruff check .` + `uv run mypy src/ai_api` + `pytest`；**前端 `npx vitest run`（全套、非單檔）+ `npx tsc --noEmit`**。檢查指令**用 `; echo $?` 看真正退出碼、別用 `cmd | tail && echo OK`**（pipe/`&&` 會遮蔽前段退出碼）。
- **教訓**：本機品質關卡的**範圍與指令要逐字對齊 CI**——路徑範圍（`.` vs `src`）、**有哪些關卡**（ruff／mypy／pytest／**前端 vitest＋tsc**）、且**跑全套非單檔**（改共用元件會波及別支測試）。**驗證指令本身別讓 pipe 吃掉退出碼**（`a | b && c` 的 `&&` 看的是 `b`）。**直推 main（小改、不開 PR）時這條加倍重要——沒有 PR 當關卡，假綠會直接讓 main 變紅**；所以直推前更要完整跑、看退出碼。做法：照 `.github/workflows/{ci,frontend}.yml` 列一份 pre-push 清單逐條跑。
- **來源**：CI `.github/workflows/` 的 `ruff check .` + `uv run mypy` + 前端 vitest/tsc；階段 29②（PR #77）、階段 36（PR #93 mypy 紅）、Codex 還原 script（直推 main、Frontend CI 連兩紅 + tsc 退出碼被 pipe 遮蔽，2026-06-29）

### 真實牌價會推翻「憑種類想當然」的計費假設——`inspect` litellm model_cost 再定 spec

- **理論說**：圖片生成模型「當然」是按張/按 pixel 計費，所以用圖片端點來證明「非 token 計費一般化」剛好。
- **實際發生**：spec 階段印了 litellm `model_cost`，發現本平台實際服務的 **Azure `gpt-image-1/2` 其實是 _token_ 計費**（`input_cost_per_token`/`output_cost_per_image_token`），dall-e-2 才 per-pixel、dall-e-3 才 per-image。用圖片端點根本不會觸發非 token 計費——證明不了一般化。改用 **OCR**（`azure_ai/mistral-document-ai` 的 `ocr_cost_per_page`，乾淨 per-page、JSON 進出無 binary）。同場也 `inspect` 確認 `OCRResponse.pages`（`len`＝頁數）才寫計量。
- **解決方式**：spec 前花 5 分鐘 `python -c "import litellm; print(litellm.model_cost[...])"` 把「這個模型實際用什麼單位計費 / 回傳長怎樣」印出來，再決定用哪個端點當證明消費者、計量欄取哪個。
- **教訓**：呼應「採用前先驗證能力邊界」「採用 SDK 前先印一次真實回傳值」——但更前置到 **spec 設計層**：別用「這類模型應該是 X 計費」的種類直覺去選證明對象與設計 schema。一次 `print(model_cost)` 就改寫了整個 spec 的端點選擇，省下做完才發現「圖片其實是 token、白做」的整輪工。
- **來源**：`specs/040-ocr-billing-units/research.md` R1/R3；階段 29②

### binary I/O 端點：輸出非串流就在 handler 內記帳、multipart 上傳要 `python-multipart`

- **理論說**：把 TTS（回音檔）/STT（收音檔）當成跟 chat/embedding 一樣的 JSON proxy，計費照舊放在共用流程。
- **實際發生**：階段 29③ 加 TTS/STT 才碰到兩個 binary 形態的現實：(1) `litellm.aspeech` 回 `HttpxBinaryResponseContent`（要讀 `.content` bytes、用 `Response(media_type="audio/mpeg")` 回，**不是 JSON**）；(2) FastAPI 的 `Form`/`UploadFile`（STT multipart 上傳）在 import/route 階段就 `RuntimeError: Form data requires "python-multipart"`——**該套件沒裝**。`litellm` 既有不代表 multipart 解析既有。
- **解決方式**：(1) TTS 音訊體積小 → **非串流**：一次讀 `.content`、在 handler 主體內就 `record_call`（不放 finally），client 必定還連著（避開階段 11 串流 CancelledError 坑）；錯誤路徑仍回 JSON。(2) 把 `python-multipart` 加進依賴（FastAPI 官方 optional dep，multipart 上傳沒它做不到）——這是個誠實的 Constitution Deviation，PR 明列理由。
- **教訓**：新增「非 JSON I/O」端點時，**形態本身就是新依賴面**：binary 輸出要選串流 vs 一次讀（小資料選後者、計費綁在資料到手點）；multipart 上傳要確認 `python-multipart` 在依賴裡。「litellm 函式既有 + 計費層既有」≠「整條 I/O 既有」——HTTP 層的輸入解析/輸出形態是另一軸，要各自驗一次（`inspect` 回傳型別 + 真的跑一次 route）。
- **來源**：`src/ai_api/proxy/audio.py`（TTS `Response` / STT `UploadFile`）、`pyproject.toml`（`python-multipart`）；階段 29③

### STT per-second 計量沒 duration 來源就別硬上——用 token 計費、per-second 延後

- **理論說**：whisper 類 STT 以「每秒音訊」計價（litellm `input_cost_per_second`），所以 STT 端點按音訊秒數計費。
- **實際發生**：`inspect` `litellm.TranscriptionResponse` → 只有 `text` + `usage`，**沒有 `duration` 欄**。要算秒數得自己解析上傳音檔的長度——mp3 需第三方音訊庫（stdlib `wave` 只認 WAV），違反「能不加套件就不加」。
- **解決方式**：STT 改走 **token 計費**（`usage` 有 token 就 `calculate_cost`，如 `azure/gpt-4o-transcribe`；whisper 類無 usage → cost 0），per-second **延後**（標記為「需音訊長度來源/新依賴」的後續）。spec 的 Assumptions 明寫此限制。
- **教訓**：呼應「採用前印真實回傳值」——計費單位的「數量來源」也要先驗證存不存在。回應沒帶你要的計量欄位時，**降級到回應真的有的單位**（token）+ 誠實標記原單位延後，比為了一個單位硬拉一個音訊庫進來划算。先別為「規格上該有的單位」付一個新依賴的代價。
- **來源**：`specs/041-multi-endpoint-complete/research.md` R4、`src/ai_api/proxy/audio.py` STT 計費；階段 29③

### 改 model_kind 的 mode→kind 對映後，要重跑全套件——admin model-test 有個「未知 mode」整合測試會撞

- **理論說**：給 `model_kind._MODE_TO_KIND` 加一個對映（如 `moderation→moderation`），只影響該類型的判定，跑相關單元測試即可。
- **實際發生**：階段 31 加了 moderation/search/image_edit 三個 mode→kind，本機跑 `test_model_kind.py`（單元）綠就推；但 CI 紅在 `tests/integration/test_admin_model_test.py::test_unknown_mode_unsupported`——它**拿某個「當時還未知」的 mode 當『unknown』的代表**來斷言「admin 測試按鈕對未知種類回 supported=False」。每次有 mode 從 unknown 變成 known，這個測試的代表就失效（階段 29③ 把 rerank 變 known 時改用 moderation，階段 31 又把 moderation 變 known）。而且它是 **integration（testcontainers Postgres）**，本機若沒在「加對映後」重跑完整 `pytest tests/` 就漏掉。
- **解決方式**：把該測試的代表換成「**目前仍未支援**」的 mode（video_generation / realtime / vector_store）。並記住：**改任何「列舉對映/分類」後，重跑完整 `pytest tests/`**（不只改動點附近的單元測試）——尤其有測試以「某個分類的反例」立論時。
- **教訓**：當一個測試以「X 是某類別的反例」立論（unknown mode、未支援能力、空集合…），它對「該類別的成員集合」有**隱性依賴**；每次擴張那個集合就可能讓反例失效。這類測試該用「結構上永遠在類別外」的代表（如註定不做的 mode），或改成不依賴特定成員。流程面：**動列舉/對映 → 全套件重跑**，別只跑改動點旁的測試（呼應「本機關卡範圍要對齊 CI」——這次是「測試廣度」沒對齊）。
- **來源**：`tests/integration/test_admin_model_test.py` `test_unknown_mode_unsupported`、`services/model_kind.py`；階段 29③→31（PR #79 第二輪紅）

### 「能不能測這個種類」與「實際怎麼測」必須同源——能力查詢從 recipe 表衍生，別另立常數

- **理論說**：`is_supported(kind)` 回「這個種類能不能自動測」用一個常數判斷（如 `kind not in {stt,unknown}`），測試 dispatch 另寫一個 `if/elif` 真打上游——兩邊各自維護就好。
- **實際發生**：admin「測試模型」對 OCR（及 rerank/search/moderation/image_edit）回「**通過 延遲 0 ms**」——根本沒打上游。根因:`is_supported` 定義是「不在 {stt,unknown}」（所以說 OCR 支援），但 dispatch 的 `if/elif` 只有 chat/embedding/tts/image 四個分支。階段 29②③ 把 ocr/rerank… 種類加進來後，`is_supported` 說「支援」、卻沒有對應分支會跑 → 呼叫**靜默 no-op** → 回傳「通過 0ms」的假綠。兩套東西 drift 了:一套說「能測」，另一套根本沒有對應的測法。
- **解決方式**:建 `services/model_test.py` 一張 `RECIPES` 表（kind → 怎麼測:最小真實呼叫 + billable 旗標）當**單一真理**;`is_testable`/`is_billable` 都從表**衍生**;`model_kind.is_supported/is_billable` 改委派給它;`admin_test_model` 改用 `recipe = RECIPES.get(kind); await recipe.call(common)` 取代 if/elif。沒 recipe 的 kind 自動「尚不支援自動測試」，**絕不假通過**。順手把 moderation/rerank 補成真測試（它們之前也假通過）。
- **教訓**：當「**能不能做 X**」（capability 查詢）與「**怎麼做 X**」（實際執行）由兩處各自維護，它們**一定會 drift**——而 drift 的失敗模式是最惡的「靜默假成功」（no-op 看起來像通過）。讓 capability 查詢**從執行的定義衍生**（`is_testable(k) := k in RECIPES`），兩者就**結構上不可能不一致**:加一個種類沒寫 recipe → 自動誠實回「不支援」，而不是假通過。資料驅動的「一張表 = 唯一真理」勝過「平行維護的兩個清單」。呼應 Principle 7 演進性:data-over-code。
- **來源**：`src/ai_api/services/model_test.py`（RECIPES）、`services/model_kind.py`（委派）、`api/admin_catalog.py`（recipe dispatch）;階段 31 後續修復（PR #82，rev 90）

### 新端點光「壞 token→401」不算驗過——provider 路由不符會潛伏到第一次真打

- **理論說**：新增 `/v1/ocr` 後,線上 smoke「壞 token→401」就代表端點上線可用了。
- **實際發生**：階段 29② 的 `/v1/ocr` 對 `azure/mistral-document-ai-2512` **從來沒能跑通**——litellm OCR 只支援 `azure_ai/`〔Azure AI Foundry〕、`mistral/`、`vertex_ai/`,**不支援 `azure/`**〔Azure OpenAI〕,會 raise `OCR is not supported for provider: azure`。但 catalog 把模型登記成 `azure/…`、`upstream_model` 就直接帶 `azure/` 前綴 → 每次 OCR 呼叫都被擋。這個 bug 潛伏了好幾個 rev,因為「壞 token→401」在**進到 litellm 之前**就被 auth 擋下回 401,根本沒觸發 provider 路由那段;直到 rev 91「測試模型」按鈕對它**真打一次**才浮現。
- **解決方式**：`upstream.aocr` 把 `azure/` → `azure_ai/` 重映〔同一 endpoint/key,Foundry 用 azure_ai 前綴可達〕——這是 `/v1/ocr` 端點與測試 recipe 的**唯一共同通道,一處改兩處修**。並學到:新增端點的線上驗證,「壞 token→401」只證明「路由有掛上、auth 有擋」,**證明不了「帶正確憑證真打會通」**——後者要對至少一個真模型真打一次〔或用 admin 測試按鈕〕,尤其牽涉 litellm provider 能力差異〔同一家雲的 `azure/` vs `azure_ai/` 支援的端點不同〕時。
- **教訓**：401 smoke 與「真打通過」是**兩個不同的保證**:前者測「閘門在不在」,後者測「閘門後面的路通不通」。只做前者會把「auth 正確擋下」誤當成「端點可用」。呼應「採用前先驗證能力邊界」——litellm 同一 provider 家族對不同端點〔chat/ocr/…〕的支援度不一致,`azure` 能 chat 不能 ocr,要用 `azure_ai`。**端點驗收清單該有一條:帶真憑證對一個真模型成功跑一次,不能只靠 401。** admin「測試模型」按鈕正是把這條變成隨手可做的動作——它揭露此 bug 就是它的價值證明。
- **來源**：`src/ai_api/proxy/upstream.py` `aocr` azure→azure_ai 重映、litellm `ocr/main.py` `get_provider_ocr_config`〔只認 azure_ai/mistral/vertex〕;階段 31 後續〔PR #84,rev 92〕,由 rev 91「補真分支」的 OCR 測試實打揭露

### 通用 gateway（LiteLLM Proxy）功能跟你重疊 ≠ 該改用它——判準是「領域第一公民同不同軸」

- **理論說**：LiteLLM Proxy 開箱就有 virtual key / budget / spend tracking / model access / rate limit / admin UI——功能清單跟我們自製 gateway 重疊一大半，那我們是不是在重造輪子、不如改用 Proxy form？（realtime 討論時被連續追問：為何不用 Proxy form？它真的做不到我們的分配管理嗎？）
- **實際發生**：誠實盤點後確認 LiteLLM Proxy **能做到主線**——發 key、限 model、限額度（連 `model_max_budget` per-key-per-model 都有）、看花費、撤回、user/team 階層。但有幾樣塞不進它的模型：額度綁「**分配**」且跨同一成員多把 key 共用、自適應配額池（Σq=T 守恆）、異常偵測自動隔離 + service flag 豁免、scoped credential 的**成員自助 attenuation**（成員只在自己已被授予的分配內打包 key）、面向非技術成員的自助 UX + 課堂 tag rollup。根因：LiteLLM 的歸戶**第一公民是 key / user / team**，我們是**「分配」(member × model)**——同一件事、不同世界觀。
- **解決方式**：build-vs-adopt **不以「功能清單重疊度」判，以「領域第一公民是否同軸」判**。同軸 → adopt（我們 library form 只呼叫 `acompletion`/`aresponses` 就是把 litellm 當邊緣 adapter）；不同軸 → 採用它等於要嘛放棄自己的領域模型、要嘛在它外面再套一層（雙核心、必 drift，違原則 5）。且對**已上線、已兌現價值**的系統，門檻再升一級：問題不是「它能不能做基本款」（通常能），而是「把已經服務了原則 6 + 配額池 + 課堂的這些，遷到它的 key/user/team 模型上重做，值不值」——幾乎都不值。
- **教訓**：現成通用工具功能與你高度重疊時，最危險的不是「它不行」，而是**誤把「功能重疊」當成「該 adopt」**。真正該問的是：你的價值核心建在哪個第一公民上？它的呢？**不同軸時，adopt 它＝換掉你實作原則的地基，省下的是管線、賠掉的是領域貼合**（本案：Proxy 省掉 realtime WS 管線，卻接不回「歸戶到分配」這個真正的核心工作）。這延伸「build vs adopt 評估要在 specify 之前做」——形態選定後，**遇到該形態的誘人場景（如 realtime 之於 Proxy form）時，回到第一公民判準，別被單一功能拉走**重評整個地基。呼應原則 5（單一管理路徑；雙核心並行必 drift）+ 原則 7（library form ＝核心穩定、邊緣快變、單一 adapter 隔開；Proxy form 會讓快變的 litellm 變成核心，方向反了）。
- **來源**：realtime 端點 build-vs-adopt 討論（2026-06-12，chat-only）；vision 階段 29 計費段「不採 litellm Proxy 的計費系統（不認得我們的『分配』模型）」、架構段「library only，不啟用 Proxy server form」；延伸自上方「build vs adopt 評估要在 specify 之前做」。

### realtime 轉錄是「能力軸」不是 litellm mode——別用 mode 推斷，讀 `supported_endpoints`

- **理論說**：模型走哪個端點看 litellm `mode`（chat/embedding/audio_transcription…），所以「realtime 即時轉錄」也該有個 `mode=realtime`，`model_kind` 照 mode 對映就好。
- **實際發生**（階段 32）：一開始把 `/v1/realtime` 的判定建在 `mode==realtime` 上。但實測 litellm（PR #29775）把 `gpt-realtime-whisper` 標 **`mode=audio_transcription`**（跟 `whisper-1` 同 mode！），realtime 能力是放在 **`supported_endpoints` 含 `/v1/realtime`**；整張 model_cost 唯一 `mode=realtime` 的只有兩個 Gemini live。照 mode 判 → 沒有任何 Azure 轉錄模型會被認成 realtime、端點閘門全擋。且 `whisper-1`（批次-only）與 `gpt-realtime-whisper`（可 realtime）**同 mode、不同端點能力**，光看 mode 根本分不出。
- **解決方式**：`model_kind` 改**能力優先**——`litellm_sync.raw.supported_endpoints` 含 `/v1/realtime`（或 admin 在能力欄標 `realtime`，`realtime:blocked` 強制關）→ `realtime`，否則才落 mode 對映。與階段 25 `responses_support`（responses 能力是獨立軸、非 mode）**同形狀**。
- **教訓**：「模型能走哪個端點」常被誤當成 mode 的同義詞，但 mode 是「原生 API 型態」（軸①）、端點能力是另一條軸（軸③，原則 7 守軸正交）。litellm 自己就把 realtime 轉錄能力放在 `supported_endpoints` 而非另開 mode——**採用一個外部分類前，先確認你要的語意它擺在哪個欄位**，別假設「具備 X 能力 ⟺ mode==X」。同 mode 可有不同端點能力（whisper-1 vs gpt-realtime-whisper）；凡「同類但能力有別」就是該獨立成軸、別 overload 既有欄位的訊號（呼應「把 responses 從 mode 推導」那個 latent bug 的同根教訓）。
- **來源**：`src/ai_api/services/model_kind.py` `_is_realtime_capable`；litellm PR BerriAI/litellm#29775（`gpt-realtime-whisper`：`mode=audio_transcription` + `supported_endpoints`）；階段 32

### 採上游「即時/WS 協定端點」前，用真憑證探測一次——並把 provider 的拒絕 body 帶出來當診斷

- **理論說**：照 litellm/官方文件的 URL 慣例組 Azure realtime WS URL（`/openai/realtime?api-version=…&deployment=<dep>`），CI 用 mock WS 跑綠就能上線。
- **實際發生**（階段 32）：部署後 admin 按「測試模型」回**裸 `HTTP 400`**。litellm/Azure 文件常見的 `deployment=<dep>` 慣例對 realtime **轉錄**不適用——帶 `deployment=` 會被 Azure 路由成**對話型** realtime session，轉錄模型不支援 → `400 OperationNotSupported「realtime operation does not work with the specified model」`；正解是 **`intent=transcription` 且不帶 `deployment=`**（模型由 client 的 `session.update` 指定），且 api-version 要 `2025-04-01-preview`（`2024-10-01-preview` 不行）。這些光看文件 / CI mock 全測不出來。**定位關鍵兩步**：① 在 `open_realtime_ws` 把握手拒絕的 **status + body** 帶出來（原本只看到裸 400，等於沒線索）；② 用真憑證在 backend pod 內 `kubectl exec` 直接探測各 URL 組合，Azure 的 error body 直接說明問題（連帶用 data-plane `GET /openai/deployments` 確認 deployment 真的存在）。
- **解決方式**：`_build_realtime_url` 去 `deployment=`、加 `intent=transcription`、版本 `2025-04-01-preview`（env `AZURE_REALTIME_API_VERSION` 可覆寫）；`open_realtime_ws` 捕捉握手拒絕、`raise RuntimeError(status+body)`；smoke 改純連線等首事件（連上即 `transcription_session.created`，不必送 session.update）。**部署後在新 pod 內跑實際 `realtime_smoke` 對真 Azure 回 `{'ok':True}` 才算驗收**。
- **教訓**：呼應「採用 SDK 前先印一次真實回傳值」「新端點光壞 token→401 不算驗過」——對**即時/串流/WebSocket 協定**再升一級：(a) 文件慣例（尤其跨 OpenAI↔Azure）常有端點別的細節差異（`deployment=` vs `intent=`、api-version 世代），**採用前用真憑證對真端點探測一次**，別只信文件；(b) 把 **provider 的拒絕 status+body 主動帶出**到錯誤訊息／日誌——裸 `HTTP 400` 無從下手，有 body 一次定位（這個診斷本身就是定位本 bug 的關鍵）；(c) WS/即時這類 CI 只能 mock 的邊界，真打驗證要排進部署煙霧——admin「測試模型」按鈕正是把它變成隨手可做的動作（它揭露此 bug 就是它的價值證明，同 `/v1/ocr` 那條）。
- **來源**：`src/ai_api/proxy/upstream.py` `_build_realtime_url` / `open_realtime_ws` / `_realtime_reject_detail` / `realtime_smoke`；階段 32（spec 044，rev 95；測試按鈕真打 + cluster 內探測揭露）

### 接不上的「續接請求」要明確拒絕，別靜默降級——無聲丟脈絡比報錯更糟

- **理論說**：Responses 的 `previous_response_id` 接不上時（過期、或被 per-allocation 隔離擋下），為了讓客戶端「換 model 不報錯」，乾脆**寬容降級**——丟掉那個 previous id、當新一輪重開，UX 看起來比較順。
- **實際發生**：VS Code GitHub Copilot 設 `apiType=responses`（走**伺服器端對話狀態** `store`+`previous_response_id`）。在**同一把金鑰下切換 model（＝切換分配）**續用同一對話 → 那個 `previous_response_id` 屬於舊分配 → 我們的 per-allocation 隔離回 `response_forbidden`；續用過期對話則回 `response_not_found`。一度想「寬容降級成新一輪」讓它不報錯。
- **解決方式（抉擇）**：**維持明確吐錯，不做靜默降級**。根因：server-state 把「記憶」外包給伺服器、客戶端沒留 transcript，所以降級**救不回 context**——結果是「使用者以為續接、model 卻失憶」的**靜默錯誤**，比一個可操作的明確錯誤更糟。明確錯誤讓邊界可見：使用者知道「換 model／過期 ＝ 開新對話」。對策是把**錯誤訊息做得可操作**（講清楚「請開新對話」），而非把錯誤藏起來。
- **教訓**：當一個「續接／還原／沿用既有狀態」的請求**無法被忠實履行**時，**寧可明確拒絕（fail loud）也不要靜默降級到一個「看起來成功、實際丟了東西」的狀態**。判準：降級後是否**無聲損失**使用者預期的資料／脈絡？是 → 該吐錯（呼應「靜默假成功是最惡失敗模式」recipe-table 假通過、原則 2 可追蹤性：跨分配不串味）。延伸架構觀：**伺服器端對話狀態是便利選項、有固有取捨**；可攜的正道是 **stateless**（客戶端持有並重播 context，如 Codex `store=false`、OpenRouter、Chat Completions）——順 UX 來自「客戶端自己記」，非伺服器。故我們對外**鼓勵 stateless**，server-state（store=true）支援但定位為便利選項，並老實標明「伺服器端對話記憶是 per-分配的，跨 model 帶脈絡得靠客戶端重播」。
- **來源**：`src/ai_api/proxy/responses.py` `resolve_for_continuation`（`response_not_found`／`response_forbidden`，維持拒絕）；GitHub Copilot `apiType=responses` 同金鑰跨分配切換實測（2026-06-27，chat 討論）；延伸自「能不能測 ⟺ 有沒有 recipe（靜默假成功）」與原則 2 可追蹤性。

### 寫給「第三方客戶端」的設定說明，要真機跑一次才算數——文件慣例會騙人

- **理論說**：要在 UI 卡片教使用者怎麼把某客戶端（GitHub Copilot、Continue…）指向本平台，照官方文件把欄位寫上去就好。
- **實際發生**（階段 36 Copilot 卡）：照 VS Code 官方文件寫「`url` 填模型的完整端點」，於是卡片教使用者填 `…/v1/chat/completions`。維護者真機一跑，**正確的是 `url` 只填 base `…/v1`**——Copilot 自己會依 `apiType`（`responses`/chat completions）把路徑接上去；填完整端點反而錯。連 config 的**結構**（頂層 provider 陣列 + 巢狀 `models`、`apiKey` 走 VS Code secret 參照）都跟臆想不同。文件對「url 是 base 還是完整端點」這種細節常含糊或過時。
- **解決方式**：把客戶端設定說明當成「**未驗證直到真機跑過**」——拿真帳號/真金鑰在該客戶端實際接一次、列模型 + 對話成功，再把**那份可用的設定**原樣搬進卡片（標「已在真機驗證」）。卡片只放驗證過的形狀；不確定的欄位寧可交給該客戶端的 wizard，不要自己臆測一個值寫死。
- **教訓**：呼應「採上游 WS 協定前用真憑證探測」「採用 SDK 前先印一次真實回傳值」——但對象是**我們寫給使用者的對外設定文案**：第三方客戶端的設定細節（base vs 完整端點、欄位名、config 結構）以**真機行為**為準，不以官方文件字面為準。判準：「這份設定我親手在該客戶端跑通過嗎？」沒有 → 標「待驗證」、別當成已驗證的步驟發出去（否則使用者照做卻處處紅字，正是階段 34 排除 Copilot 卡的原始顧慮）。附帶：能用「**幫使用者把設定產生好**」（如 Copilot 卡一鍵帶出 `models` 陣列）就別叫他手打——少一個出錯點。
- **來源**：`frontend/src/components/copilot-app-detail.tsx`（真機驗證後改 base `url` + provider 陣列結構 + 一鍵複製 `models`）；GitHub Copilot Custom Endpoint 真機（2026-06-28，維護者 VS Code 實測 `chatLanguageModels.json`）；rev 99→101。

### 安裝腳本改使用者本機的共用設定檔：先備份再覆寫、用工具自身 CLI 重設登入、提醒關閉長駐 GUI

- **理論說**：一鍵安裝把本平台的 provider 寫進 Codex `~/.codex/config.toml`、用 `codex login --with-api-key` 設好金鑰就好；merge-style 保留使用者原設定最不打擾。
- **實際發生**（階段 38）：對「已經有 Codex」的使用者三個坑：① 殘留登入（ChatGPT 帳號）**搶優先權**——只 `login` 不 `logout`，我們的金鑰沒勝出；② merge 保留的**舊 config 殘留**（未知鍵）卡住連線；③ 預裝且**執行中的桌面版**握著 `~/.codex`、退出時回寫，把腳本剛寫的設定**蓋掉**——使用者照做卻沒生效。blind（無法先探 Codex 內部）下，merge-保留反而是亂源。
- **解決方式**：(a) **動任何共用設定檔前先帶時間戳備份**（`*.bak-<ts>`，cp 失敗就 fail-loud 中止、不在沒備份下改檔），並提供**對稱的一鍵還原**把最近備份放回去（還原前也先存 `*.prerestore-<ts>`）；(b) config.toml 改**整檔覆寫成已知乾淨狀態**（blind 下繞過所有未知殘留，備份保可逆），而非 merge 保留；(c) 登入用**工具自身 CLI 重設**（`codex logout` 再 `codex login`），**別手寫它的 auth 檔格式**（跨版本會爛）；(d) 長駐 GUI（桌面版）共用同一份設定 → 腳本/卡**提醒先完全關閉**（含 Windows 工作列／系統匣常駐），`curl|sh` 無法中途暫停只能提醒。
- **教訓**：腳本去改「使用者本機、且可能被別的程式共用」的設定檔時——**備份是前置動作不是事後**（且要可一鍵還原）；blind 修復「未知殘留」用**重設到已知乾淨狀態 + 備份可逆**比「聰明地保留」穩；登入/憑證類**用該工具的 CLI 重設、別硬編檔案格式**（呼應「別硬編外部工具格式、用它的 CLI」）；**長駐 GUI 會與你的寫入競爭**，至少要提醒關閉（能偵測更好，但行程名跨版本脆弱、提醒先行）。判準：「這個設定檔有沒有可能被別的程式（GUI/另一個 session）同時握著或回寫？」有 → 備份 + 提醒關閉。
- **來源**：`src/ai_api/install/codex.{sh,ps1}.tmpl`（logout、整檔覆寫、備份、桌面版提醒）、`codex-restore.{sh,ps1}.tmpl`（一鍵還原）、`frontend/src/components/codex-install-card.tsx`；spec 052 + 還原 small-change；三平台真機驗收 2026-06-29（rev 103→104）。

### 把設定從 env 搬到 DB（admin 可編輯）：改「所有讀取點」指向單一入口 + 首讀 lazy-seed 保零行為變更

- **理論說**：要讓 admin 在 UI 改某個原本 env/Helm 的設定（如配額池 T／保底），建個 DB 表 + 一個 PUT 端點、讓 UI 寫它就好。
- **實際發生**（階段 39）：那個設定在後端常被**多處讀取**——T／保底同時被 `apply_rebalance`（執法）與 `GET /quota-pool/status`（顯示）讀。若只把 UI/顯示改讀 DB、漏掉執法那條（仍讀 env），就會「**顯示值 ≠ 實際執法值**」drift（admin 以為改了、rebalance 還用舊 env 值）——正是 body-size／白名單那條教訓的同形。另外冷啟動：DB 剛建表沒有列，若不處理會回 0／壞掉、或與現行 env 值不符（行為突變）。
- **解決方式**：(a) 建**單一讀取入口** `get_pool_config(db)`（get-or-create），把**所有**讀取點都改成呼叫它（grep 舊的 `settings.pool_*` 確認一個不剩）——DB 成為唯一真理；(b) 入口**首讀 lazy-seed 自現行 env**（無列時用 settings 值建列），讓搬家當下**零行為變更**，env 自此退為 bootstrap 預設；(c) 不保留「env 與 UI 都能改」的雙路（單一真理，原則 5）。
- **教訓**：搬「會被多處讀」的設定到 DB 時，**先列出所有讀取點（grep 舊來源）再一次全改指向單一入口**——漏一個就是「顯示≠執法」的沉默 drift（呼應「加欄要追到所有讀寫點」「顯示值=執法值不 drift」）。冷啟動用 **lazy-seed 自舊來源**保證搬家零行為變更，比 migration 內寫死預設更穩（migration 不易讀 env、且寫死值可能與現行 env 不符）。前例可抄：階段 13 `notification_config` 單例（`CHECK id=1`）。附帶踩坑：pyproject `per-file-ignores` 同一檔已有一條（`api/quota_pool.py=["N806"]`）時要**合併成 `["N806","RUF001"]`**，再加一行同 key 會 TOML duplicate-key 解析失敗。
- **來源**：`src/ai_api/services/quota_pool.py` `get_pool_config`（單一入口 + lazy-seed）、`api/quota_pool.py`（PUT + GET 改讀）、`models/pool_config.py`、migration 0021；spec 053、階段 39、rev 105（2026-06-29 真機驗收）。

### bookkeeping 寫入別掛在請求 session 上跨外部慢呼叫——共用熱列會鎖死所有併發、拖垮連線池

- **理論說**：在 proxy 流程裡更新「最後使用時間」這類 bookkeeping 欄位（`provider_credentials.last_used_at`、`credentials.last_used_at`）是小事，順手 `flush()` 在請求的 session 上就好。
- **實際發生**（ccsh 上線後人潮塞車，2026-06-29）：`get_next()` 把共用 provider 憑證的 `last_used_at` flush 在**請求 session** 上，於是那一列的 row lock 要等**請求結束**才釋放——而請求結束在**漫長的上游 Azure 呼叫之後**。全機關共用**同一把 Azure key** → 每個併發請求都 `UPDATE provider_credentials … WHERE id=<同一把>`，全部卡在同一列 row lock 上排隊、各自佔住一條 DB 連線等待 → SQLAlchemy 連線池打爆（`QueuePool limit of size 5 overflow 10 reached, connection timed out`）→ `/v1/responses` 500。實測 `pg_stat_activity`：50 條 active 卡死、最久一條 1004 秒、全是那句 UPDATE。CPU/記憶體全程很閒（12%）——**症狀像「算力不夠/連線太少」，根因其實是「鎖持有時間 × 共用熱列 × 併發」**。
- **誤判與彎路**：先當成容量問題——加 pod（2→5）、把連線池做成可調並加大（+`pool_pre_ping`）。這些**只是治標**（讓更多請求一起卡在同一把鎖），甚至更糟（更多連線去搶同一列）。`pg_terminate_backend` 清掉卡死交易能即時破結，但幾秒內又重新堆積——因為程式還是跨上游持鎖。
- **解決方式**：bookkeeping 更新改用**獨立短交易**（另開一個 session、寫完**立刻 commit**），鎖只持有毫秒、**絕不跨外部慢呼叫**；且**不要弄髒請求 session 上的 ORM 物件**（否則請求結束 commit 時又重發一次 UPDATE、把長鎖加回來）。一處（`get_next`）修好，四個 proxy 入口（chat/responses/router/realtime）全受惠。修復後連線 79→5、active 51→1、卡死 UPDATE 50→0、500 歸零。
- **教訓**：① 任何「請求生命週期內、上游慢呼叫之前」拿到的 row lock，預設它會被**持有到請求結束**（含整段上游時間）——bookkeeping/計數/`last_used_at` 這類**非交易核心**的寫入，要嘛獨立短交易立即 commit、要嘛 best-effort/節流，**別跟著請求 session 跨外部呼叫**。② 共用單一資源（一把 key、一個計數列）時，熱列 row lock 是隱形的全域序列化點——併發越高越致命。③ 診斷「塞車」先看 `pg_stat_activity` 的 `state=active` 數、`xact_start` 最久秒數、卡在哪句 query，**別先假設是 CPU/連線數**（node CPU 12% 卻在塞車，就是鎖/外部等待）。④ 既有的 app-key `last_used_at` 早就做了 >5min 節流（`services/allocations.py`），provider-cred 這條卻漏了——**同類 bookkeeping 要套用同一套防護**。
- **來源**：`src/ai_api/services/provider_credentials.py::get_next`（獨立短交易）+ `src/ai_api/db.py`/`config.py`（可調池 + `pool_pre_ping`）+ helm `database.poolSize/maxOverflow`；事故 2026-06-29、ccsh rev 3 / tew rev 106、鏡像 `sha-6da8b19`。

### 異常偵測要能被 admin 自助暫停，且稀疏 baseline 要退回絕對門檻（比例規則需足量樣本才可信）

- **理論說**：用「近1h ≥ baseline/hr × 倍數」抓爆量很直覺；門檻寫在 env、偵測器自動隔離即可。
- **實際發生**（研習誤隔離，2026-06〜07）：baseline 稀疏時比例規則的門檻低到荒謬——某分配 baseline 僅 3.65 次/hr，研習示範 103 次（10×=36.5）就被自動隔離、正常使用者吃 403。而且辦活動當下**管理員無法自助關閉**、只能找工程師改 env 或暫停排程（違反原則 6）。
- **誤判彎路**：一開始想「調高倍數」或「暫停 cronjob」。調倍數是無腦放寬（會放過真濫用）；暫停 cronjob 是工程師介入、非自助，且事後易忘了開回。
- **解決方式**（spec 054）：① **稀疏 baseline 退回絕對門檻**——baseline 樣本數 < `baseline_min_calls`（預設 200）時不套比例規則、只用絕對門檻；研習 103 次在絕對門檻（1萬）下不觸發，但真跑掉狂打上萬次照抓。② **設定搬 DB 單例**（比照 `pool_config`/`notification_config`，migration + `get_anomaly_config` lazy-seed）＝單一真理、admin 可自助改。③ **admin 可自助暫停/關閉**：偵測器讀 `effective_enforcing`（開關 AND 未在暫停期），不執法時照掃描/稽核但不隔離；`pause_until` 過期讀時判斷即自動恢復（不需背景任務），辦活動設「暫停到結束時間」不怕忘記關回。
- **教訓**：① **比例/相對門檻只有在 baseline 有足量樣本時才可信**——樣本不足要退回絕對門檻，別讓「除以小樣本」放大成脆弱門檻（剛遷移的新叢集、新分配、計畫性衝量全是稀疏 baseline 的常客）。② **保護型自動化（會擋人的）要給 admin 自助的暫停/關閉旋鈕**，且最好帶「到期自動恢復」——不是只能靠工程師（原則 6）。③ 「暫停」用讀時判斷 `pause_until > now` 比背景清理簡單且不會漏。④ 硬天花板（配額）已在時，第二層偵測「暫停」的風險有界，可以更放心地把控制權交給 admin。
- **來源**：`services/anomaly.py`（`get_anomaly_config` + 稀疏 baseline 分支 + `effective_enforcing` 略過）、`models/anomaly_config.py`、`api/anomaly.py`、migration 0022；spec 054、rev 107（ccsh rev 4 / tew rev 107，`sha-e1ea1c2`）。

### 「email」若只是未驗證識別碼，就別用 EmailStr 綁死——放寬成自由帳號可零 migration，但要追出所有把它當 email 的隱形耦合

- **理論說**：本地登入用 email 當帳號很自然，欄位叫 `email`、schema 用 `EmailStr` 驗證，天經地義。
- **實際發生**（spec 055）：使用者要「用帳號（非 email）登入」。一查才發現 **email 在本地登入根本沒被驗證**——系統從不寄信給成員（邀請是管理員手動交付的 token 連結、SMTP 只給 admin），email 只是個**未驗證的識別字串**。強制它是 email 格式毫無實質意義，純粹是 `EmailStr` 這個型別選擇留下的耦合。
- **解決方式**：識別碼**重用既有 `members.email` 欄**（唯一、String(320)、無格式約束）→ 值可為帳號或 email、**零 migration**。把 `EmailStr` 換成一個小的 `validate_identifier`（strip+lower、非空、無空白、長度上限；`@` 是否允許由業務決定，本案最終允許）。登入查詢/速率限制/稽核/session 全不動（只換識別碼型別）。
- **隱形耦合要追全**：`EmailStr` 不只在登入——還散在**建立成員 / 批次匯入 / email 白名單 / tag 規則測試**等多個 admin schema；自動 tag 更是 `email.partition("@")` 切 local/domain 來比對（網域/後綴 matcher 對「無 @ 的帳號」自然不命中、但**用 `partition` 不會 crash**）。放寬時要 grep 全部 `EmailStr` 使用點逐一決定（本案：只放寬 local 相關；OIDC 一律 email、其網域式自動註冊/白名單不動），並補一個 `identifier_regex` matcher 讓純帳號也能自動分組。
- **教訓**：① 型別即契約——`EmailStr` 這種「看似合理的嚴格驗證」會**悄悄把一個未驗證識別碼綁成 email**，需求一變才發現是自找的限制。先問「這個 email **真的**被當 email 用嗎（有寄信/驗證嗎）？」再決定要不要 `EmailStr`。② 放寬一個「身分/識別」欄位時，**grep 出所有把它當 email 的點**（schema 驗證、字串切分、規則比對、UI 標籤）逐一決定，別只改登入。③ 重用既有欄位（值語意放寬）常能**零 migration** 達成，比新增 `username` 欄+雙軌省事得多——但要接受「同一欄混裝兩種值」的語意債（本案可接受）。④ 用 `partition("@")` 而非 `split("@")[1]` 這類寫法，天然對非 email 輸入安全（不 crash，只是不命中）。
- **來源**：`src/ai_api/auth/identifier.py`（normalize/validate）、`api/auth.py`（登入放寬）、`api/admin_members.py`/`admin_tag_rules.py`（EmailStr→identifier）、`models/tag_rule.py` + `services/tag_rules.py`（`identifier_regex`）；spec 055、無 migration、ccsh rev 6 / tew rev 108、`sha-8a2444f`（2026-07-02）。

### shell 腳本裡 `$VAR` 後面直接接中文/全形字元一定要加大括號 `${VAR}`——否則某些 locale 會把非 ASCII 位元組吃進變數名、`set -u` 當場炸

- **理論說**：`say "已備份為 *.bak-$TS（在 $CODEX_HOME）。"` 看起來沒問題，`$TS` 前面剛設過、字串也用雙引號包好。三平台真機驗收也過了。
- **實際發生**（真機 macOS，2026-07-03）：使用者跑 `curl … | sh` 裝 Codex，噴 `sh: line 39: TS?: unbound variable`——即使 `set -eu` 下 `TS` 明明在前面設過。根因：`$TS` 後面**緊接全形括號 `（`**（U+FF08，UTF-8 三個位元組）。在使用者那台的 shell/locale 下，變數名解析把 `（` 的首位元組（0xEF）當成名字的一部分 → 讀成 `$TS\xef…` → 未定義 → `set -u` abort，**在寫入任何設定前就中止**。**跟「Codex 桌面版沒關」無關**（那行只是固定 echo）。
- **為什麼之前驗收沒踩到**：這是 **locale 相依**——UTF-8 locale 的 bash 會正確在 `S` 停住；C/POSIX 或某些 locale 的 shell 會貪婪地吃掉後續位元組。同一支腳本，A 機器好、B 機器炸。
- **解決方式**：把**所有「後面緊接非 ASCII 字元」的 `$VAR` 都改成 `${VAR}`**（大括號明確界定名字結尾）。用 `perl -CSD -pe 's/\$([A-Za-z_]\w*)(?=[^\x00-\x7F])/\${$1}/g'` 一次掃全檔。四支安裝腳本（sh + ps1）都要。並加**回歸測試**：斷言 render 後的腳本裡沒有「裸 `$VAR` 直接接非 ASCII 位元組」（`re.findall(r"\$[A-Za-z_]\w*[^\x00-\x7F]", body)` 應為空）。
- **教訓**：① 給非工程師跑的 shell 腳本、又混中文訊息時，**變數一律 `${VAR}`**——尤其緊接標點/中文處。這種 bug 只在特定 locale 現形，本機測不出來、要嘛真機、要嘛靜態掃描擋。② 「三平台驗收過」不等於「所有 locale 過」；locale/編碼類 bug 要用**規則掃描**當守門（呼應「本機測不出來的東西要用 CI/規則擋」）。③ 順帶：這次 image build 被 Trivy 擋下（joserfc 1.6.5 的 HS256 空 HMAC key CVE-2026-49852，transitive via authlib）——有 fix 的 auth 函式庫 CVE 就**升版**（`uv lock --upgrade-package joserfc` → 1.7.2）別 ignore。
- **來源**：`src/ai_api/install/codex.sh.tmpl`（+ .ps1 + restore 兩支）、`tests/contract/test_install_endpoint.py::test_no_unbraced_var_before_non_ascii`（回歸守門）、`uv.lock`（joserfc 1.7.2）；`sha-1a3462e`（ccsh rev 8 / tew rev 110、2026-07-03）。

### 逐筆可觀測性：後端資料/端點常已齊，缺的是「對外輸出補成本 + admin UI 頁 + 逐筆散點」——彙總圖看不出離群的單次呼叫

- **理論說**：已經有依 成員/分配/模型/日 的彙總圖 + 熱力圖 + CSV，用量可觀測性很完整了。
- **實際發生**（spec 056）：使用者問「管理員看得到每一筆 record 嗎？逐筆能成圖嗎？」一盤點才發現——**逐筆端點與資料早就有**（`/admin/allocations/{id}/calls`、`CallRecord` 有 `cost_usd`/`quantity`/`unit`），但：① admin **前端沒有頁面**接它（只能打 API）；② 逐筆對外輸出（`CallRecordOut`、`/me/.../calls`）**漏帶成本**（DB 有 cost_usd 卻沒序列化出去）；③ 所有圖都是**時間桶彙總**，沒有「每筆呼叫一個點」的散點——**離群的單次大呼叫在彙總圖裡被平均掉、看不出來**。
- **解決方式**：三刀都很小、**零 migration**——(a) `CallRecordOut` + `/me/.../calls` 補 `cost_usd`/`quantity`/`unit`（未定價⇒null，別當 0）；(b) 新 `GET /admin/records`（跨成員/分配 keyset 游標 + 篩選）+ 觀測頁「逐筆記錄」tab；(c) 共用 `<PerCallScatter>`（recharts `ScatterChart`，一點一呼叫、y=花費↔tokens），admin 與成員共用。
- **教訓**：① 盤點可觀測性時分「**彙總層 vs 逐筆層**」兩條線各自查——彙總完整不代表逐筆可達；「後端有端點」≠「使用者看得到」（同「backend 有 API 卻沒 UI = 隱性債」）。② **DB 有記的欄位要確認有沒有序列化出去**——`cost_usd` 存了卻沒進逐筆輸出，是常見的「記了但看不到」。③ **彙總會藏離群**——要抓「某一次異常大呼叫」需逐筆散點，不是日彙總。④ **未定價語意**：逐筆成本 None 要顯示「未定價」不可當 0（跨端點只有花費可比，但沒定價的不能亂補 0）。
- **流程再犯**：前端 CI 跑 `eslint .`，我本機只跑了 vitest/tsc/build **又漏了 eslint**（`no-explicit-any` 擋下）；且用 `;` 串接 tsc+git 導致 tsc 失敗仍 push 出一個壞 commit。**改前端一定本機先跑 `npx eslint .` + `tsc --noEmit`（用 `&&` 串、別用 `;`）再 push**（強化既有「本機關卡逐字對齊 CI」那條）。
- **來源**：`api/schemas.py::CallRecordOut`、`api/records.py::list_records`+`GET /admin/records`、`services/records.py::list_records`、`api/me.py`（calls 補成本）、`components/per-call-scatter.tsx`、`routes/admin/records.tsx`；spec 056、無 migration、ccsh rev 9 / tew rev 111、`sha-eb84520`（2026-07-03）。

### token 額度欄位要用 BigInteger——月配額可破 INT4（~21.4 億），Postgres 會溢位 500、SQLite 不會（本機測不出）

- **理論說**：月 token 額度用 `Integer` 存綽綽有餘。
- **實際發生**（2026-08-03）：admin 在模型的「自助領取」把預設月額度填 `10000000000`（100 億）→「更新失敗」。根因：`model_catalog.self_service_default_quota` 是 Postgres `INTEGER`（INT4，上限 2,147,483,647），100 億**溢位**→ `integer out of range` → 500。而且 `allocations.quota_tokens_per_month`、`pool_config.total_tokens_per_month` 也都是 INT4——就算模型設定存下了，之後自助**領取**把額度複製進 allocation 時一樣會溢位。**SQLite（本機/CI）的 INTEGER 是 64-bit，10e9 照存不誤**，所以單元/契約測試完全抓不到。
- **解決方式**：三個 token 額度欄位全改 `BigInteger`（migration 0023，**dialect-guarded**——SQLite 已是 64-bit 且不能 ALTER TYPE，直接 skip；Postgres 做 INT4→INT8 widening、小表、無資料損失）。API 加合理上限（`le=1e15`）讓誇張值乾淨 422 而非到 DB 才炸。**回歸守門用「斷言欄位型別是 BigInteger」**（因為 SQLite 不會溢位，跑值的測試擋不住回退成 INT4）。
- **教訓**：① **凡是「數量會成長的計數/額度」欄位，預設就用 `BigInteger`**——token 數、bytes、累計計數，很容易破 21 億；INT4 是隱形天花板。② 這是「**SQLite 寬鬆 / Postgres 嚴格**」再一次（同 FK 循環那條）——**數值溢位類 bug 本機測不出、要嘛 Postgres 整合測試、要嘛斷言 schema 型別**。③ 額度/計數類欄位加 API 上限（`le=`），把「到 DB 才 500」變成「schema 就 422」。④ 加欄位/改型別時，**同語意的欄位要一起檢**（一個 self_service_default_quota 溢位，就代表 allocation/pool 的同類欄位也會）。
- **來源**：`models/{allocation,pool_config,model_catalog}.py`（BigInteger）、`alembic/versions/0023_bigint_token_quotas.py`（dialect-guarded ALTER）、`api/admin_self_service.py`（le 上限）、`tests/contract/test_self_service_quota.py`（型別守門）；2026-08-03、ccsh rev 11 / tew rev 113、`sha-6766f2a`。

### 資料驅動端點的 `call` lambda 若寫死只 forward 必填欄位，會靜默吞掉所有 pass-through 參數——OCR 的 `include_image_base64`/`pages` 就這樣沒了

- **理論說**：`/v1/ocr` 走資料驅動 registry（spec 042），`upstream.aocr(**kwargs)` 早就會把 kwargs 經 `_extra` 全轉給 litellm、`engine` 也把上游回應原封 `return payload`——參數/回應鏈是通的。
- **實際發生**（2026-08-06，使用者回報「送 `include_image_base64:true` 回來 base64 是空、`pages` 被忽略整份都掃」）：根因**只在 registry 那一行**——`call=lambda f, r, m: upstream.aocr(model=m, document=f["document"], **creds(r))` **只 forward `document`**，client 送的 `include_image_base64`/`pages`/`image_limit`… 在這層就被丟掉、根本沒進 `aocr`。不是回應被濾（`engine` 沒濾），也不是上游不吐。
- **怎麼定位（分三段各自證）**：① 請求段——讀 registry lambda 發現只送 `document`（smoking gun）；② 回應段——讀 `engine.py` 確認 `payload = upstream_result…; return payload` 沒濾任何欄位（排除「gateway 濾掉圖」）；③ 上游段——**在 pod 裡直接呼叫 `upstream.aocr(..., include_image_base64=True, pages=[0,1,2])`**（現役 pod 即可，因 bug 只在 registry、`aocr` 本身會 forward）打真 PDF，證實 Azure Foundry `mistral-document-ai` **確實吐圖**（page 有 `images[].image_base64` 28KB + bbox、`pages_processed` 隨 `pages` 收斂）。三段分證＝一次就鎖定是中間哪層，不用瞎猜。
- **解決方式**：registry `/ocr` 的 call 改成也 forward **白名單** pass-through 欄位（`_OCR_PASSTHROUGH` = pages/include_image_base64/image_limit/image_min_size/bbox_annotation_format/document_annotation_format/id，用 `_ocr_extra(f)` 挑出 client 有送的非 None 值）——**白名單而非盲 `**f`**，免得把 junk 灌進 litellm。單元測試斷言「送了 include_image_base64/pages → mock aocr 的 await kwargs 收得到」。零 migration。
- **教訓**：① 資料驅動端點省了流程碼，但每個 `call` lambda 是「欄位→上游」的**手寫對應**，很容易只接必填、**靜默漏掉選填 pass-through**——加端點/審端點時要問「這個上游 API 還吃哪些選填參數？有沒有都接上？」。② debug「參數/資料在哪層不見了」用**分段各自證**（請求映射 / 回應塑形 / 上游行為），比端到端瞎試快。③ **上游行為可用現役 pod 直接呼叫 wrapper 驗**（繞過壞掉的路由層），不必等修好部署——尤其想先確認「上游到底支不支援」再決定要不要修。
- **來源**：`proxy/registry.py`（`_OCR_PASSTHROUGH`+`_ocr_extra`、`/ocr` spec）、`tests/contract/test_ocr.py::test_ocr_forwards_image_and_pages_params`；spec 042、無 migration、ccsh rev 12、`sha-b2f0d96`（2026-08-06，真 PDF 端到端驗證圖穿透）。

### GitHub Actions runner 整個不接單時，本機 `docker buildx --platform linux/amd64 … --push ghcr` 是部署逃生路

- **實際發生**（2026-08-06）：push 到 main **完全沒觸發** Image build run（上一個 run 停在 3 天前）、手動 `workflow_dispatch` 也卡 `queued` 9 分鐘 job 沒開始——GitHub 那側 runner 不健康，等它無底洞。
- **解決方式**：本機自己 build 推 ghcr、繞過 Actions——`gh auth token | docker login ghcr.io -u <user> --password-stdin` → `docker buildx build --platform linux/amd64 -f deploy/docker/Dockerfile -t ghcr.io/<user>/ai-api:sha-<shortsha> --push .`（tag 沿用 `sha-<git短碼>` 慣例，可追溯）→ 照常 `helm upgrade --set image.tag=sha-<shortsha>`。**節點是 amd64**（`kubectl get nodes -o …architecture` 先確認）→ 在 arm64 Mac 上走 emulation，`uv pip install` 慢一點但 litellm 有 manylinux wheel 不需 rust（本機直接 `uv run` 反而會想從 sdist 編 litellm-rust、撞本機舊 rustc 而失敗——**別在本機 host 上 uv run 跑測試驗 litellm 版，用現有 `.venv` 或直接 Docker**）。
- **教訓**：① CI 只是「方便的預設路徑」不是唯一出圖法——image build 本質是 `docker build+push`，Actions 掛了就本機做，deploy 不必被 CI 綁架。② tag 仍用 `sha-<git碼>` 讓「跑的 image ↔ 哪個 commit」可追。③ 本機 build 要**對齊叢集節點架構**（amd64/arm64）。④ 這條跟「litellm 1.95 的 rust 元件本機編不動（rustc 太舊）」是同一顆地雷的兩面——Docker builder 用 python:3.11-slim + manylinux wheel 避開了，本機 host uv run 卻會踩到。
- **來源**：`deploy/docker/Dockerfile`（python:3.11-slim builder → distroless runtime）；2026-08-06、繞過 GitHub Actions runner outage 部署 ccsh rev 12。

### `/v1/chat/completions` 一直沒實作串流——`stream:true` 被靜默吞、回整包 JSON；且跟 OCR 同款只 forward `messages`

- **理論說**：`engine.py` 註解寫「串流端點（chat/completions、responses）因要串流中計費、各有 handler」——聽起來 chat/completions 有串流。
- **實際發生**（使用者問「是不是沒支援 stream？」）：只有 `/v1/responses` 真的實作了 SSE；`router.py::proxy_chat_completions` **完全沒碰 `stream` 欄位**——不管送不送 `stream:true` 都呼叫 `acompletion`（非串流）回一整包 `chat.completion` JSON。用 OpenAI SDK 開 `stream=True` 的 client 期待 SSE chunk、卻拿到整包 → 解析失敗/卡住。而且**跟 OCR 同一顆地雷**：handler 只 forward `messages`，`temperature`/`max_tokens`/`tools`/`tool_choice`/… 全被丟（見上方 OCR 那條）。
- **解決方式**：比照 `/v1/responses` 的串流模式——`stream:true` → `upstream.acompletion(stream=True, ...)` → `StreamingResponse`，逐 chunk relay 成 `data: {..}\n\n` + 收尾 `data: [DONE]\n\n`。計費：**強制對上游帶 `stream_options={"include_usage": True}`**（不管 client 有沒有要），這樣一定拿得到 token 數 → 在收到 usage chunk 當下（client 還連著）用**獨立 fresh session** 記帳（`get_db_session` 的請求 session 在 StreamingResponse body 跑時已關）＋ `finally` 保底（斷線也不漏帳）。兩條路（stream/非stream）都改成 forward 一份 chat 參數白名單。
- **踩到的真實差異**：**OpenAI 標準**是「沒要 usage 就完全不送；要的話最後一個 chunk `choices:[]`＋usage」。但 **Azure/litellm 把 usage 掛在一個 `choices` 非空的 chunk 上**——所以「choices 空才 strip」的第一版邏輯攔不到、會把 usage 洩漏給沒要的 client。修正：沒要 usage 時，凡帶 usage 的 chunk 就把 `usage` 欄位設 `null` 再轉發（choices 也空才整包丟），billing 照樣從原值記。**真機驗證**：沒要 usage→回應 `"usage":null` 不外洩、要 usage→usage 正常帶出、三筆串流都正確記帳。
- **教訓**：① 「有各自的 handler」不等於「都實作了」——註解描述**意圖**，要看 handler 真的做了沒。② 串流計費要在**收到 usage 當下就記**（client 還連著），別留到 `finally`——client（Codex/SDK）常在最後一個 event 後立刻斷線 cancel task，`finally` 會漏（同 responses 那條）。③ 串流記帳一律**開新 session**（請求 session 早關）＋ `except BaseException` 吞 CancelledError 才不會靜默漏帳。④ **別假設上游串流的 usage chunk 形狀**——OpenAI 與 Azure/litellm 不同（choices 空 vs 非空），要對「任何帶 usage 的 chunk」都處理，strip/null 要能涵蓋兩種 framing。⑤ 為了計費**強制上游 include_usage**、但對「沒要的 client」保持 OpenAI 語意（不外洩 usage）＝gateway 要能「自己要、幫 client 過濾」。
- **來源**：`proxy/router.py`（`_CHAT_PASSTHROUGH_FIELDS`、串流分支 `event_gen`/`_record_fresh`/`_bill`、usage null-on-relay）、`tests/contract/test_proxy_chat.py`（串流 forward/記帳/斷線保底/usage strip/null/passthrough）；無 migration、ccsh rev 14、`sha-cabdd3e`（2026-08-08，真機兩案驗證）。期間 image build 又被 Trivy 月度漂移擋（aiohttp CVE-2026-69244→3.14.3、cryptography CVE-2026-69247→50.0.0，皆有 fix 直接升）。

### 轉發 client 參數會讓推理模型 502（temperature≠1）；litellm `drop_params` 救不了「自訂 Azure deployment 名」——要反應式丟參數重試

- **理論說**：上面加了 chat 參數 passthrough（含 `temperature`）＝更完整。加 `drop_params=True` 就能讓 litellm 自動丟掉模型不支援的參數。
- **實際發生**（rev 14 上線後使用者回報「對話串流 502」）：某些**推理模型只接受 `temperature=1`**（Azure 回 `400 Unsupported value: 'temperature' does not support 0.4`）。client 送 `temperature:0.4` → 我照 passthrough 轉發 → Azure 400 → gateway 502。**串流與非串流都中**（我引入的回歸——改之前 temperature 根本沒轉發所以不會爆）。加了 `drop_params=True` **仍 502**：litellm 的 drop_params 靠它**內建模型表**查「該模型支援哪些參數」，但 `gpt-5.6-luna` 是**使用者在 Azure 自訂的 deployment 名**，litellm 不認得（deployment 名是任意別名、無法反推底層模型）→ 退回「當普通 chat 模型、支援 temperature」→ 不丟。
- **解決方式**：**反應式重試**——上游因某參數 400 時，從錯誤訊息 regex 出 param 名（`_rejected_param`：`Unsupported value/parameter: 'X'`、`'X' does not support`）、把它從 droppable 拿掉、重試（每次只丟一個 → 有界終止）。不依賴 litellm 認不認得模型。`drop_params=True` 保留當第一層（認得的模型直接丟）。**失敗那次不計費**（Azure 400 在跑模型前、無 token；且 `record_call` 只在成功後跑，重試 loop 內不寫任何 record）→ 無雙重計費、無幽靈帳；串流的 400 發生在「回 StreamingResponse 前」→ client 不會收半截再重來。真機驗證：`gpt-5.6-luna`+`temperature=0.4` 串流/非串流都 200，log 有 `dropping and retrying`，帳只記一筆。
- **教訓**：① **gateway 轉發任意 client 參數給任意模型 = 一定會撞到「某模型不吃某參數」**；別假設參數通用。② **litellm `drop_params` 依賴模型表**，對「自訂 Azure deployment 名／比 litellm 版本新的模型」無效——真正 provider-agnostic 的作法是**反應式 catch 400 → 丟指名參數 → 重試**。③ 加「把 client 輸入轉發給上游」的能力時，**同時想好「上游嫌棄某輸入」的降級路徑**（drop+retry），否則就是把上游的 400 直接變成自己的 502。④ 重試要保證**不重複計費**：只在成功後記帳、失敗路徑不寫 record；並確認失敗是 pre-inference（不然可能已產生 token）。⑤ 我們目錄其實有 `reasoning` 能力標記，未來可據此**預先**不送 temperature 省掉那一次往返——但重試是必留的保險網。
- **來源**：`proxy/router.py`（`_rejected_param`、`_call_upstream` 重試迴圈）、`tests/contract/test_proxy_chat.py::test_proxy_chat_retries_dropping_rejected_param`；無 migration、ccsh rev 16、`sha-061a079`（2026-08-08，`gpt-5.6-luna`+temperature 真機驗證）。

### multipart 上傳 502：`UploadFile` 要從 `starlette` import，不是 `fastapi`——後者是子類，`isinstance` 對 `request.form()` 的實例回 False

- **理論說**：engine 的多段解析把 `UploadFile` 轉成 `(filename, bytes)` tuple 再送 litellm，語音/圖片編輯端點都走這。
- **實際發生**（使用者回報 `/v1/audio/transcriptions` 502）：litellm/openai 噴 `Expected entry at 'file' to be bytes/IOBase/PathLike/tuple but received <class 'starlette.datastructures.UploadFile'>`。根因：engine `from fastapi import UploadFile`，但 `await request.form()`（starlette）回的是 **`starlette.datastructures.UploadFile`**；`fastapi.UploadFile` 是它的**子類** → `isinstance(starlette實例, fastapi.UploadFile)` = **False** → 轉換分支沒進 → 原始 UploadFile 直送上游 → openai `assert_is_file_content` 擋下 → 502。影響所有 multipart 端點（`/v1/audio/transcriptions`、`/v1/images/edits`）。
- **為什麼測試沒抓到**：契約測試 `patch("upstream.atranscription", AsyncMock(...))`——mock **照單全收原始 UploadFile、不檢查型別**，所以「檔案沒被轉成 tuple」這件事被 mock 遮住；只有真上游（openai client）才會嫌。**mock 掉上游 = 也 mock 掉了型別契約**。
- **解決方式**：`from starlette.datastructures import UploadFile`（父類，`isinstance` 同時涵蓋 starlette 與 fastapi 兩種實例，因 fastapi 的是子類）。**測試加「mock 無關」的守門**：斷言 mock 收到的 `file` 是 `tuple`、且 `[0]==檔名`、`[1]==bytes`（而非光看 200——200 是 mock 給的、遮住真 bug）。
- **教訓**：① **`request.form()` 直接讀（繞過 FastAPI 參數模型）時，UploadFile 是 starlette 型別**；要判型別就 import starlette 的（父類），別 import fastapi 的（子類、只認得經 FastAPI 參數注入的實例）。② **mock 上游會連帶 mock 掉型別/序列化契約**——凡是「我方把資料塑形後交給上游」的轉換，測試要**直接斷言塑形結果**（收到的是 tuple 嗎？），不能只看 mock 回的 200。同類：OCR「回應塑形」「參數轉發」也該斷言塑形本身。③ 子類 `isinstance` 陷阱：`isinstance(父實例, 子類)` 恆 False——用「基底類別」判型別最穩。
- **來源**：`proxy/engine.py`（`from starlette.datastructures import UploadFile`）、`tests/contract/test_audio.py::test_stt_multipart_billed_tokens`（斷言 tuple 轉換）；無 migration、ccsh rev 17、`sha-96d5938`（2026-08-08，真 WAV 打 `azure/whisper` 200 驗證）。附帶觀察：whisper 不回 usage → 逐筆 token 為 null（TokenMeter 對 whisper 計不到量，屬既有計費議題、非本 bug）。

### 有些模型要**必填**特定參數（diarization 要 `chunking_strategy`）——drop-param 的反面：反應式「補上預設重試」

- **實際發生**（使用者逐字稿 app 打 `azure/gpt-4o-transcribe-diarize` 502）：`chunking_strategy is required for diarization models`。轉錄 spec 跟 OCR 同款只 forward `file`，client 也沒送 → 缺必填 → Azure 400 → 502。這是 temperature 那條（參數被拒→丟掉）的**反面**：這次是**缺必填→要補上**。
- **解決方式**：轉錄改用具名 call 函式（非 lambda）——① forward 白名單 STT 參數（`language`/`prompt`/`response_format`/`chunking_strategy`/`timestamp_granularities`/`include`；**故意不含 temperature**，因某些轉錄模型也拒 temperature）；② 反應式：catch「`chunking_strategy` …required」→ 補 `chunking_strategy="auto"` 重試。真機驗證：diarize 模型 200、回 usage（`input_tokens`/`output_tokens`）。
- **教訓**：① provider 的「參數契約」有兩面——**多餘的要丟（drop）、缺的要補（inject）**；gateway 轉發任意 client 輸入給任意模型，兩面都要有降級路徑，否則就是把上游 400 變自己 502。② 反應式重試（從錯誤訊息判斷要丟哪個/補哪個）比「維護每模型參數表」耐用（litellm 的模型表對自訂 Azure deployment 名無效，見上）。③ **engine 的 `spec.call` 可以是有狀態的 async 函式**（含 try/retry），不必是純 lambda——需要重試/降級的端點就寫成具名函式。④ 新的 transcribe 模型回 usage 用 `input_tokens`/`output_tokens`（非 `prompt/completion_tokens`）→ TokenMeter 只接到 total、prompt 為 null；同 responses 的 usage 映射議題，未來可為 STT 加 `input→prompt` 映射（計費精度，非 502）。
- **來源**：`proxy/registry.py`（`_STT_PASSTHROUGH`、`_transcription_call` 具名函式 + chunking_strategy 補值重試）、`tests/contract/test_audio.py::test_stt_diarization_injects_chunking_strategy`；無 migration、ccsh rev 18、`sha-8f18eaf`（2026-08-08，`gpt-4o-transcribe-diarize` 真 WAV 200 驗證）。

### 前端 nginx 的 `/v1` catch-all 沒設 proxy timeout → 60 秒預設切斷長轉錄/OCR/圖片 → 504（回的是 nginx HTML，不是閘道 JSON）

- **理論說**：閘道前面是 traefik ingress；長工作靠端點自己處理。
- **實際發生**（使用者逐字稿「第 1/6 段 15%」時噴 `504 <html>...nginx/1.27.5...`）：① 回的是 **nginx HTML 504 不是我閘道的 `{"error":...}` JSON** → 是「某層 nginx 逾時」，不是閘道邏輯；② `curl -I https://ai.ccsh.tn.edu.tw` 的 `server: nginx/1.27.5` 揭穿——**閘道前面那層 nginx 就是我們自己的前端 pod**（`nginxinc/nginx-unprivileged:1.27-alpine`，服務 SPA + 反向代理 API 到後端；架構是 ingress→前端nginx→後端，不是直連後端）；③ 前端 `deploy/nginx/default.conf.template` 只有 `/v1/responses`、`/v1/realtime` 設了 `proxy_read_timeout 3600s`，**generic `location /v1` 沒設 → 吃 nginx 預設 60 秒** → 所有非串流長工作（轉錄/diarization、OCR 大 PDF、圖片生成、長非串流 chat）跑過 60 秒就被前端 nginx 切成 504。
- **解決方式**：generic `/v1` 也加 `proxy_read_timeout 3600s` + `proxy_send_timeout 3600s`（後者給大檔上傳）。**template 烤在前端 image 裡** → 要重建**前端** image（非後端）+ `helm --set frontend.image.tag=`。驗證：exec 進前端 pod `grep -A4 "location /v1 " /etc/nginx/conf.d/default.conf` 確認 3600s 上線。
- **教訓**：① **回的錯誤長什麼樣就能定位是哪一層**——nginx HTML 504 ≠ 閘道 JSON error；先看回應格式再猜。② `server:` 標頭直接告訴你有幾層 proxy——**別假設拓撲**（記憶裡寫 traefik，實際前面還有自家前端 nginx）。③ **反向代理的 catch-all location 要跟特例 location 一樣顧到 timeout**——只給串流端點設長 timeout，非串流長工作（轉錄/OCR/圖片）會被 catch-all 的預設 60 秒陰到。④ 這類「限制在 proxy 層」的問題，程式碼再對也沒用——**盤點限制要含 nginx/ingress 設定**（timeout、client_max_body_size、buffering）。⑤ 前端 nginx 設定改動 = **重建前端 image**，別只動後端。
- **來源**：`deploy/nginx/default.conf.template`（generic `/v1` 加 proxy_read/send_timeout 3600s）；ccsh rev 19、前端 `sha-9876f8b` + 後端 `sha-6a6a40a`（2026-08-08，pod 內 grep 驗證 timeout 上線）。同批出：**TokenMeter 補 `input_tokens/output_tokens→prompt/completion` 映射**（`endpoint_spec.py`，修 gpt-4o-transcribe/-diarize token 計費本為 0；真機驗證 diarize 現記到 prompt=15/completion=82/total=97）。whisper 無 usage 的按時長計費**經使用者決定先不做**（無音訊庫、不新增套件；diarize/transcribe 有 token 已足夠）。
