# 原則

> 工程通則（TDD、契約優先、可觀測性、YAGNI 等）見 `.specify/memory/constitution.md`。
> 本檔只記「AI API 分享與權限管理」的**領域**原則：根公理 + 從它推導的 7 條。
> 原則應該很少改；經常要編輯的多半是設計決策（歸 `concepts/`）或因果軌跡（歸 `history/`）。

## 根公理

**分享就是資源的分配。**

在組織內部脈絡下，AI API 的存取權不是抽象的「許可」，而是具體的「資源」——模型存取、
用量配額、速率上限、成本歸屬。分享一個 API 就是把資源的一部分分配給某個團隊或個人；
**分配是有對象、有額度、可調整、可收回的**，不是一次性的移交。下面 7 條全是它的投影。

## 衍生原則

### 1. 憑證隔離（Credential Isolation）

- **推導自**：根公理（每筆分配都是獨立的領取，不能共用單據）。
- **意義**：被分配者永遠拿不到底層供應商的 API key；系統發行獨立、可識別、可撤回的憑證。
  **唯一性與額度的單位是「分配」而非「token」**——憑證是一把可命名的**應用 key（scoped
  application credential）**，其 scope 為一組分配（≥1），每次呼叫依 request 的 model 歸戶到
  對應分配。〔業界對照：GitHub fine-grained PAT、service account、OAuth scopes。〕
- **如何應用**：對外 token 綁定一組分配（同一把 key 內各分配 model 不得重複，否則歸戶有歧義）；
  底層供應商 key 只存在服務內部，絕不出現在回應/日誌/錯誤；一分配可被多把憑證授權、撤銷單把
  不影響其他（名副其實）；額度/歸戶在分配層，故 token 數不繞過配額與異常偵測、無需軟上限；
  **attenuation（不提權）**——一把 key 的 scope 只能含擁有者已被授予的分配。
- **首見**：Arc 1（分配/憑證的初始模型）；一般化為 M:N 於 Arc 5（階段 20）。詳見
  `concepts/憑證是應用金鑰其單位是分配而非token.md`。

### 2. 可追蹤性（Traceability）

- **推導自**：根公理（分配本質要求帳目清楚）。
- **意義**：每筆分配綁定可識別資源（模型/端點/專案），每次呼叫都能回溯到「分配 → 被分配者 →
  團隊」。資源端與使用端兩面都可追蹤，才構成完整審計。
- **如何應用**：分配必有資源綁定，不存在「萬用/匿名分配」；呼叫日誌必帶分配 ID 與身份，無可
  歸屬者記為匿名拒絕、不得硬塞給任一分配；**拒絕路徑跟成功路徑一樣是一等公民**（要在 raise 前
  先 bind 上下文）；DB 有記的欄位要確認有序列化出去（否則可觀測性只是名義上的）。
- **首見**：Arc 1。跨端點延伸至 Responses/多單位計費/逐筆散點（Arc 4/6/8）。

### 3. 即時撤回（Instant Revocation）

- **推導自**：根公理（資源不是送出去就拿不回來的）。
- **意義**：撤回後任何後續呼叫立刻被拒，不依賴 token 自然過期。
- **如何應用**：每次呼叫驗證分配的「當前狀態」而非只驗 token 簽章（故選 server-side session、
  每次查 DB 現況，而非 stateless JWT）；撤回生效有 SLO、必留稽核；連線型端點（realtime）以旁路
  週期 re-check 收斂到同一 SLO。
- **首見**：Arc 1（001 research §4 逼出「每次查 DB 現況」+ server-side session 兩個架構決策）。

### 4. 轉分配需顯式允許（No Implicit Re-allocation）

- **推導自**：根公理（被分配到資源的人，預設沒有再分配的權力）。
- **意義**：被分配者預設不能把資源再分給第三方；如需轉分配，須由擁有者明確開啟。
- **如何應用**：分配上有 `can_redelegate` 旗標，預設 `false`；即使開啟，二次分配範圍不得超過原
  分配，擁有者仍可見、可撤回整條鏈。OAuth/應用金鑰的 attenuation 是同一精神的現行具現（只能打包
  自己已被授予的分配，不創造新權限）。
- **首見**：Arc 1（原則層預埋）；attenuation 於 Arc 5/8 落地。

### 5. 集中管理單一真理（Single Authority for Access）

- **推導自**：根公理 + 原則 2（多條路徑管同一件事 → 必然 drift → 追蹤斷裂）。
- **意義**：對「誰能存取什麼」「配額多少」「哪些 redirect 可放行」這類治理決策，系統內只有**一條
  可改寫的路徑**；其他機制要嘛 derive 自它、要嘛只在它不存在時當 bootstrap fallback。
- **如何應用**：成員清單是 access 的單一真理，email 白名單退為 bootstrap-only；業務/治理設定用
  `CHECK id=1` DB 單例 + lazy-seed（env 退為 bootstrap 預設），且**所有讀取點都改指向單一入口**，
  漏一個就是「顯示 ≠ 執法」的沉默 drift；一個語意旗標可支援多個治理用途（service flag 同時豁免
  rebalance 與 anomaly），不為每個機制各加專用 exempt 旗標。
- **首見**：Arc 1/3（白名單 → bootstrap-only 的種子）；模式化為 env→DB 單例於 Arc 7/8。詳見
  `concepts/env設定搬DB單例用lazy-seed保首次零行為變更.md`、`concepts/同一件事只能有一條可改寫的路徑.md`。

### 6. 可達性（Accessibility）——被分配者必須能實際取用

- **推導自**：根公理（分配的目的是讓對方**真的用到**；因技術門檻/缺 UI/裝置限制而用不到，這筆
  分配只是名義上的、不算完成）。
- **如何應用**：面向非技術使用者用白話 UX；admin 與成員的每項能力都要有對應 UI——
  **「後端有 API 但只能靠工程師/SQL 才能操作」視為功能未完成，非待 polish**；自助操作不需另一個
  actor 協助；跨裝置可用（桌機完整、手機堪用）；「目錄能放但 gateway 服務不了」＝名義可見、實質
  不可達，要補齊（Arc 6 多端點全開的母題）。
- **首見**：Arc 4（由手機 RWD / 成員圖表驅動，2026-06-09 正式寫入）。反面案例遍布 Arc 6/7/8。

### 7. 演進性（Evolvability）——核心穩定、邊緣快變，用適配層隔開

- **推導自**：根公理（分配的價值「誰能用什麼、可計量、可撤回、可追蹤」與 AI 能力的快速更迭無關；
  故核心必須與快變的 AI 邊緣隔離，否則邊緣的 churn 會把核心一起拖垮）。
- **如何應用**：
  - **適配層**：快變外部依賴（litellm 等）只透過單一 adapter 對話（`litellm_registry` /
    `proxy/upstream.py`）——版本變動只改一處，爆炸半徑鎖在邊緣。
  - **資料勝於程式**：易變的東西（模型/價格/能力旗標/端點）做成可同步、可編輯的**資料**（端點
    registry、model_test recipe 表），「新模型上市」＝加資料而非改碼。
  - **實測勝於臆測**：會變的能力做成「可測試 + admin 可覆寫」（responses 雙來源、依種類測模型）；
    採用 SDK 前先 `inspect.signature`/`print` 驗證能力邊界。
  - **守住軸的正交**：新功能先問「這是哪條軸」（①模型原生 API 型態 ②模型能力 ③gateway 端點可用性
    ④客戶端工具），別 overload 既有欄位（把 responses 從 mode 推導的 latent bug 即代價）。
  - **build-vs-adopt 判準**：以「領域第一公民是否同軸」判，非功能重疊度；對已兌現價值的核心，門檻
    再升一級（realtime 不用 litellm Proxy form 即此）。
- **首見**：Arc 5（多條教訓收斂，2026-06-09 新增為原則 7）。詳見
  `concepts/模型資訊的三軸要正交不可overload一個欄位.md`、`concepts/功能重疊不等於該adopt判準是領域第一公民同不同軸.md`。

## 關鍵延伸（主題觸發必讀）

| 觸發關鍵字 | MUST 讀 |
|---|---|
| 憑證 / 應用金鑰 / scope / M:N / 歸戶 | `concepts/憑證是應用金鑰其單位是分配而非token.md` |
| 白名單 / 單例設定 / env→DB / lazy-seed | `concepts/env設定搬DB單例用lazy-seed保首次零行為變更.md` |
| 單一真理 / 平行路徑 / drift | `concepts/同一件事只能有一條可改寫的路徑.md` |
| 可見性 / access policy / 目錄過濾 | `concepts/可見性等於供給存在交集授權允許.md` |
| responses / 能力 / mode / 軸 | `concepts/模型資訊的三軸要正交不可overload一個欄位.md` |
| 計費 / 單位 / 配額 / USD | `concepts/花費USD是跨計量單位的唯一共同分母.md` |
| 端點 / registry / 加端點 | `concepts/加一個同形態端點應該等於加一筆資料.md` |
| build vs adopt / litellm / realtime | `concepts/功能重疊不等於該adopt判準是領域第一公民同不同軸.md` |
| 部署 / fail-fast / 首位 admin | `history/004-bootstrap-admin-token從主要保護降為break-glass.md` |
