# Lessons Archive

> 從 experience.md 移過來的早期教訓——大多是 setup-time 工具坑、或已被 lint/CI/code review 守住的 pattern，
> 留作歷史紀錄。若同類問題未來又冒出來，先在這裡找。

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

## 從 experience.md 移入（2026-06-03，Phase 13 後分流）

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

### 版本化資料的「生效鍵」要用 datetime，不要用 date

- **理論說**：價目版本用「生效日」(date) 當唯一鍵 `(provider, model, effective_from)` 很直覺。
- **實際發生**：同一個模型同一天只能有一個版本——使用者當天想補一個「快取折扣價」版本就撞
  `duplicate_version`，得等到隔天才能改價。對「即時改價」是硬傷。
- **解決方式**：前端生效欄位改 `datetime-local`、預設帶「現在」（本地時區），送出轉 UTC ISO。
  後端本來就存完整 timestamp、唯一鍵也是 timestamp，無需改 schema——只是前端先前砍到只到日。
- **教訓**：append-only / 版本化資料若「同一鍵粒度內可能要產生多筆」，鍵就要用足夠細的粒度
  （datetime 而非 date）。UI 的時間輸入精度會無聲地變成業務限制。
- **來源**：`frontend/src/routes/admin/prices.tsx`（date → datetime-local）；階段 11

## 已內化的通用教訓（2026-08-26 自 experience.md 蒸餾移入）

> 早期較通用、現已成習慣的前端/工具/測試坑;仍有效,只是不再需要放在一頁可讀的核心 experience。

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

### CSS grid 內要 `truncate`，該格必須 `min-w-0`

- **理論說**：給格子加 `truncate` 就會把過長文字截斷加省略號。
- **實際發生**：「最近呼叫」表用 `grid-cols-5` 等寬，但一條不可斷行的 request UUID 把該欄
  撐到比分配寬度還寬，`truncate` 也沒生效——結果「總 tokens」與「請求 ID」視覺上黏成一團。
- **解決方式**：grid/flex 子項預設 `min-width:auto`（不會縮過內容），要讓 `truncate` 作用必須
  加 `min-w-0`；並用比例欄寬（`grid-cols-[...fr]`）+ 欄間距，長 ID 加 `title` tooltip。
- **教訓**：`truncate`（`overflow:hidden`）在 grid/flex 子項裡幾乎都要搭配 `min-w-0` 才有效，
  這是排版「欄位互相擠爆」最常見的根因。
- **來源**：`frontend/src/routes/allocation-detail.tsx` 最近呼叫表；階段 11

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
