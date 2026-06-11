# Feature Specification: 計費一般化（非 token 單位）+ OCR 端點

**Feature Branch**: `040-ocr-billing-units`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "計費一般化（非 token 單位）+ OCR 端點"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 成員呼叫 OCR 模型並按頁計費歸戶（Priority: P1）🎯 MVP

成員手上有一個 OCR（文件辨識）模型的分配與金鑰。他送一份文件給 OCR 端點，拿回辨識出來的文字，且這次呼叫的用量**以「頁數」這個原生單位計量**、按當時頁價計算花費、歸戶到他的分配——和聊天/embedding 走同一條前置檢查（憑證、分配、存取、上游憑證）。這是整個「多端點開放」主題第一個**非 token 計費**的端點，同時把計費層從「只懂 token」一般化成「能裝任何計量單位」。

**Why this priority**: 它同時交付兩件事——成員真的能用 OCR 模型（原則 6），以及把計費層一般化（後續 OCR/圖片/語音端點的共同地基）。沒有它，OCR 模型只能「列在目錄、呼叫不到」。本身即可獨立驗收的 MVP。

**Independent Test**: 給一個 OCR 模型的有效金鑰 + 一份文件 → 拿回文字 + 記一筆「`quantity=頁數`、`unit=page`、`cost>0`、歸戶該分配」的用量；未授權模型 / 壞金鑰 → 擋下。

**Acceptance Scenarios**:

1. **Given** 一個 OCR 模型分配 + 金鑰，**When** 成員以有效金鑰送文件呼叫 OCR 端點，**Then** 回傳辨識文字、並記一筆成功用量：計量單位為「頁」、數量等於處理頁數、花費按當時頁價計算、歸戶到該分配。
2. **Given** 該 OCR 模型在價目表中已有「每頁價」，**When** 計費發生，**Then** 花費 = 頁數 × 每頁價（與既有 token 計費邏輯互不影響）。
3. **Given** 一個 OCR 模型在價目表中**未定頁價**，**When** 成員呼叫，**Then** 仍回傳結果、用量記錄頁數，但花費以 0 計（沿用既有「未定價→成本 0」慣例），不阻擋呼叫。
4. **Given** 金鑰的範圍**不含**所請求的 OCR 模型，**When** 呼叫，**Then** 被擋下並回「模型不符／未授權」。
5. **Given** 壞或缺的金鑰，**When** 呼叫，**Then** 回 401。

---

### User Story 2 - 非 token 計費可稽核、admin 可覆寫建議頁價（Priority: P2）

管理員要能為 OCR（及未來其他非 token）模型設定/檢視「每頁價」，且這個價可以**取自上游成本建議**（系統內建的成本對照），也可以在建議值缺漏或錯誤時**手動覆寫**。計費永遠以「平台自己的價目表」為準（可稽核、append-only、呼叫當時的價），不直接信任外部成本表。

**Why this priority**: 計費的可追蹤性與正確性（原則 2）；但建立在 US1 的計量地基上，故次之。

**Independent Test**: admin 為一個 OCR 模型設「每頁價」→ 成員呼叫後花費按該價計；admin 覆寫頁價 → 之後的呼叫按新價、先前紀錄不變（point-in-time）。

**Acceptance Scenarios**:

1. **Given** 一個 OCR 模型，**When** admin 查看其價格，**Then** 看得到「每頁價」欄位（與既有 token 價並列、不混淆）。
2. **Given** 系統有上游成本建議（每頁），**When** admin 採用，**Then** 該建議被快照進平台價目表成為當前頁價。
3. **Given** admin 手動設定/覆寫每頁價，**When** 之後成員呼叫，**Then** 花費按新價計；改價前已記錄的呼叫花費**不被追溯改動**（呼叫當時的價）。

---

### User Story 3 - OCR 上游錯誤可診斷（Priority: P2）

OCR 上游失敗時，端點要回帶原因的錯誤、記一筆 `upstream_error` 用量、並在伺服器留可診斷的紀錄，不無聲吞掉。

**Why this priority**: 可觀測性（原則 2 / 可診斷）；與 US1 同檔的錯誤分支。

**Independent Test**: 讓 OCR 上游丟錯 → 回帶原因的錯誤 + 記一筆 `upstream_error`（帶 model / allocation）；底層憑證不入訊息。

**Acceptance Scenarios**:

1. **Given** OCR 上游回失敗，**When** 成員呼叫，**Then** 端點回帶上游原因的錯誤、記一筆 `upstream_error` 用量（帶 model、allocation），且伺服器有一行帶上下文的紀錄。
2. **Given** 任何錯誤，**When** 回應或紀錄產生，**Then** 底層供應商金鑰絕不出現在訊息或日誌中。

---

### User Story 4 - 目錄正確標示 OCR 類型 + 顯示如何呼叫（Priority: P3）

成員在模型目錄看 OCR 模型時，應被正確標示為「OCR 類型」（不再被假裝成 chat），詳情頁顯示 `/v1/ocr` 的呼叫範例；其他類型一致地呈現。

**Why this priority**: 可達性的呈現面（原則 6）；獨立於計費，可最後做。

**Independent Test**: OCR 模型詳情回 `kind=ocr` + 顯示 OCR 呼叫範例；chat / embedding 模型不受影響。

**Acceptance Scenarios**:

1. **Given** 一個 OCR 模型，**When** 成員看其詳情，**Then** 類型標示為 OCR、且顯示 `/v1/ocr` 的呼叫範例。
2. **Given** chat / embedding 模型，**When** 看詳情，**Then** 仍顯示各自正確的類型與呼叫範例（零回歸）。

---

### Edge Cases

- **多頁文件**：一次處理 N 頁 → 計量 `quantity=N`、花費 = N × 每頁價。
- **未定頁價**：模型沒有每頁價 → 花費以 0 計、仍記頁數，不阻擋。
- **token 端點不受影響**：chat / embedding 仍以 token 計量與計費，新單位欄對它們為空。
- **配額（已知限制）**：既有「每月 token 配額」無法度量「頁」；本階段 OCR 呼叫**不被 token 配額擋下**，但花費仍記錄、歸戶可見。每單位用量上限（如每天 N 頁）為後續工作，不在此範圍。
- **跨單位不可加總**：頁、token、秒、張彼此不能相加；聚合/跨端點只能以「花費（USD）」為共同軸（既有花費圖自動涵蓋；本階段不改圖表）。
- **上游回傳頁數缺漏**：若上游未回明確頁數 → 以可得的最佳計量（如輸入文件頁數）為準；無法判定時記 `quantity` 為空、花費 0 並留紀錄。

## Requirements *(mandatory)*

### Functional Requirements

#### 計費一般化（跨 US1/US2 的核心能力）

- **FR-001**: 用量紀錄 MUST 能承載「計量數量 + 計量單位」（單位至少含 token 與 page；設計上可擴充至 image / second / character），且既有 token 欄位**保留**、chat/embedding 繼續以 token 計量（零回歸）。
- **FR-002**: 價目表 MUST 能承載「每單位價」（如每頁價），與既有 token 價並存且不混淆；價目為 **append-only、point-in-time**（改價不追溯既有紀錄）。
- **FR-003**: 花費計算 MUST 一般化為「數量 × 對應單位的當時價」；token 模型的計費結果 MUST 與現行完全一致（零回歸）。
- **FR-004**: 系統 MUST 能將「上游成本建議的每單位價」快照進平台價目表作為建議來源；計費**只信任平台價目表**，不直接用外部成本表計費。
- **FR-005**: admin MUST 能檢視並手動設定/覆寫非 token 模型的每單位價（覆寫缺漏或錯誤的建議）。

#### OCR 端點（US1/US3）

- **FR-006**: 系統 MUST 提供一個 OCR 呼叫端點，讓持有 OCR 模型有效金鑰的成員送文件、取回辨識文字。
- **FR-007**: OCR 呼叫 MUST 走與既有聊天/embedding **同一條前置檢查**（金鑰驗證、分配、模型存取、上游憑證解析）。
- **FR-008**: OCR 呼叫成功 MUST 記一筆用量：單位為「頁」、數量為處理頁數、花費按每頁價、歸戶到對應分配。
- **FR-009**: OCR 上游失敗 MUST 回帶原因的錯誤、記一筆 `upstream_error` 用量（帶 model / allocation）、伺服器留可診斷紀錄；底層憑證 MUST NOT 出現在訊息或日誌。

#### 目錄誠實與呈現（US4）

- **FR-010**: 成員目錄 MUST 正確標示 OCR 模型的類型（不得把 OCR 模型假裝成 chat）；詳情頁顯示對應的 `/v1/ocr` 呼叫範例。
- **FR-011**: chat / embedding 等既有類型的目錄標示與呼叫範例 MUST 不受影響（零回歸）。

#### 共通

- **FR-012**: 既有聊天 / responses / embedding 端點、token 計費、用量視圖、配額 MUST 維持原行為不變（零回歸）。
- **FR-013**: 所有資料庫 schema 變更 MUST 為加欄式（不破壞既有資料），且維持單一 migration head。

### Key Entities *(include if feature involves data)*

- **用量紀錄（CallRecord）**：每次呼叫的計量 + 花費 + 歸戶。新增「計量數量」與「計量單位」兩個面向；既有 token 欄位保留。
- **價目（PriceList）**：模型在某時點的價格。一般化為能存「每單位價」（每頁等），與 token 價並存；append-only。
- **分配（Allocation）**：用量歸戶的對象（不變）。
- **模型目錄（ModelCatalog）**：承載模型類型（含 OCR）與呼叫方式呈現（唯讀衍生，不新增儲存）。
- **計量單位（Unit）**：列舉概念（token / page / …）；標示一筆用量以何種單位計量、以對應何種每單位價。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員能以有效金鑰呼叫 OCR 模型並取回文字，且該次呼叫記一筆「以頁計量、按頁價計費、歸戶分配」的用量（端到端可驗）。
- **SC-002**: 既有 token 模型（chat / embedding）的計費結果與用量記錄在本變更前後**完全一致**（零回歸，既有計費測試全綠）。
- **SC-003**: admin 能為 OCR 模型設定/覆寫每頁價；改價後的呼叫按新價計、改價前的紀錄花費不變。
- **SC-004**: OCR 上游失敗時，成員得到可理解的錯誤、且該次失敗在用量視圖中可見（記為上游錯誤），底層憑證不外洩。
- **SC-005**: OCR 模型在目錄中被正確標示類型並顯示呼叫範例；chat/embedding 呈現不受影響。
- **SC-006**: 資料庫維持單一 migration head；無新增第三方套件。

## Assumptions

- **計量單位以「頁」為 OCR 的原生單位**：對齊上游成本對照中 OCR 模型的「每頁成本」概念；頁數以上游回應或輸入文件可得的最佳值為準。
- **沿用統一前置檢查**：OCR 端點重用既有 endpoint-agnostic preflight，不另寫一套（增量＝解析請求 → 同一條 preflight → 呼叫對應上游函式 → 記帳）。
- **計費方法論沿用既有原則**：上游成本對照當「建議價來源」，快照進平台 PriceList（append-only、可稽核），計費只用 PriceList、歸戶分配；建議缺漏/錯誤由 admin 覆寫。
- **OCR 輸入以文件參照（URL 或內嵌）為主**：避免二進位 multipart 上傳；二進位輸入/輸出（如音檔、圖片 bytes）不在本階段範圍。
- **非 token 呼叫此階段不被 token 配額擋下**：token 月配額無法度量「頁」；OCR 呼叫仍記花費、歸戶可見，但每單位用量上限為後續工作（descope 的每日上限可能在此以「每天 N 頁/張」回來）。
- **圖表/視覺化不在本階段**：跨單位只能以花費為軸；既有花費圖已涵蓋，token 專屬圖的調整留待後續。
- **不在本範圍**：圖片生成端點（Azure gpt-image 實為 token 計費、不觸發本一般化）、語音 TTS/STT（二進位 I/O）、rerank / moderation、每單位用量上限、圖表改版。
