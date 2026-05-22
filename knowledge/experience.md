# 經驗

## 教訓

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
