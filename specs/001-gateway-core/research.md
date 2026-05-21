# Phase 0 Research: 階段 1 — 分流核心

本檔解決 plan.md Technical Context 中所有 NEEDS CLARIFICATION 與選型決策。
每一項以「決策 / 理由 / 已評估的替代方案」三段式呈現。

---

## 1. 代理核心：使用 LiteLLM 的哪一個介面？

**決策**：使用 **LiteLLM Proxy Server**（`litellm[proxy]`），以 YAML 設定
模型路由與底層憑證；在其前置加上 FastAPI 的請求攔截中介層處理憑證驗證與
請求改寫。

**理由**：
- LiteLLM Proxy 已內建多供應商抽象、用量計費勾子、OpenAI 相容路徑，省去
  自行實作 Azure OpenAI 客戶端
- Proxy 形態可獨立 scale、容易容器化、與 K8s 部署模型自然對齊
- 願景階段 3 要計算費用 — LiteLLM Proxy 已有費用估算欄位可沿用

**已評估**：
- **LiteLLM SDK（library 模式）內嵌**：簡單但等於自行寫 proxy，失去
  LiteLLM 多年累積的供應商錯誤處理
- **直接呼叫 Azure OpenAI SDK**：違反「契約優先 + 可替換性」精神，未來
  難以擴充其他供應商

---

## 2. 憑證攔截：在 LiteLLM 之前還是之後？

**決策**：在 LiteLLM Proxy **之前**以 FastAPI middleware（或反向代理 router）
攔截憑證；驗證通過後，把對應分配的「資源綁定模型名稱」與內部高權限
service token 注入 request，再轉發到 LiteLLM Proxy。

**理由**：
- 「分配憑證」是本專案發行的對外抽象，不能與 LiteLLM 內部 virtual keys
  混為一談 — 雖然 LiteLLM 本身有 virtual key 機制，但「分配狀態」「資源
  綁定」「審計欄位」是我們自有領域，不該綁進 LiteLLM 配置
- 攔截在前可確保撤回邏輯獨立可演進，未來加入 SSO / quota 不需動 LiteLLM
- 失敗時可立即回應，避免 LiteLLM 把錯誤翻譯成供應商錯誤格式

**已評估**：
- **直接使用 LiteLLM virtual keys**：太緊耦合，撤回 SLO 與審計欄位受限於
  LiteLLM 的 schema；且 virtual keys 配置變更需重啟 / reload
- **在 LiteLLM 之後做後處理**：失敗請求已消耗上游配額，違反 FR-008

---

## 3. 資料持久化：選型與遷移

**決策**：**SQLAlchemy 2.x + Alembic + Pydantic v2**。生產用 PostgreSQL 15+，
本機開發與 CI 可用 SQLite。

**理由**：
- 需要持久化分配狀態（FR-004）、撤回需立即生效（FR-007）→ 必須是
  ACID + 跨副本一致的儲存。Postgres 是最務實選擇
- SQLAlchemy 2.x 的 typed mappings 與 Pydantic v2 相容良好
- Alembic 提供宣告式 schema 演進，便於未來階段擴張欄位

**已評估**：
- **Redis 為主儲存**：撤回快但缺乏可審計性與耐久性，會違反「不依賴 token
  簽章過期」的精神
- **MongoDB**：schema 演進彈性更高，但事務性、JOIN 與審計查詢遠不如 RDBMS

---

## 4. 撤回的「立即生效」如何實作

**決策**：每次代理呼叫都先**查 DB** 取得分配當前狀態（active / revoked），
不快取狀態於進程內。SLO 5s 由 DB 查詢延遲 + 副本間複製延遲共同決定，初期
單 primary 即可滿足。

**理由**：
- 最簡單、最不易出錯 — 與 YAGNI 一致；50 active 分配、100 calls/min 的
  規模下，每次呼叫查 DB 的開銷可忽略
- 未來若加 read replica 或快取（cache invalidation 是難題），仍可在不影響
  介面契約的前提下優化

**已評估**：
- **進程內快取 + pub/sub 通知撤回**：複雜度大幅上升，違反 YAGNI；初期不必要
- **JWT + 短 TTL**：撤回會「等待 token 過期」，違反 FR-007「不依賴自然過期」

---

## 5. 機密保護：如何驗證錯誤路徑也不洩漏 key

**決策**：在 logging 層加 **redaction filter**，比對設定中的 Azure OpenAI key
字串並以 `***` 取代；同時加一條**契約測試**：以故意觸發各類錯誤（無效 token、
模型不存在、上游 5xx）跑全套對外端點，掃描回應 body / headers / 日誌中
不得出現 key 明文。

**理由**：
- 防禦深度：即便 LiteLLM 或 SDK 將 key 寫入錯誤訊息，redaction filter 也能
  在 log/response 邊界擋住
- 契約測試確保 SC-003（key 洩漏次數 = 0）可被機器驗證、CI 強制

**已評估**：
- **僅靠程式碼審查**：不可被機器強制，會在演化中漏網
- **僅靠 redaction filter**：若 filter bug，沒有檢查能發現；雙保險為佳

---

## 6. 部署：Helm vs Kustomize

**決策**：**Helm chart** 為主要交付物。本機開發以 docker-compose；K8s 部署
使用 Helm。

**理由**：
- Helm 在 CNCF 生態最普及，組織 IT 流程通常已熟悉
- 參數化（values.yaml）天然支援多環境
- 回滾路徑明確（`helm rollback`），對應 FR-018 的「≤ 5 分鐘回到前一版」

**已評估**：
- **Kustomize**：overlay 模型優雅但對「LiteLLM 版本變數化」較不直覺
- **裸 manifests**：簡單但缺少版本管理與回滾原語

---

## 7. LiteLLM 鏡像自動更新：工具鏈

**決策**：**Renovate** 監看 `values.yaml` 中的 LiteLLM image tag → 開 PR →
CI（lint + test + 契約測試 + smoke 整合）→ 合併後由 GitOps（**Argo CD** 或
Flux）自動同步至叢集。回滾以 `helm rollback` 為主路徑，必要時可手動釘版本。

**理由**：
- Renovate 對容器鏡像支援好，且可設定每週固定時段 PR，避免高頻打擾
- 安全性 patch 走相同流程，只是觸發時機不同（CVE 公佈時手動加速合併）
- Argo CD 提供視覺化滾動狀態與回滾按鈕，符合運維友善

**已評估**：
- **Dependabot**：對 Helm values 內鏡像 tag 支援不如 Renovate 精細
- **無 GitOps 直接 `helm upgrade`**：可行但失去版本可追溯性

---

## 8. 本機開發體驗

**決策**：`docker-compose.yml` 啟 Postgres + 本服務；服務以 `uv run` 或
`python -m ai_api` 在本機直接執行（不需 K8s），透過環境變數注入 Azure
OpenAI key（個人開發者可用自己的 Azure OpenAI sandbox）。

**理由**：
- 願景明確「不要求本機跑 K8s」
- docker-compose 啟 Postgres 比安裝原生 Postgres 摩擦更低
- 服務本身在本機跑（非容器化），有最佳除錯體驗（pdb、reload）

**已評估**：
- **全容器化本機**：方便但 reload 與除錯體驗差
- **SQLite for everything**：本機可用，但與生產 Postgres 行為差異會被掩蓋
  （見 constitution「整合測試覆蓋外部依賴」），故 CI 一定要跑 Postgres

---

## 9. 測試策略：分層與覆蓋率

**決策**：三層測試。

| 層 | 工具 | 內容 |
|---|---|---|
| Unit | pytest + mocks | 純函數、credential 生成、redaction filter |
| Contract | schemathesis + 自寫斷言 | OpenAPI 一致性 + 錯誤路徑 key 不洩漏掃描 |
| Integration | pytest + testcontainers + Azure OpenAI sandbox | 真實 Postgres、真實上游、撤回 SLO 量測 |

CI 必跑全部三層；本機開發只跑 unit + contract 即可，integration 在 push 前手動跑。

**理由**：
- 與 constitution III、IV 一致
- testcontainers 讓整合測試可重現、CI 友善

---

## NEEDS CLARIFICATION 解決狀態

spec.md 與 plan.md 中所有 NEEDS CLARIFICATION 已全數收斂為決策；剩餘細節
（具體欄位、HTTP 路徑、錯誤碼）見 `data-model.md` 與 `contracts/openapi.yaml`。
