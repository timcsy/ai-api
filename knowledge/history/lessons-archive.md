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

