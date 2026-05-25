# Feature Specification: Multi-Provider Support with Admin-Managed Credentials and Tag-Based Access

**Feature Branch**: `012-multi-provider-access`
**Created**: 2026-05-25
**Status**: Draft
**Input**: User description: "Multi-provider LLM support with admin-managed encrypted credentials and tag-based access rules"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 多 Provider 代理可用 (Priority: P1)

組織需要透過同一個入口存取多家 LLM 供應商（首批：Azure OpenAI、OpenAI 雲端、
Anthropic、Gemini）。管理員設定一家以上 provider 的 API key 之後，成員透過
分配到的 token 即可呼叫任一家 provider 的 model；對外回應格式統一為 OpenAI
相容 schema，使呼叫端不需為每家寫不同程式。

**Why this priority**: 這是整個 feature 的根本價值；沒有多 provider 代理，
其他子功能（credential UI、tag policy）都失去意義。也是組織採購多家 AI
服務後的最直接訴求。

**Independent Test**: 管理員以 fixture 方式注入 2 家 provider credential
（例：Azure OpenAI + Anthropic），對 catalog 加入各家 1 個 model，建立 1 筆
allocation 並用同一個 token 分別呼叫兩家 model 的 chat completion endpoint，
兩次呼叫都回 200 且回應為 OpenAI 相容 schema。

**Acceptance Scenarios**:

1. **Given** 管理員已加入 Azure OpenAI 與 Anthropic 的 credential、catalog
   有 `gpt-4o-mini`（Azure）與 `claude-3-5-sonnet`（Anthropic）、成員擁有
   一筆 active allocation，**When** 成員用該 token 呼叫
   `POST /v1/chat/completions` model 指定 `gpt-4o-mini`，**Then** 系統回 200
   且使用 Azure credential 完成 upstream 呼叫
2. **Given** 同上前置條件，**When** 成員改 model 為 `claude-3-5-sonnet`，
   **Then** 系統回 200 且使用 Anthropic credential 完成 upstream 呼叫
3. **Given** 一個 model 設定為 Anthropic provider，但管理員從未加入 Anthropic
   credential，**When** 成員呼叫該 model，**Then** 系統以 `provider_unavailable`
   錯誤回 503，不洩漏內部狀態

---

### User Story 2 — Admin 在 UI 管理 Provider Credential (Priority: P2)

管理員不再需要修改環境變數或 K8s Secret 才能新增 / 替換 provider key；
透過 admin web UI 即可建立、查看（僅 fingerprint）、rotate、停用 provider
credential。建立或 rotate 時系統一次性顯示明文 key（同 allocation token
模式），離開頁面後永遠不可再查；底層儲存全程加密。

**Why this priority**: User Story 1 在「fixture 注入」狀態下即可成立，但
要讓真實組織用，必須讓管理員自服務式地管 credential，不能仰賴 ops 改設定。

**Independent Test**: 以 admin 身分登入 UI，於 `/admin/providers` 新增一筆
OpenAI credential（貼 plaintext key），看到一次性 banner 顯示明文；重新整理
頁面後僅看到 fingerprint。按 rotate 取得新明文、舊明文立即失效（用 fixture
方式測試 upstream 呼叫）。按停用後該 credential 不再被 routing 選取。

**Acceptance Scenarios**:

1. **Given** admin 已登入 UI，**When** 至 `/admin/providers` 按「新增」
   選擇 provider 類型、貼上 plaintext key、按確認，**Then** 系統儲存
   加密 key、寫入稽核事件，並一次性 banner 顯示 plaintext key 與
   fingerprint
2. **Given** 一筆已建立的 credential，**When** admin 重新整理列表，
   **Then** 看到 provider 類型、label、fingerprint、建立日期、狀態，
   **但不顯示明文**
3. **Given** 一筆 active credential，**When** admin 按 rotate，**Then**
   系統產生新 plaintext key、立即生效於 routing；舊 key 立即失效；寫入
   `provider_credential_rotated` 稽核事件
4. **Given** 一筆 active credential，**When** admin 按停用，**Then**
   依賴它的 model 對成員立即不可用；後續呼叫回 `provider_unavailable`

---

### User Story 3 — Tag-based 存取規則（admin 批次授權） (Priority: P3)

管理員為成員打 tag（例：`eng`、`pm`、`contractor`、`trial`），並為 catalog
中的每個 model 設定「預設可見性」與「允許 / 禁止 tag」。改 tag 即時影響成員
能看到與呼叫到哪些 model；不需要對每個 model × 每個 member 逐一指定。

**Why this priority**: User Story 1+2 已能讓所有授權成員看到所有 model；
P3 加入細緻權限管控，是企業必需但非 MVP-blocking 的能力。

**Independent Test**: 建 2 個 member（alice、bob），alice 打 tag `eng`，
bob 不打。Catalog 中 `claude-3-5-sonnet` 設 `allowed_tags=["eng"]`。
alice 呼叫 `GET /catalog/models` 看到 claude；bob 看不到。bob 直接呼叫
proxy 試該 model 被拒（防禦性二次檢查）。

**Acceptance Scenarios**:

1. **Given** alice 有 tag `eng`、bob 無 tag、`claude-3-5-sonnet` model
   設 `allowed_tags=["eng"]`，**When** alice 呼叫 `GET /catalog/models`，
   **Then** 列表包含 `claude-3-5-sonnet`
2. **Given** 同上，**When** bob 呼叫 `GET /catalog/models`，**Then** 列表
   不含 `claude-3-5-sonnet`
3. **Given** 同上，**When** bob 直接呼叫 `POST /v1/chat/completions` 指定
   `claude-3-5-sonnet`，**Then** 系統回 403 `model_forbidden`，寫入稽核
4. **Given** admin 將 bob 加入 `eng` tag，**When** bob 重新呼叫 catalog
   list，**Then** 立即看到 `claude-3-5-sonnet`（無需重新登入或等候）
5. **Given** admin 把 `claude-3-5-sonnet` 設成 `denied_tags=["contractor"]`、
   alice 同時有 `eng` 與 `contractor` tag，**When** alice 呼叫，**Then**
   被拒（deny 優先於 allow）
6. **Given** admin 在 admin UI 多選 5 個 member、按「Apply tag」選 `eng`，
   **When** 操作完成，**Then** 5 個 member 全部立即擁有 `eng` tag，寫入
   單筆批次稽核事件

---

### User Story 4 — 既有 Azure 設定遷移到 DB 管理 (Priority: P4)

組織既有 `AZURE_OPENAI_API_KEY` env / Helm value 已在 production 運作，
不能在升級時讓服務斷線。提供工具 / 流程讓 admin 把既有 env 中的 key 灌入
DB 成為一筆受管 credential，並安全地從 Helm values 移除 env，過程中不影響
進行中的呼叫。

**Why this priority**: 不是新功能但是現場升級必要；沒做完，組織不敢上線
new release。

**Independent Test**: 在已有 `AZURE_OPENAI_API_KEY` env 的環境下，執行
migration 命令 → DB 出現一筆 Azure provider credential、稽核事件記錄
「migrated from env」；停止 env 後重新呼叫 proxy 仍正常。

**Acceptance Scenarios**:

1. **Given** 部署環境有 `AZURE_OPENAI_API_KEY` env，且 DB 無對應 credential，
   **When** admin 執行 migration 命令，**Then** DB 新增一筆受管的 Azure
   credential、稽核事件標記 `source=env_migration`
2. **Given** migration 完成，**When** admin 從 Helm values 移除 env
   並重新 deploy，**Then** 服務不重啟也能正常代理 Azure 呼叫（DB credential
   已生效）
3. **Given** 同時存在 env 與 DB credential，**When** proxy 接到 Azure 呼叫，
   **Then** 優先使用 DB credential，env 僅作為 fallback（讓 migration 期間
   平滑切換）

---

### Edge Cases

- **加密金鑰遺失**：若加密金鑰遺失或被 rotate，所有現有 credential 立即
  不可解密；系統啟動時必須**拒絕啟動**並寫明確錯誤訊息，而非以「假裝沒事」
  方式啟動後 runtime 才崩
- **同 provider 多 credential**：admin 加同一家 provider 多把 key 時，
  系統需要決定挑選策略；首版採 round-robin（記錄 `last_used_at`），
  並允許 label 區分用途（例：「team-a-key」、「emergency-backup」）
- **Tag 衝突**：member 同時有 allow 與 deny 命中的 tag → deny 優先
- **Catalog 載入時 provider unknown**：YAML 指定不在已支援清單的 provider
  → 載入 fail-fast，error message 列出支援清單
- **Member 被 disable 後 tag 仍存在**：disabled member 即使有任何 tag 也
  完全看不到任何 model（既有 disable 行為優先）
- **Rotation 競賽**：admin A 與 admin B 同時 rotate 同一 credential →
  後到者覆蓋前到者，兩次 rotation 都寫入稽核
- **Provider API 暫時故障**：upstream 5xx 時不要把 credential 標為 disabled；
  區分「key 無效」（401/403）與「服務暫時故障」（5xx），前者可以選擇性
  quarantine、後者重試
- **Model 改 provider**：catalog 中既有 model 的 `provider` 欄被改（例
  從 Azure 改到 OpenAI 雲端），既有 allocation 仍 work（routing 用即時 lookup）

## Requirements *(mandatory)*

### Functional Requirements

**多 provider 代理**
- **FR-001**: 系統 MUST 支援以下 provider 各至少一個 model：Azure OpenAI、
  OpenAI cloud、Anthropic、Gemini
- **FR-002**: 系統 MUST 對所有 provider 提供 OpenAI 相容的對外 response
  schema（chat completions endpoint），呼叫端不需切換 SDK
- **FR-003**: 系統 MUST 依 model 在 catalog 中的 `provider` 欄位決定使用
  哪家 provider 的 credential，而非靠呼叫端指定
- **FR-004**: 當 model 對應 provider 沒有 active credential，系統 MUST
  回 503 `provider_unavailable`，不洩漏內部狀態

**Credential 管理**
- **FR-005**: 系統 MUST 提供 admin 介面新增、列出、rotate、停用 provider
  credential
- **FR-006**: API key 在儲存層 MUST 加密，明文僅存於建立 / rotate 當下的
  API response，**且僅顯示一次**
- **FR-007**: 列表頁與 detail 頁 MUST NOT 顯示明文 key；只顯示 fingerprint
  （hash 前 N 碼，至少 8 碼）
- **FR-008**: 系統 MUST 為以下事件寫入稽核：`provider_credential_created`、
  `provider_credential_rotated`、`provider_credential_disabled`、
  `provider_credential_used_first_time`
- **FR-009**: 同一 provider 可同時有多筆 active credential；系統 MUST 採
  round-robin 挑選，並紀錄 `last_used_at`

**加密金鑰**
- **FR-010**: 加密金鑰 MUST 由 K8s Secret 提供（與 Phase 2.5 既有 cookie key
  管理模式一致）；Helm chart MUST 將該 Secret 標示為**必要**，缺漏時 pod
  拒絕啟動。Dev / 本機環境允許從 env var 載入以方便開發，但 production 部署
  documentation MUST 強制要求 K8s Secret 來源
- **FR-011**: 加密金鑰遺失或無法解密時系統 MUST 拒絕啟動並以明確錯誤
  指出原因，而非以降級模式繼續

**Tag-based 存取規則**
- **FR-012**: 系統 MUST 提供 admin 介面建立、刪除 tag；tag 名稱在組織內 unique
- **FR-013**: 系統 MUST 允許 admin 為 member 加 / 移除 tag，包含批次操作
  （多選 member → apply tag）
- **FR-014**: catalog 中每個 model MUST 有 `default_access` 欄位，值為
  `open`（所有通過 credential gate 的成員都能看到，除非命中 `denied_tags`）
  或 `restricted`（只有命中 `allowed_tags` 的成員能看到）。建立 model 時
  admin **MUST 明確指定**（無系統層級預設），catalog YAML schema 中該欄為
  必填；CLI loader 對缺欄位的 model 載入失敗並提示
- **FR-015**: 系統 MUST 支援 model `allowed_tags`（list）與 `denied_tags`
  （list）；當 member tag 同時命中兩者時，deny 優先於 allow
- **FR-016**: catalog list / detail endpoint 對成員 MUST 套用兩道過濾：
  credential gate（model 對應的 provider 至少有 1 筆 active credential）
  ∩ access policy（default + allow/deny tag）
- **FR-017**: proxy 呼叫時 MUST 在 routing 前再次檢查存取規則（防禦性
  二次檢查），不依賴前端過濾
- **FR-018**: tag 變更 MUST 立即生效（不需 cache invalidation 流程）

**遷移**
- **FR-019**: 系統 MUST 提供升級路徑把既有 `AZURE_OPENAI_API_KEY` env 灌入
  DB 成為受管 credential，且**最終狀態 env 完全不再被讀取**。為達 SC-007
  零停機，升級分兩個 release：
  - **Release N+1（transitional）**：CLI migration 命令；proxy 讀 credential
    時 DB 優先、找不到才 fallback 到 env（過渡期共存）
  - **Release N+2（final）**：fallback 路徑從程式碼移除；proxy 只從 DB 讀
    credential。升級時 admin MUST 完成驗證步驟（grep 確認 env 已從 Helm
    values 移除 + DB 有對應 credential + 一次成功 proxy 呼叫）才視為升級完成

**橫切**
- **FR-020**: 所有新 endpoint MUST 套用既有 admin / member 認證模式
  （Member.is_admin 雙軌、CSRF 保護、不變更）
- **FR-021**: 既有 allocation token 不需重發；現有 allocation 在 Phase 5
  上線後立刻能用所有授權 model

### Key Entities

- **ProviderCredential**：admin 為某家 LLM 供應商加入的一筆 API 憑證。
  屬性：provider 類型（Azure OpenAI / OpenAI / Anthropic / Gemini ...）、
  label（人類可讀標記）、加密後 key、key fingerprint（hash 前 N 碼）、
  選填 base_url override、額外設定（如 Azure 的 api_version、Gemini 的
  project / location）、建立資訊（誰、何時）、狀態（active / disabled）、
  `last_used_at`
- **MemberTag**：成員與標籤的多對多關聯。屬性：member、tag 名稱、
  加標者、時間
- **Tag**（可選為簡單字串去重）：組織內可用的 tag 名稱清單；首版可以
  直接由 MemberTag 的 distinct 推導，未必需要獨立表
- **ModelCatalog（擴充既有）**：新增 `provider` 欄（哪家供應商）、
  `default_access` 欄（open / restricted）、`allowed_tags`（list）、
  `denied_tags`（list）。既有欄位不變

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理員首次設定 4 家 provider 中任 2 家、加入對應 model、
  分配給一名成員的全流程，可在 **10 分鐘內**完成（不含 K8s deploy）
- **SC-002**: 成員用同一個 token 呼叫 2 家不同 provider 的 model，
  **兩次都成功**且 response schema 一致
- **SC-003**: 管理員停用一筆 credential 後，相關 model 的呼叫在
  **10 秒內**全節點生效拒絕（既有 revocation SLO 一致）
- **SC-004**: 管理員批次為 10 個 member 打 tag 的操作，從按下確認到所有
  member 生效**少於 5 秒**，UI 不需手動 refresh
- **SC-005**: 任何 4xx / 5xx 錯誤訊息、日誌、稽核紀錄中**完全找不到**
  provider plaintext key（自動化 grep 測試通過）
- **SC-006**: 加密金鑰遺失情境下，pod **拒絕啟動**且 K8s event 顯示明確
  原因，不會以「半啟動」狀態跑
- **SC-007**: 從既有 Azure env 部署升級到 Phase 5 全流程的 downtime 為
  **0 秒**——升級流程為 (1) 部署新版（DB 與 env 都有 key，但程式優先讀 DB
  並 fallback 到 env），(2) 跑 migration CLI 把 env 灌入 DB，(3) 部署移除
  env 的版本（程式拔掉 fallback 路徑）；步驟之間不需停機

## Assumptions

- 組織內部使用，使用者數預期百人量級；不需考慮百萬 tag 規模
- 「OpenAI 相容」response schema 以業界廣為採用的 OpenAI ChatCompletion
  格式為對外契約（呼叫端 SDK 互通基準）
- 既有 model catalog 表可擴欄位
- 既有稽核事件型別清單可繼續擴值
- K8s 部署環境已 ready；本 feature 不引入新 infra 元件除非 FR-010 選 KMS
- 首版**不**支援 self-hosted provider（Ollama / vLLM）UI 與 health-check；
  留更後階段
- 首版**不**支援複合條件式 rule matcher；只支援 tag 集合 AND / NOT
- 首版**不**支援 provider failover 與按 provider 切配額池
- 既有 Phase 2.5 provider allowlist 在 Phase 5 仍生效：未在 allowlist 中
  的 provider 即使 admin 加了 credential 也不能被呼叫
- 既有 Phase 3c 自適應配額池仍以全域 token 計，多 provider 不分池
