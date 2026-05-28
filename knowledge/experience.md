# 經驗

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

### Helm pre-install Job 需要 Secret，Secret 必須也是 hook

- **理論說**：Helm install 把 manifests 全部建立後才執行 hook。
- **實際發生**：把 migration Job 標為 `pre-install` hook 後，Job 啟動但
  `Error: secret "..." not found` — 因為 hook 在 regular manifests **之前**
  跑，Secret 還沒被建立。
- **解決方式**：給 Secret 加 `helm.sh/hook: pre-install,pre-upgrade` +
  `helm.sh/hook-weight: "-10"`，比 Job 的預設 weight 0 更早執行。
- **教訓**：Helm hook 順序 = (前置 hook 全部跑完) → (regular manifests) →
  (post hook)。任何被 pre-hook 依賴的東西也必須是 pre-hook。
- **來源**：`deploy/helm/ai-api/templates/secret.yaml`

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

### SQLAlchemy delete 後不要再讀屬性

- **理論說**：設定 `expire_on_commit=False` 就能在 commit/flush 後安全存取
  ORM 物件屬性。
- **實際發生**：OIDC callback 流程中先 `await session.delete(state_row)` +
  `await session.flush()`，再讀 `state_row.code_verifier` / `state_row.nonce`
  傳給 token exchange。authlib 收到的是錯誤值（空 / 過期），整個 SSO 失敗
  且錯誤訊息只說 `invalid_credentials`，難以定位。
- **解決方式**：在 `delete()` **之前**就把要用的屬性 cache 成 local
  variables，再執行 delete。
- **教訓**：對於「讀後即刪」的短期 token / state 表，永遠先把要用的欄位
  copy 到 local，再 delete。`expire_on_commit=False` 不等於「物件可永遠
  被讀」。
- **來源**：`src/ai_api/api/auth.py` `oidc_callback`，修正於 commit ce3d640

### OIDC id_token 驗證要給 clock-skew leeway

- **理論說**：本機系統時間透過 NTP 同步，與 Google 偏差可忽略。
- **實際發生**：authlib 預設 `claims.validate()` 不容忍 `iat` 在「未來」。
  本機時鐘比 Google 慢 ~3 秒，每張 Google id_token 都被拒
  `InvalidTokenError: The token is not valid as it was issued in the future`。
  整段 SSO live 驗證在此卡了三輪。
- **解決方式**：`claims.validate(leeway=60)`，容忍 60 秒時鐘偏移
  （OAuth 2.0 / OIDC spec §5.3 推薦的合理範圍）。
- **教訓**：任何接收外部簽發 JWT / id_token 的程式，**預設都要設 leeway**
  （≥ 30 秒），不要假設本機時鐘準。同時 AuthError 訊息應該帶 JoseError
  子型別，否則 debug 等於猜謎。
- **來源**：`src/ai_api/auth/google_oidc.py`，修正於 commit ce3d640

### SQLAlchemy 多分支 select 的型別衝突

- **理論說**：同一個 service 函式內，可以根據參數分支構造不同的 `select(...)`
  並重用同一個 `stmt` 變數，型別推導應該自動處理。
- **實際發生**：在 `services/usage.py` 的 `aggregate_usage` 寫
  `if group_by == "member": stmt = select(...)` / `elif "allocation": stmt = select(...)`，
  mypy 立刻抱怨 `Incompatible types in assignment` — 因為
  `Select[tuple[X, Y, Z]]` 與 `Select[tuple[A, B, C]]` 是不同型別。連
  `# type: ignore` 都解不開（後續 `rows = (await db.execute(stmt)).all()`
  還是會撞型別）。
- **解決方式**：**每分支用獨立變數名**（`alloc_stmt`、`model_stmt`）+ 獨立
  `alloc_rows`、`model_rows`；保留 `stmt`/`rows` 給第一個分支。
- **教訓**：在強型別 + SQLAlchemy Core 環境下，分支建構的查詢別硬要共用
  變數名。「變數即型別」原則對 Core 特別重要。
- **來源**：`src/ai_api/services/usage.py` `aggregate_usage`

### httpx 測試 URL 帶 ISO datetime 必須先 quote

- **理論說**：`datetime.isoformat()` 產出的字串放進 query string 應該沒
  問題。
- **實際發生**：`f"?from={now.isoformat()}"` 給 httpx，FastAPI 端解析回
  422。原因：`isoformat()` 含 `+00:00`，`+` 在 query string 中是合法字元
  但被解析視為**空格**，導致 datetime 反序列化失敗。
- **解決方式**：測試端 `urllib.parse.quote(now.isoformat())`；或更穩的
  做法 — 改用 `client.get("/path", params={"from": now.isoformat()})` 由
  httpx 自行 URL-encode。
- **教訓**：任何「自行拼 query string」的測試都該過一遍 `quote`；偏好走
  client 的 `params=` 介面把這層事情交給工具。
- **來源**：`tests/integration/test_aggregation.py`

### 快速迭代不要用 mutable tag

- **理論說**：`helm upgrade --set image.tag=main` 配合 push 新版到 ghcr，
  叢集會拉到最新。
- **實際發生**：image 推上去了，但 kubelet 仍用先前 `main` 的 layer
  ——因為 `pullPolicy: IfNotPresent` 且 tag 相同，**不會重新解析 digest**。
- **解決方式**：驗證迭代時使用 immutable sha tag（`sha-<short>`），或暫時
  改 `pullPolicy: Always`。生產可以維持 `IfNotPresent` + 不可變 tag。
- **教訓**：mutable tag (`main` / `latest`) 適合宣告「想要某個流」，不適合
  「想要這個版本」。任何「為什麼跑舊版？」的除錯都從 image digest 開始查。
- **來源**：2026-05-21 k3s-tew 部署驗證

### TypeScript composite project reference 與 `noEmit` 衝突

- **理論說**：用 `references: [{ path: "./tsconfig.node.json" }]` 把 `vite.config.ts`
  獨立成子專案是 Vite 官方範本的標配。
- **實際發生**：`tsc --noEmit` 在 root tsconfig 報
  `TS6305: Output file 'vite.config.d.ts' has not been built from source file 'vite.config.ts'`。
  Composite project **必須** emit `.d.ts`，但 root 設 `noEmit: true`，兩者互斥。
- **解決方式**：對小型前端（單一 src 樹），**刪掉 composite reference**，把
  vite.config.ts 直接放進 root tsconfig 的 include 即可。如真的需要分層，
  改用 `tsBuildInfoFile` 或多個獨立 tsconfig 並分次跑 tsc。
- **教訓**：composite project 不是「免費的好做法」— 為了一個設定檔分層會把整
  個 typecheck 流程綁定到 emit 模式。
- **來源**：`frontend/tsconfig.json`，3b.0 scaffold

### Vitest 自帶 Vite 副本導致 plugin 型別衝突

- **理論說**：`vitest.config.ts` 用 `defineConfig` from `vite` 加上 React plugin，
  在 `test:` 欄位填 Vitest 設定即可。
- **實際發生**：tsc 抱怨 `Type 'PluginOption' is not assignable to type 'PluginOption'`
  —— 兩個型別字面相同但來自不同路徑：`node_modules/vite/...` vs
  `node_modules/vitest/node_modules/vite/...`。Vitest 為了鎖版本自帶一份 Vite。
- **解決方式**：選一條 — `// @ts-expect-error - vitest extends Vite config`
  在 `test:` 上頭蓋章；或拆分 `vite.config.ts` 與 `vitest.config.ts` 並用
  `mergeConfig` 從 vitest/config 來合併。
- **教訓**：tool ecosystem 嵌套 dep 是常態（vitest / next.js / remix 都自帶
  vite）；遇到「兩個看起來一樣的型別不相容」第一反應就是 grep `node_modules`
  找重複包。
- **來源**：`frontend/vitest.config.ts`

### ESLint 在 TS 檔對 DOM 全域類型誤報 `no-undef`

- **理論說**：`eslint:recommended` 的 `no-undef` 規則加上 browser globals 設定
  足以涵蓋 TS 檔。
- **實際發生**：在 .ts/.tsx 寫 `RequestInit`、`React`（JSX runtime 自動引入）
  時 ESLint 都報 `'X' is not defined no-undef` — 因為 ESLint 不解析 TS 型別
  系統，只看 JS scope。
- **解決方式**：在 flat config 對 TS 檔**關掉 `no-undef`**
  （`"no-undef": "off"`）— TypeScript 自己會 catch 真正的 undefined。
- **教訓**：lint 規則該由「規則來源能看到的資訊」決定 — ESLint 看不到 TS 型別，
  就讓 TS 自己處理。重複交叉執法只會誤報。
- **來源**：`frontend/eslint.config.js`

### Alpine 基底 image 的 CVE 要主動 `apk upgrade` 補

- **理論說**：用官方 `nginx:1.27-alpine` 即可享受 Docker Hub 的安全維護。
- **實際發生**：Trivy 對 fresh-pulled `nginx:1.27-alpine` 報兩個 HIGH CVE
  （nghttp2-libs CVE-2026-27135 + zlib CVE-2026-22184）— 上游 Alpine 已有
  patched 版本，但 nginx 官方 image 重建頻率落後。
- **解決方式**：Dockerfile 在 `FROM nginx:1.27-alpine` 之後加
  `RUN apk upgrade --no-cache` 拉最新 patch；不增加 image 體積、不需 ignore CVE。
- **教訓**：固定上游 `:tag` 給的是「軟體版本」承諾，不是「最新 OS patch」承諾。
  alpine-based image 一律加 apk upgrade 是建議做法；distroless 或 wolfi 才
  能避開這層責任。
- **來源**：`deploy/docker/Dockerfile.frontend`，PR #8 Trivy scan

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

### Docker 沒開時 testcontainers 是 error 不是 skip — 新測試優先走 Docker-free

- **理論說**：整合測試一律靠 testcontainers 起真 Postgres；本機沒 Docker 時它會自動 skip。
- **實際發生**：階段 9 開工跑 `pytest` 出現 **54 個 error**（非 skip）——`conftest` 只在
  `testcontainers` import 失敗時 `pytest.skip`，但套件裝得好好的、是 **Docker daemon 沒開**，
  於是 `PostgresContainer()` 在 fixture setup 階段 raise → error。TDD 的 Red/Green 被環境卡住。
- **解決方式**：新測試優先走 **Docker-free** 路徑——service 層用自帶 temp-file SQLite engine
  （`create_async_engine` + `Base.metadata.create_all`）；端點層用既有 contract 套件的
  in-memory SQLite `app_client`（`reset_engine_for_testing("sqlite+aiosqlite:///:memory:")`）
  搭配登入 helper 或 `dependency_overrides`。Docker 回來後再跑完整 Postgres 整合測試做最終確認
  （階段 9 最終 375 passed）。
- **教訓**：TDD 的測試不該被「Docker 有沒有開」綁架。能用 in-memory / temp SQLite + dependency
  override 表達的行為，就別硬綁 testcontainers——快、可攜、CI 與本機都穩。testcontainers 留給
  「真的要驗 Postgres 專屬行為」（如 tz-aware datetime、enum、JSON column）。判斷某測試為何
  error 時，第一個檢查點就是 `docker info` 是否回應。
- **來源**：`tests/contract/test_me_usage.py`（in-memory）、`tests/integration/test_usage_member_scope.py`
  （temp-file SQLite）；階段 9 / PR #30
