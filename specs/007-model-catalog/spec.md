# Feature Specification: 階段 4 — 模型目錄 + 多面向 Filter

**Feature Branch**: `007-model-catalog`
**Created**: 2026-05-23
**Status**: Draft
**Input**: User description: "階段 4 模型目錄 + 多面向 filter（類 Azure Foundry）— 模型為第一公民、YAML 載入、faceted filter API、active member 可看"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 我要做圖，請告訴我可選哪些模型 (Priority: P1)

不熟 AI API 的成員想做「文字生圖」。打開 model catalog，挑一個 modality
output 含 image 的 filter，立刻看到所有可用模型（首版只有 dall-e-3），
點進去看到 example_request（curl + JSON）可直接複製貼上。

**Why this priority**：本階段最核心承諾 — vision「不熟 LLM API 的成員看完
能自行開始試用」。失去此能力本階段沒理由存在。

**Independent Test**：
`GET /catalog/models?modality_output=image` → 回傳僅含 image-output 模型；
`GET /catalog/models/azure%2Fdall-e-3` → 回傳含可運行的 example_request。

**Acceptance Scenarios**:

1. **Given** YAML 已載入含 dall-e-3、gpt-4o、whisper-1，**When**
   `GET /catalog/models?modality_output=image`，**Then** 僅 dall-e-3 出現。
2. **Given** 同上，**When** `GET /catalog/models?modality_input=text&modality_output=text`，
   **Then** gpt-4o 出現、dall-e-3 與 whisper-1 不出現。
3. **Given** 某模型有 example_request，**When** 點 detail 端點，**Then** 回傳
   `example_request` 欄位含完整 curl 字串 + JSON body 範例。

---

### User Story 2 - 我要找支援 vision 又有 function-calling 的便宜模型 (Priority: P1)

進階使用者已知道自己需要哪幾個 capability，想 AND filter：
「modality_input 含 image、capabilities 含 function-calling、cost_tier=low」
應該只命中 gpt-4o-mini（首版設定）。

**Why this priority**：多選 capability 的 AND 語意是「filter」存在的核心 —
若回 OR 結果，跟「列表 + 客戶端篩選」沒兩樣，目錄價值大減。

**Independent Test**：
`GET /catalog/models?modality_input=image&capability=function-calling&capability=vision&cost_tier=low`
回傳 1 個結果（gpt-4o-mini）。

**Acceptance Scenarios**:

1. **Given** gpt-4o (high cost) 與 gpt-4o-mini (low cost) 都有 vision +
   function-calling capability，**When**
   `?capability=vision&capability=function-calling&cost_tier=low`，**Then**
   僅 gpt-4o-mini 命中。
2. **Given** 重複 `capability` 是 AND（必須全具備），**When** 給某模型缺一個
   要求的 capability，**Then** 該模型不出現。
3. **Given** 跨欄位 filter，**When** `?modality_input=text&capability=function-calling`，
   **Then** 兩條件 AND，少一個就排除。
4. **Given** 未指定任何 filter，**When** `GET /catalog/models`，**Then** 回傳
   全部 active 模型（deprecated 與 status!=active 預設排除）。

---

### User Story 3 - UI 想知道有哪些 filter 值可選 + 各幾個 (Priority: P1)

3b SPA 想建 sidebar：「modality input: text (8), image (3), audio (1)」。
需要一個端點直接拿這份 faceted 計數，不需要前端自己 group。

**Why this priority**：facet API 是「目錄」與「list 端點」的關鍵差異；3b 沒
這個就會 N+1 query 或硬寫 enum，違背「目錄是描述性資料」精神。

**Independent Test**：
`GET /catalog/filters` 回所有 filter dimension（modality_input、
modality_output、capabilities、cost_tier、recommended_for）及每個 value 的
命中數。

**Acceptance Scenarios**:

1. **Given** YAML 已載入 8 個模型，**When** `GET /catalog/filters`，**Then**
   回 JSON：
   ```json
   {
     "modality_input": {"text": 8, "image": 3, "audio": 1},
     "capabilities": {"chat": 6, "vision": 3, "function-calling": 4},
     "cost_tier": {"low": 3, "medium": 3, "high": 2},
     "recommended_for": {"summarization": 4, "translation": 4}
   }
   ```
2. **Given** 一個 dimension 完全沒人有，**When** facet 計算，**Then** 該
   dimension 仍出現於回應但 value 為空 dict（穩定 schema）。

---

### User Story 4 - 管理員每月手動同步 Azure 新模型 (Priority: P2)

Azure 每月可能發新模型。管理員寫一份 YAML、跑 CLI 載入；同 slug 自動 upsert，
不需手動刪舊資料。

**Why this priority**：催生 catalog 長期可維護；首版內容會過時，沒有低摩擦
更新流程，catalog 半年就過時不可用。

**Independent Test**：
跑 `python -m ai_api.cli.load_models deploy/catalog/azure-2026-06.yaml` 兩次，
不報錯（idempotent）；改 YAML 內某模型的 description，第二次 load 後 detail
端點回傳新 description。

**Acceptance Scenarios**:

1. **Given** 空目錄，**When** 載入 8 model YAML，**Then** DB 多 8 筆。
2. **Given** 同 YAML 再載一次，**When** 跑完，**Then** DB 仍 8 筆（無重複，
   無錯誤），且 `updated_at` 更新。
3. **Given** YAML 改了某模型 description + 加入新 capability，**When** 載入，
   **Then** 對應 row 的 description 與 capabilities 更新。
4. **Given** YAML 移除某模型（reorder），**When** 載入，**Then** 已存在但未
   在 YAML 列出的模型**保持原樣**（不刪除，避免事故性 wipe）；管理員若要
   下架，改 status 即可。

---

### User Story 5 - 棄用模型不該被新使用者用到 (Priority: P2)

某模型被 Azure 公告即將停服。管理員把 YAML 該 model `status: deprecated`
重新載入；列表預設不再回傳；但詳細查詢仍可看到（含 deprecation note），
方便既有使用者了解何時換。

**Why this priority**：避免新分配跑到要下架的模型；同時讓現有使用者有遷移
緩衝。

**Independent Test**：
`GET /catalog/models` 不含 deprecated；`GET /catalog/models?include_deprecated=true`
含；`GET /catalog/models/{deprecated_slug}` 200 + deprecation note。

**Acceptance Scenarios**:

1. **Given** gpt-4 (deprecated) 與 gpt-4o (active)，**When**
   `GET /catalog/models`，**Then** 僅 gpt-4o。
2. **Given** 同上，**When** `?include_deprecated=true`，**Then** 兩個都回。
3. **Given** 直接查 deprecated slug，**When** detail，**Then** 200 含
   `deprecation_note` 欄位（如「Azure 將於 2027-01 停服」）。

### Edge Cases

- **YAML schema 錯誤**（如 modality_input 含未知值）：CLI 載入失敗、明確錯誤
  訊息指出哪一行哪個欄位；DB 不留半改半的狀態。
- **slug 衝突檢測**：slug 是唯一識別；YAML 內重複 slug 須報錯。
- **filter 值不存在**：如 `?cost_tier=ultra` → 該 cost_tier 不存在；回 200 +
  空陣列（不是 400），方便 UI 試 filter 不被驚擾。
- **filter 大小寫**：`modality_input=Text` vs `text` — 後端正規化小寫比對。
- **空目錄**：`GET /catalog/models` 回空陣列、`GET /catalog/filters` 回空
  dict 結構（不是 404）。
- **PriceList 對齊**：catalog model.slug 與 PriceList 的 `provider/model`
  不一定 1:1（catalog `azure/gpt-4o-mini` ↔ PriceList provider=azure
  model=gpt-4o-mini）；對齊 SOP 寫 docs。

## Requirements *(mandatory)*

### Functional Requirements

#### 資料模型
- **FR-001**: 系統 MUST 維護一份「模型目錄」資料表 `model_catalog`，每筆
  含 slug、provider、display_name、family、description、modality_input
  (list)、modality_output (list)、capabilities (list)、context_window (int)、
  cost_tier (low/medium/high)、recommended_for (list of scenario tags)、
  tags (list)、example_request (json)、official_doc_url、status
  (active/preview/deprecated)、deprecation_note、created_at、updated_at。
- **FR-002**: `slug` 為 PRIMARY KEY，命名規則 `<provider>/<model_name>`。

#### YAML 載入
- **FR-003**: 提供 CLI `python -m ai_api.cli.load_models <yaml_path>`，
  upsert by slug；新 slug → INSERT；既有 slug → UPDATE 全部欄位、保留
  `created_at`、更新 `updated_at`。
- **FR-004**: YAML schema 驗證失敗（缺欄位、modality/capability/cost_tier 值
  超出列舉、slug 衝突）MUST 在 transaction 內 abort + 明確錯誤訊息；DB
  維持載入前狀態。
- **FR-005**: 未在新 YAML 出現但 DB 已有的 model **不刪除**（idempotent 防
  事故性 wipe）；下架請改 status。

#### Filter API（核心）
- **FR-006**: `GET /catalog/models` 回 list；無 filter 時回所有 `status=active`
  的 model（依 slug 排序，確定性）。
- **FR-007**: filter 規則：
  - list-valued field（capabilities、modality_input/output、recommended_for、
    tags）：query string 重複該 key 表示 **AND**（如
    `?capability=vision&capability=function-calling` = 兩者都有）
  - single-valued field（cost_tier、provider、family、status）：單一值
  - 跨欄位 AND
- **FR-008**: filter 值大小寫不敏感（後端比對前 normalize 小寫）。
- **FR-009**: `?include_deprecated=true` 開關才回 deprecated；預設 false。
- **FR-010**: 無命中時回 `200` + 空陣列；不回 4xx。
- **FR-011**: 數值 filter：`?min_context_window=N`（≥ N tokens）。

#### Detail API
- **FR-012**: `GET /catalog/models/{slug}` 回單筆完整（含 example_request、
  deprecation_note）；slug 不存在 → 404。
- **FR-013**: 即使 status=deprecated 也可 detail 查到（不過濾）。

#### Filter facet API
- **FR-014**: `GET /catalog/filters` 回 faceted dict：對每個可 filter 的
  dimension，回該 dimension 的所有 value 與 active model 計數。dimension
  涵蓋至少：modality_input、modality_output、capabilities、cost_tier、
  recommended_for、family、tags。
- **FR-015**: facet 計數 MUST 排除 deprecated（與預設列表行為一致）。
- **FR-016**: facet 結構穩定：即使某 dimension 全 0，仍回該 dimension key
  + 空 dict。

#### 權限
- **FR-017**: 三個 catalog 端點 MUST 要求 active member 登入（既有 session
  cookie）；無認證 → 401；status=disabled 的 member → 403。**不需 admin**。

#### 不在本階段範圍
- **FR-018** (NON-GOAL): 從 Azure / LiteLLM 自動同步 model 清單。
- **FR-019** (NON-GOAL): 「智慧推薦」依輸入語意找模型。
- **FR-020** (NON-GOAL): UI / 視覺呈現（留 3b）。
- **FR-021** (NON-GOAL): 多語言描述（首版只繁中）。
- **FR-022** (NON-GOAL): 即時定價（cost_tier 而非絕對價）— 整合 PriceList
  留未來。
- **FR-023** (NON-GOAL): 整合到「建立 allocation」流程作為 model picker
  （留 3b UI）。

### Key Entities

- **ModelCatalog**（新表）：
  - 欄位如 FR-001
  - 列舉值（保存於 `Settings` 或 enum class）：
    - `modality_input` / `modality_output`: text / image / audio / video / embedding
    - `capabilities`: chat / vision / function-calling / json-mode / tool-use /
      streaming / reasoning / embedding / fine-tuning
    - `cost_tier`: low / medium / high
    - `status`: active / preview / deprecated
    - `recommended_for`: 開放標籤（不嚴格限制；常見：summarization /
      translation / stt / tts / image-gen / code / chat / agent / embedding /
      classification）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 首版 YAML 含 ≥ 8 個 Azure OpenAI 主力模型（gpt-4o、gpt-4o-mini、
  o1-mini、o3-mini、text-embedding-3-small、text-embedding-3-large、
  dall-e-3、whisper-1、tts-1）。
- **SC-002**: 多選 AND 正確性：seed 上述 8 模型，
  `?capability=vision&capability=function-calling&cost_tier=low` 命中
  剛好 1 個（gpt-4o-mini）。
- **SC-003**: facet 結構穩定：對空 DB 與 8-model DB 兩種狀態，
  `GET /catalog/filters` 都回相同的 dimension key 集合。
- **SC-004**: idempotent 載入：對同 YAML 跑 CLI 兩次，第二次無錯誤且 DB
  row 數不變。
- **SC-005**: 棄用隔離：將某 model status 改 deprecated 再載入，預設
  `GET /catalog/models` 不再回該 slug，但 detail 仍可查到含
  deprecation_note。
- **SC-006**: 既有 167 tests + 後續新增測試全綠（無回歸）。
- **SC-007**: 所有 FR 在 git 歷史可見「test commit 早於 impl commit」
  （延續 TDD 紀律 / SC-008 慣例）。

## Assumptions

- **內容由人工 YAML 維護**：每月新 Azure 模型由管理員手動更新 YAML 並 PR。
- **active member 可看**：catalog 是描述性、非機密資訊；未開放給未登入用戶
  以避免被當「Azure 模型對外披露頁」濫用。
- **deprecated 不刪除**：歷史 model 永久保留於 DB，僅以 status 隔離；既有
  分配若用到 deprecated model 仍可運作（proxy 不擋）。
- **cost_tier 由人工註於 YAML**：與 PriceList 解耦；缺對應 PriceList 時
  cost_tier 仍可用。
- **多 provider 預留欄位**：首版只 azure；schema 已留 provider 欄位，未來
  加入新供應商無需 migration。
- **filter 不做模糊比對**：`?capability=vision` 必須精確匹配 list 內字串；
  不支援 LIKE / 子字串。
- **example_request 為描述性 JSON**：spec 不規範格式具體欄位；CLI 載入時
  不驗證內容合法性（只驗 schema 完整性）。
