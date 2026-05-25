# 經驗

## 教訓

### build vs adopt 評估要在 specify 之前做

- **理論說**：vision 寫「以 LiteLLM 為核心」就代表會用 LiteLLM。
- **實際發生**：Phase 1 一開始只用了 `litellm.acompletion()` 一個函式
  （library mode），自製了 FastAPI gateway、認證、配額、UI、計費 — 直到
  Phase 3b 收尾使用者才發現「我以為你在 LiteLLM 上加邏輯，沒想到是自幹
  並行版」。多花了大量工，且揹了 LiteLLM 依賴卻沒享受其好處。
- **解決方式**：在 spec / plan 階段就要明確分辨**LiteLLM 是「library」
  還是「Proxy service」**——前者只是函式呼叫，後者才提供 UI / 認證 / 配額
  / 計費。並要主動向 user 確認預設選擇，而不是隱性決定。Phase 011 起改用
  官方 `openai` SDK（Azure mode）直連，drop `litellm` 套件。
- **教訓**：vision 提到的工具，要先確認**它的形態**（lib vs service vs
  framework）和**我們打算用哪個形態**；任何「build vs adopt」決策必須
  在 specify 之前明確問 user，不要在 plan 階段才隱性決定。
- **來源**：`src/ai_api/proxy/upstream.py`（從 `litellm.acompletion` 改
  `AsyncAzureOpenAI`）；PR #11 之後（Phase 011 hotfix）

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
