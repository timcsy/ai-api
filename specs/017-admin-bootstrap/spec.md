# Feature Specification: 管理員 Bootstrap 與部署強化

**Feature Branch**: `017-admin-bootstrap`
**Created**: 2026-05-27
**Status**: Draft
**Input**: User description: "Admin bootstrap and deployment hardening: provision the first admin member via a CLI command run as a Helm hook Job (idempotent, OIDC pre-create or local_password invitation), fail-fast at startup when ADMIN_BOOTSTRAP_TOKEN is empty or the known default while COOKIE_SECURE is true, and document the K8s deployment flow"

## 背景

目前系統有兩條管理員認證路徑（`require_admin`）：(1) 帶 `X-Admin-Token` 且值等於 `ADMIN_BOOTSTRAP_TOKEN` 的 bootstrap token，(2) session 對應到 `is_admin=True` 的 member。全新部署後資料庫沒有任何 admin member，且前端後台 UI 只吃 session、從不送 bootstrap token，因此剛部署完**沒有人能登入後台**。要產生第一個 admin 目前只能手動拿 bootstrap token 打 API。此外 `ADMIN_BOOTSTRAP_TOKEN` 預設值 `local-dev-admin-only` 是一把公開已知的萬能後門金鑰，若部署時未覆蓋即為重大風險。

本功能補上「首位管理員自動佈建」與「不安全預設值防呆」，並寫成部署文件，讓 K8s 部署一次到位且不會誤帶後門。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 首位管理員自動佈建 (Priority: P1)

平台維運者在全新環境完成部署後，事先指定的那一個人就能直接登入後台管理，過程中維運者不需要手動拼湊 token、也不需要手動改資料庫。

**Why this priority**: 沒有這一塊，部署完成的系統等於不可用——沒有人進得了後台、無法建立其他成員或設定。這是讓系統「可被接管」的最小前提。

**Independent Test**: 在乾淨資料庫上以指定的管理員 email 執行佈建動作，然後確認該 email 對應的成員存在且具管理員權限、能通過後台授權檢查；用其他 email 則不具管理員權限。

**Acceptance Scenarios**:

1. **Given** 乾淨資料庫且尚無任何管理員，**When** 以指定 email 與 OIDC 身分執行佈建，**Then** 系統建立一筆該 email、具管理員權限、登入方式為 Google OIDC、無密碼的成員。
2. **Given** 上述成員已存在，**When** 該人首次用 Google 登入相同 email，**Then** 系統比對到既有成員並直接給予管理員 session（不另建重複帳號）。
3. **Given** 已存在指定 email 的管理員，**When** 再次執行佈建（例如每次升級都會重跑），**Then** 不重複建立、不報錯，視為成功（idempotent）。
4. **Given** 以本地密碼身分執行佈建，**When** 建立完成，**Then** 系統產生該管理員的一次性邀請／初始登入資訊，供其首次設定密碼。
5. **Given** 佈建動作必須在資料表結構就緒後才能成功，**When** 結構尚未套用，**Then** 佈建動作以明確錯誤失敗（不可在無結構時誤建）。

---

### User Story 2 - 不安全預設憑證防呆 (Priority: P2)

維運者若在正式環境忘了覆蓋那把公開已知的後門金鑰，系統會直接拒絕對外服務，逼維運者修正，而不是悄悄帶著後門上線。

**Why this priority**: 屬安全強化。系統在沒有這層防呆時仍能運作，但會帶著高風險的已知後門。比照既有的加密金鑰啟動防呆做法，把「預設憑證上線」變成不可能。

**Independent Test**: 在「正式環境」訊號開啟下，分別以空值、已知預設值、與一個自訂強值設定該金鑰啟動系統，確認前兩者拒絕啟動、後者正常啟動；在非正式環境下三者皆可啟動。

**Acceptance Scenarios**:

1. **Given** 正式環境訊號開啟且後門金鑰為已知預設值，**When** 系統啟動，**Then** 啟動失敗並回報「金鑰仍為預設值，拒絕在正式環境啟動」之明確訊息。
2. **Given** 正式環境訊號開啟且後門金鑰為空，**When** 系統啟動，**Then** 啟動失敗並回報明確訊息。
3. **Given** 正式環境訊號開啟且後門金鑰為自訂值，**When** 系統啟動，**Then** 正常啟動。
4. **Given** 非正式環境（本地開發），**When** 後門金鑰維持預設值啟動，**Then** 正常啟動（保留零設定的開發體驗）。

---

### User Story 3 - 部署與救援文件 (Priority: P3)

維運者打開一份文件，就能知道部署需要哪些機密設定、首位管理員怎麼產生、忘了覆蓋金鑰會怎樣、以及萬一所有管理員都失聯時如何救援。

**Why this priority**: 文件不影響執行時行為，但決定維運者能否正確、可重複地完成部署與接管。屬支援性質，排在功能之後。

**Independent Test**: 一位未參與開發的維運者僅依文件，即可在測試叢集完成部署並以指定管理員登入後台，無需詢問開發者。

**Acceptance Scenarios**:

1. **Given** 一份部署文件，**When** 維運者依步驟操作，**Then** 文件涵蓋：必填機密清單、首位管理員設定、預設金鑰防呆行為、以及全員失聯時的救援步驟。
2. **Given** 既有 README，**When** 維運者尋找部署說明，**Then** 能從 README 連結到該部署文件。

---

### Edge Cases

- 指定的管理員 email 已存在、但登入方式與佈建要求不同（例如既有為本地密碼、佈建要求 OIDC）：佈建動作必須以明確衝突訊息失敗，不得覆寫既有身分。
- 已存在其他管理員、但指定 email 尚未建立：佈建動作仍應建立並升級該指定 email（不因「已有別的 admin」而跳過）。
- 嘗試降級系統中最後一位管理員：維持既有保護（不可降級最後一位 admin），佈建不應繞過此保護。
- 佈建動作與資料庫遷移的執行順序：佈建必須在遷移成功之後、應用程式對外服務之前完成。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 提供一個可在部署環境執行的佈建動作，能以指定 email 建立一位具管理員權限的成員。
- **FR-002**: 佈建動作 MUST 支援兩種登入方式：Google OIDC（預建無密碼成員，待其首次登入比對綁定）與本地密碼（產生一次性邀請／初始登入資訊）。
- **FR-003**: 佈建動作 MUST 為 idempotent——對已存在的指定管理員重複執行時不重複建立、不失敗、視為成功。
- **FR-004**: 佈建動作 MUST 在資料表結構未就緒時以明確錯誤失敗，且在部署編排上保證於資料庫遷移之後、應用程式對外服務之前執行。
- **FR-005**: 當指定 email 已存在但登入方式與佈建要求衝突時，佈建動作 MUST 以明確錯誤拒絕，不得覆寫既有成員身分。
- **FR-006**: 系統 MUST 在啟動時，於正式環境訊號開啟且 bootstrap token 為空或為已知預設值時，拒絕啟動並回報明確錯誤（fail-fast）。
- **FR-007**: 系統 MUST 在非正式環境下，即使 bootstrap token 為預設值仍允許啟動，以保留本地開發的零設定體驗。
- **FR-008**: 系統 MUST 以既有的「HTTPS／安全 cookie」設定作為正式環境訊號，不新增額外環境變數。
- **FR-009**: 部署編排 MUST 提供以宣告式設定指定首位管理員 email 與登入方式的方式，並可整體啟用／停用該佈建步驟。
- **FR-010**: 專案 MUST 提供一份部署文件，涵蓋必填機密清單、首位管理員佈建、預設金鑰防呆行為、與全員失聯救援步驟，且自 README 可連結到達。
- **FR-011**: 既有的兩條管理員認證路徑與「不可降級最後一位 admin」保護 MUST 維持不變，本功能不得削弱現有授權行為。

### Key Entities *(include if feature involves data)*

- **管理員成員 (Admin Member)**：具管理員權限旗標的既有成員實體；本功能不新增資料表，只透過佈建動作建立／升級既有成員實體的管理員權限與登入方式。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在乾淨環境完成部署後，指定的管理員無需任何手動 token 操作即可登入後台（手動步驟數為 0）。
- **SC-002**: 對同一指定管理員重複執行佈建任意次數，結果一致且皆成功（不產生重複成員、不報錯）。
- **SC-003**: 在正式環境訊號開啟下，帶預設或空 bootstrap token 的部署 100% 無法對外服務（啟動即失敗）。
- **SC-004**: 一位未參與開發的維運者僅依文件即可在測試環境完成部署並登入後台，無需向開發者提問。
- **SC-005**: 既有測試全數維持通過，現有管理員授權與保護行為零退化。

## Assumptions

- 目標部署平台為 Kubernetes，且沿用既有 Helm chart 與「一次性 Job、同 image、`envFrom` 同一 Secret」的模式（已由現有遷移 Job 建立）。
- 多數正式部署採 Google OIDC 登入，故 OIDC 預建為首選路徑；本地密碼路徑作為次要選項保留。
- 「正式環境」以既有的安全 cookie 設定（HTTPS 部署本就會開啟）作為判定訊號，不引入新的環境變數。
- bootstrap token 在本功能後定位為 break-glass（緊急救援）用途，前端不使用它；日常管理一律走 admin member session。
- 不變更資料庫結構；不變更既有授權邏輯，只新增佈建工具、啟動防呆、部署編排與文件。
