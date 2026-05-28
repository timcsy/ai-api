# Feature Specification: 階段 10 使用體驗打磨收尾

**Feature Branch**: `020-phase10-ux-polish`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "Phase 10 UX polish finish: member dashboard allocation cards show display_name + current price; claimable cards link to model detail; first-run 3-step onboarding; single canonical call endpoint across dashboard and how-to-call example; admin quota adjust uses a shadcn Dialog instead of native prompt/confirm; token hint copy covers self-service. Excludes 3b.7 Playwright E2E."

## 背景

本機真實使用者實測走通後盤點出數處摩擦：成員儀表板資訊要逐張點開、技術 slug 不好讀、新手不知如何開始、呼叫端點兩處顯示不一致、admin 局部用瀏覽器原生對話框、token 提示文案偏 admin 視角。本功能把這些一次打磨完，皆不改動核心領域行為，只讓既有流程更直觀、資訊更易消化、操作更一致。對應願景〈階段 10〉剩餘項（不含 3b.7 Playwright E2E，該項另立）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 分配卡片一眼看懂（名稱 + 現價）(Priority: P1)

成員在儀表板的「我的分配」卡片上，直接看到好讀的模型名稱（而非技術 slug）與目前單價，不必逐張點進去。

**Why this priority**: 成員最常停留的頁面；把「這是什麼模型、花多少錢」放到卡面，是資訊易消化的最大增量，且延續階段 9 的自我掌握。

**Independent Test**: 有分配的成員開啟儀表板 → 每張卡片顯示模型顯示名稱（slug 為輔）與現價（每 1M）；缺價目的模型標「未定價」。

**Acceptance Scenarios**:

1. **Given** 成員有一張對應某 model 的分配，**When** 開啟儀表板，**Then** 卡片以該 model 的顯示名稱為主、slug 為輔呈現。
2. **Given** 該 model 目前有價目，**When** 看卡片，**Then** 顯示現價（每 1M，與目錄/詳情同一格式）。
3. **Given** 該 model 無價目，**When** 看卡片，**Then** 顯示「未定價」而非 0 或空白。

---

### User Story 2 - 領取前先了解（卡片可點進詳情）(Priority: P2)

成員在「可自助領取」卡片上可直接點進該 model 的詳情頁，領取前先看能力、價格、說明，而不是盲領。

**Why this priority**: 降低盲目領取；但成員仍可從模型目錄達成，故次於 P1。

**Independent Test**: 點擊任一可自助領取卡片 → 導向該 model 的詳情頁。

**Acceptance Scenarios**:

1. **Given** 儀表板有可自助領取的 model 卡片，**When** 點擊卡片（非領取鈕區域），**Then** 導向該 model 詳情頁。
2. **Given** 卡片同時有「領取」鈕，**When** 點領取鈕，**Then** 仍執行領取、不誤觸導頁。

---

### User Story 3 - 新成員上手引導 (Priority: P2)

完全沒有分配的新成員，在儀表板看到「① 領取憑證 ② 複製 ③ 貼進 Authorization」三步極簡引導，知道怎麼開始。

**Why this priority**: 直接服務願景「讓不會寫程式的同事也能用」；但僅影響首次、空狀態。

**Independent Test**: 以無任何分配的成員登入 → 儀表板顯示三步上手引導；一旦有分配則不再強調。

**Acceptance Scenarios**:

1. **Given** 無分配的成員，**When** 開啟儀表板，**Then** 顯示三步上手引導。
2. **Given** 已有至少一張分配的成員，**When** 開啟儀表板，**Then** 不顯示（或不突顯）該引導，避免干擾。

---

### User Story 4 - 呼叫端點單一可信來源 (Priority: P1)

成員不論在儀表板「API 端點」或任一「如何呼叫」範例看到的呼叫網址都一致且正確，複製後可直接使用，不會因兩處顯示不同而困惑。

**Why this priority**: 真實使用者實測時就被「兩處網址不同、複製出來不能跑」絆住；正確性問題，影響每個要呼叫 API 的人。

**Independent Test**: 比對儀表板「API 端點」與「如何呼叫」範例顯示的 base URL → 兩者一致；該網址即為實際可呼叫的端點。

**Acceptance Scenarios**:

1. **Given** 成員開啟儀表板與任一「如何呼叫」範例，**When** 比對顯示的呼叫網址，**Then** 兩處相同。
2. **Given** 複製範例中的呼叫指令，**When** 以有效憑證執行，**Then** 能打到 gateway（不因網址錯誤而連不上）。

---

### User Story 5 - admin 配額調整對話框一致化 (Priority: P3)

管理員調整分配配額時，使用與全站一致的對話框（可看清欄位、驗證輸入），而非瀏覽器原生彈窗。

**Why this priority**: 一致性與輸入正確性的打磨；功能本身已可用，故較低。

**Independent Test**: 管理員對一筆分配觸發「調整配額」→ 出現站內對話框，輸入非數字被擋、輸入有效值後套用成功。

**Acceptance Scenarios**:

1. **Given** 管理員在分配列觸發調整配額，**When** 對話框開啟，**Then** 為站內一致樣式、預填目前配額。
2. **Given** 輸入無效（非數字／負數），**When** 嘗試送出，**Then** 被擋並提示；空白＝無限額。

---

### User Story 6 - token 提示文案涵蓋自助情境 (Priority: P3)

成員看到的 token 取得說明同時涵蓋「管理員分配」與「自助領取」兩種來源，不再只寫 admin 視角。

**Why this priority**: 純文案修正，影響理解但不影響操作。

**Independent Test**: 閱讀儀表板 token 提示 → 文案涵蓋自助領取情境。

**Acceptance Scenarios**:

1. **Given** 成員開啟儀表板，**When** 閱讀 token 提示，**Then** 文案同時說明自助領取與管理員分配的 token 取得方式。

---

### Edge Cases

- **顯示名稱缺漏**：分配對應的 model 已不在目錄（orphan）→ 卡片以 slug 呈現、不報錯。
- **未定價**：缺價目的 model 卡片顯示「未定價」，不顯示 0 或誤導金額。
- **可點卡片 vs 內部按鈕**：可自助領取卡片可點進詳情，但卡內「領取」鈕點擊不應同時觸發導頁。
- **端點正確性**：dev 與 prod 顯示的呼叫網址都要是實際可達的端點（不可一處對、一處錯）。
- **零退化**：既有用量摘要、配額視角、領取、撤回、暫停/恢復行為不受影響。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 「我的分配」卡片 MUST 以模型顯示名稱為主、slug 為輔呈現；model 已不在目錄時退回以 slug 呈現且不報錯。
- **FR-002**: 「我的分配」卡片 MUST 顯示該 model 目前單價（與目錄/詳情同一單位與格式）；無價目時標「未定價」。
- **FR-003**: 「可自助領取」卡片 MUST 可點進該 model 詳情頁；卡內「領取」鈕的點擊 MUST 不觸發導頁。
- **FR-004**: 無任何分配的成員 MUST 在儀表板看到三步上手引導；已有分配者 MUST 不被該引導干擾。
- **FR-005**: 儀表板「API 端點」與所有「如何呼叫」範例顯示的呼叫 base URL MUST 來自單一可信來源、彼此一致，且為實際可呼叫的端點（dev/prod 皆正確）。
- **FR-006**: 管理員調整分配配額 MUST 使用站內一致的對話框（預填目前值、擋非法輸入、空白＝無限額），不使用瀏覽器原生彈窗。
- **FR-007**: 成員 token 取得說明文案 MUST 同時涵蓋自助領取與管理員分配兩種來源。
- **FR-008**: 既有成員/管理員功能（用量摘要、配額視角、自助領取、撤回、暫停/恢復、目錄）MUST 零退化。

### Key Entities *(include if feature involves data)*

- **分配 (Allocation)**：既有；卡片需其對應 model 的顯示名稱與現價（顯示名稱來源於目錄）。不變更分配資料語意。
- **模型目錄項 (Catalog Model)**：既有；提供顯示名稱、現價供卡片呈現。
- 不新增資料表、不變更 schema。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員不點進任何單張分配，即可在儀表板看到每張分配的模型名稱與現價（未定價有明確標示）。
- **SC-002**: 可自助領取卡片 100% 可點進對應 model 詳情；領取鈕不誤觸導頁。
- **SC-003**: 無分配的新成員首次登入即見三步上手引導。
- **SC-004**: 儀表板與「如何呼叫」範例顯示的呼叫網址 100% 一致，且複製即可呼叫（不再需手改 port）。
- **SC-005**: 管理員調整配額透過站內對話框完成，無效輸入被擋。
- **SC-006**: 既有測試全數通過，現有成員/管理員行為零退化。

## Assumptions

- 顯示名稱與現價皆取自既有模型目錄與價目資料；不新增資料來源。
- 現價沿用既有顯示單位（每 1M）與格式化，與目錄/詳情一致。
- 「呼叫端點單一來源」以使用者瀏覽器實際可達的 gateway 入口為準；dev 與 prod 皆需正確（實作層決定統一到哪個來源）。
- 上手引導為靜態三步說明，不含互動式教學。
- 不含 3b.7 Playwright E2E（另立 spec）；不含全面視覺改版／換 design system。
