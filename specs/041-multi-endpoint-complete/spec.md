# Feature Specification: 多端點全開（圖片 / rerank / TTS / STT）+ 目錄誠實

**Feature Branch**: `041-multi-endpoint-complete`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "多端點全開（圖片 / rerank / TTS / STT）+ 目錄誠實"

## User Scenarios & Testing *(mandatory)*

本功能把「多端點開放」主題**完整收尾**：補齊圖片生成、重排序（rerank）、語音合成（TTS）、語音轉文字（STT）四個成員端點，並還掉「非 chat 模型在管理介面被假裝成 chat」的目錄誠實債。每個端點都走與聊天/embedding/OCR **同一條前置檢查**，以**各自的原生單位計量計費**並歸戶分配。

### User Story 1 - 成員呼叫圖片生成模型（Priority: P1）🎯 MVP

成員持有圖片生成模型的金鑰，送一段文字提示，取回生成的圖片（以資料形式回傳，非二進位檔案串流），用量以 token 計量計費、歸戶分配。

**Why this priority**: 圖片是需求最廣、最低風險的新端點——計費沿用既有 token 機制（這類模型以 token 計價），輸入輸出皆為一般資料（JSON），無二進位處理；可作為本功能的 MVP。

**Independent Test**: 有效金鑰 + 圖片模型 → 送提示 → 取回圖片資料 + 記一筆 token 計費歸戶；未授權/壞金鑰 → 擋下。

**Acceptance Scenarios**:

1. **Given** 一個圖片生成模型分配 + 金鑰，**When** 成員送文字提示呼叫圖片端點，**Then** 取回生成圖片的資料、記一筆成功用量（token 計量、按價計費、歸戶分配）。
2. **Given** 金鑰範圍外的模型，**When** 呼叫，**Then** 被擋下（未授權）。
3. **Given** 壞/缺金鑰，**When** 呼叫，**Then** 回未授權。
4. **Given** 上游圖片生成失敗，**When** 呼叫，**Then** 回帶原因的錯誤、記一筆上游錯誤用量。

---

### User Story 2 - 成員呼叫重排序（rerank）模型（Priority: P2）

成員送一個查詢 + 一組候選文件，取回依相關度重排序後的結果，用量以「**每次查詢**」這個原生單位計量計費、歸戶分配。

**Why this priority**: rerank 是 RAG 常用能力，輸入輸出皆 JSON、無二進位；且其計費單位是「每查詢」——**第二次驗證**計費一般化能裝非 token 單位（繼 OCR 的「頁」之後），確認一般化不是一次性特例。

**Independent Test**: 有效金鑰 + rerank 模型 → 送 query + documents → 取回排序結果 + 記一筆「每查詢」計費歸戶。

**Acceptance Scenarios**:

1. **Given** 一個 rerank 模型分配 + 金鑰，**When** 成員送 query + documents，**Then** 取回排序結果、記一筆成功用量（單位＝查詢、數量＝1、按每查詢價計費、歸戶分配）。
2. **Given** rerank 模型未定每查詢價，**When** 呼叫，**Then** 仍回結果、記用量、花費以 0 計。
3. **Given** 缺 query 或 documents，**When** 呼叫，**Then** 回請求格式錯誤。
4. **Given** 上游失敗，**When** 呼叫，**Then** 回帶原因錯誤、記上游錯誤用量。

---

### User Story 3 - 成員呼叫語音合成（TTS）模型（Priority: P3）

成員送一段文字，取回**合成的語音音檔**（二進位音訊內容），用量以「**每字元**」這個原生單位計量計費、歸戶分配。

**Why this priority**: TTS 帶來新形態——**回應是二進位音檔**（需以音訊內容回傳，非 JSON）。計費以輸入字數（字元）計，沿用計費一般化的單位維度。價值高但形態新，故次於兩個純 JSON 端點。

**Independent Test**: 有效金鑰 + TTS 模型 → 送文字 → 取回音檔內容 + 記一筆「每字元」計費（量＝輸入字數）歸戶。

**Acceptance Scenarios**:

1. **Given** 一個 TTS 模型分配 + 金鑰，**When** 成員送文字，**Then** 取回音檔（二進位音訊內容、正確的內容類型）、記一筆成功用量（單位＝字元、數量＝輸入字數、按每字元價計費、歸戶分配）。
2. **Given** TTS 模型未定每字元價，**When** 呼叫，**Then** 仍回音檔、記用量、花費以 0 計。
3. **Given** 上游 TTS 失敗，**When** 呼叫，**Then** 回帶原因錯誤、記上游錯誤用量。
4. **Given** 計費／用量記錄需在音檔資料產出當下完成，**When** 回應產生，**Then** 用量不因回應形態（二進位）而漏記（不無聲消失）。

---

### User Story 4 - 成員呼叫語音轉文字（STT）模型（Priority: P4）

成員**上傳一個音檔**，取回辨識出的文字，用量以該模型的原生單位（音訊秒數，或對 token 計價的模型以 token）計量計費、歸戶分配。

**Why this priority**: STT 是另一個新形態——**輸入是上傳的音檔**（多段表單上傳，非 JSON）。計量需要音訊長度（秒）或 token，較其他端點多一個未知。形態最複雜，故優先序最低。

**Independent Test**: 有效金鑰 + STT 模型 → 上傳音檔 → 取回文字 + 記一筆計費（秒或 token）歸戶。

**Acceptance Scenarios**:

1. **Given** 一個 STT 模型分配 + 金鑰，**When** 成員上傳音檔，**Then** 取回辨識文字、記一筆成功用量（依模型計價方式：秒數或 token、按價計費、歸戶分配）。
2. **Given** 無法取得音訊秒數（且模型非 token 計價），**When** 計費，**Then** 用量記錄保留、花費以 0 計、不阻擋回應。
3. **Given** 缺上傳檔案，**When** 呼叫，**Then** 回請求格式錯誤。
4. **Given** 上游 STT 失敗，**When** 呼叫，**Then** 回帶原因錯誤、記上游錯誤用量。

---

### User Story 5 - 目錄誠實：非 chat 模型不再假裝 chat（Priority: P3）

管理員在模型管理介面看 OCR / embedding / 圖片 / 語音 / rerank 等非聊天模型時，**「能力」欄不再誤顯「chat」**；詳情頁能一眼看出該模型的「類型」（OCR / 圖片 / 語音 / rerank …）。

**Why this priority**: 直接修正使用者實際撞到的「`mistral-document-ai` 明明是 OCR 卻顯能力 chat」（2026-06-11）。隨著更多端點開放，目錄誠實（「能收 ⟺ 服務得了」）的呈現面必須跟上；屬橫切修正，與各端點正交。

**Independent Test**: 一個非 chat 模型（如 OCR）→ 管理介面「能力」欄不含 chat（無能力旗標時為空）、詳情頁顯示其「類型」；chat 模型不受影響。

**Acceptance Scenarios**:

1. **Given** 一個非 chat 模型且無聊天類能力旗標，**When** 管理員看其能力，**Then** 「能力」欄為空（不再被兜底成 chat）。
2. **Given** 任一模型，**When** 管理員看詳情，**Then** 看得到該模型的「類型」（chat / embedding / 圖片 / 語音 / OCR / rerank …）。
3. **Given** 一個聊天模型，**When** 管理員看其能力，**Then** 仍正確含 chat（零回歸）。
4. **Given** 一個現有已被誤標 chat 的非 chat 模型，**When** 管理員對其重新同步上游登錄資訊，**Then** 其能力被更新為正確值。

---

### Edge Cases

- **未定價（任一單位）**：模型未定該單位價 → 回結果、記數量、花費以 0 計、不阻擋（沿用既有「未定價→成本 0」慣例）。
- **token 端點零回歸**：聊天 / embedding 仍以 token 計量計費，新單位欄對其為空。
- **跨單位不可加總**：token / 頁 / 查詢 / 字元 / 秒 / 張彼此不能相加；聚合只能以花費（USD）為共同軸（既有花費圖已涵蓋；本功能不改圖表）。
- **二進位回應（TTS）**：音檔以正確內容類型回傳；計費必須在資料產出當下記，不因回應非 JSON 而漏記。
- **上傳檔案（STT）**：超大檔受既有請求大小上限約束；非音訊內容由上游判定並回錯。
- **配額（已知限制）**：token 月配額無法度量頁/查詢/字元/秒；非 token 呼叫此階段不被 token 配額擋下，花費仍記錄歸戶可見。每單位用量上限為後續工作。
- **STT 秒數來源不確定**：若上游回應未帶音訊長度，且模型非 token 計價 → 記數量為空、花費 0，不阻擋。

## Requirements *(mandatory)*

### Functional Requirements

#### 共通（四個端點）

- **FR-001**: 每個新端點 MUST 走與既有聊天/embedding/OCR **同一條前置檢查**（金鑰驗證、分配、模型存取、上游憑證解析）。
- **FR-002**: 每次成功呼叫 MUST 記一筆用量：以該模型的**原生單位**計量（token / 查詢 / 字元 / 秒）、按當時該單位價計費、歸戶到對應分配。
- **FR-003**: 未定該單位價時，MUST 仍回結果、記數量、花費以 0 計（不阻擋）。
- **FR-004**: 上游失敗 MUST 回帶原因的錯誤、記一筆上游錯誤用量（帶 model / allocation），伺服器留可診斷紀錄；底層供應商憑證 MUST NOT 出現在訊息或日誌。
- **FR-005**: 既有聊天/responses/embedding/OCR 端點、token 計費、用量視圖、配額 MUST 維持原行為不變（零回歸）。

#### 圖片生成（US1）

- **FR-006**: 系統 MUST 提供圖片生成呼叫端點，讓成員以文字提示生成圖片、以資料形式取回。
- **FR-007**: 圖片呼叫 MUST 以 token 計量計費（這類模型以 token 計價，沿用既有 token 計費）。

#### rerank（US2）

- **FR-008**: 系統 MUST 提供 rerank 呼叫端點，讓成員送查詢 + 候選文件、取回排序結果。
- **FR-009**: rerank 呼叫 MUST 以「每查詢」為單位計量計費（數量＝1 次查詢）。

#### TTS（US3）

- **FR-010**: 系統 MUST 提供語音合成端點，讓成員送文字、取回**音檔（二進位音訊內容、正確內容類型）**。
- **FR-011**: TTS 呼叫 MUST 以「每字元」為單位計量計費（數量＝輸入字數）。
- **FR-012**: TTS 的計費與用量記錄 MUST 在音檔資料產出當下完成，不因回應為二進位而漏記。

#### STT（US4）

- **FR-013**: 系統 MUST 提供語音轉文字端點，讓成員**上傳音檔**、取回辨識文字。
- **FR-014**: STT 呼叫 MUST 依模型計價方式計量計費（音訊秒數，或對 token 計價的模型以 token）。

#### 目錄誠實（US5）

- **FR-015**: 模型能力的判定 MUST NOT 把「無聊天類能力旗標的非 chat 模型」兜底成 chat；聊天類模型仍正確標 chat（零回歸）。
- **FR-016**: 管理員模型詳情 MUST 顯示該模型的「類型」（chat / embedding / 圖片 / 語音 / OCR / rerank …），與「能力」分開呈現。
- **FR-017**: 管理員 MUST 能對既有被誤標的模型重新同步上游登錄資訊，使其能力更新為正確值。

#### 計費／資料

- **FR-018**: 計量單位以字串維度承載（token / page / query / character / second …）；新增單位 MUST NOT 需要資料庫結構變更（沿用計費一般化已建立的單位維度）。

### Key Entities *(include if feature involves data)*

- **用量紀錄（CallRecord）**：每次呼叫的計量（數量 + 單位）+ 花費 + 歸戶；本功能新增 query / character / second 三種單位值（沿用既有「數量 + 單位」欄，無新結構）。
- **價目（PriceList）**：模型在某時點的每單位價；本功能沿用既有「每單位價」欄承載每查詢 / 每字元 / 每秒價。
- **分配（Allocation）**：用量歸戶對象（不變）。
- **模型目錄（ModelCatalog）**：承載模型「能力」與「類型」；本功能修正能力判定不再假裝 chat，並讓「類型」可呈現。
- **計量單位（Unit）**：列舉概念（token / page / query / character / second …），標示一筆用量的計量方式與對應價。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員能呼叫四個新端點（圖片 / rerank / TTS / STT），每個都取回正確形態的結果（圖片資料 / 排序 / 音檔 / 文字），並各記一筆「以該模型原生單位計量、按價計費、歸戶分配」的用量。
- **SC-002**: TTS 回傳可播放的音檔（正確內容類型）、STT 接受音檔上傳並回文字；兩者的用量皆正確記錄，不因二進位形態漏記。
- **SC-003**: rerank 以「每查詢」、TTS 以「每字元」計費——證明計費一般化能裝多種非 token 單位（不只 OCR 的「頁」）。
- **SC-004**: 管理介面中，OCR / embedding / 圖片 / 語音 / rerank 等非 chat 模型的「能力」欄不再顯示 chat；詳情頁可看出其「類型」；chat 模型不受影響。
- **SC-005**: 既有聊天 / responses / embedding / OCR 端點、token 計費、用量、配額、能力篩選（facet）零回歸。
- **SC-006**: 資料庫維持單一 migration head；無新增第三方套件。

## Assumptions

- **沿用統一前置檢查與計費一般化**：四端點重用既有 endpoint-agnostic preflight 與「數量 + 單位」計費維度（OCR 增量已建立），新單位＝加資料、不改結構。
- **圖片以 token 計價**：本平台服務的圖片模型（Azure gpt-image 類）以 token 計價，沿用既有 token 計費；不引入「每張/每像素」單位（非本平台所需）。
- **rerank 計量為「每次查詢 1 單位」**：對齊上游成本對照中 rerank 的「每查詢成本」概念。
- **TTS 計量為「輸入字元數」**：對齊上游「每字元」計價；輸出為音檔內容，以正確內容類型回傳（非檔案下載附件語意）。
- **STT 計量採模型計價方式**：能取得音訊秒數則按秒，否則對 token 計價模型按 token；皆不可得 → 記數量空、花費 0（秒數來源細節於規劃階段確認）。
- **二進位 I/O 限這兩類**：僅 TTS（輸出音檔）與 STT（輸入音檔）涉及二進位；其餘端點皆 JSON。
- **目錄誠實限呈現面**：修正能力判定不假裝 chat + 詳情顯類型；「類型」沿用既有衍生資訊（litellm mode），能力與類型為不同軸。現有模型需重新同步才更新既有資料。
- **不在本功能範圍**：每單位用量上限（每天 N 張/頁/秒）、圖表/視覺化改版、rerank/moderation 以外的其他端點、配額改以花費為軸。
