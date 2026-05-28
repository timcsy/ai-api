# Feature Specification: 憑證暫停 / 恢復

**Feature Branch**: `019-allocation-pause-resume`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "Admin can temporarily pause an allocation (its calls are rejected) and later resume it, preserving the same token — a reversible complement to revoke, not via quota. Adds a paused status and pause/resume actions; status-only, no token change, no reclaim lock."

## 背景

管理員有時想「臨時關閉一把憑證、過陣子再開」——例如某把無限額的服務型憑證短期停用、或可疑活動先擋住觀察。目前做不到：撤回是終局（且重新發等於換新 token），隔離只由異常偵測器自動觸發，配額=0 又正是要避免的限額手段。本功能補上一個**可逆、保留同一把 token** 的暫停能力：管理員暫停 → 該憑證呼叫立即被擋 → 恢復 → 同一把 token 又能用。對應願景〈階段 10〉「新能力：憑證暫停/恢復」。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 暫停一把憑證 (Priority: P1)

管理員把一把進行中的憑證暫停，該憑證的後續 API 呼叫立即被拒絕，但憑證本身與其 token 都保留著，等待之後恢復。

**Why this priority**: 這是核心訴求——「臨時關閉」。沒有它，管理員只能在「終局撤回」與「動配額」之間二選一，兩者都不符合「臨時、可還原、不換 key」的需求。

**Independent Test**: 對一把 active 憑證執行暫停 → 用同一 token 呼叫 API → 被拒絕並回明確「已暫停」原因；憑證仍存在、token 未變、未被鎖定。

**Acceptance Scenarios**:

1. **Given** 一把 active 憑證，**When** 管理員暫停它，**Then** 該憑證狀態變為「已暫停」，且這次操作被記入稽核。
2. **Given** 一把已暫停的憑證，**When** 持有者用原 token 呼叫 API，**Then** 呼叫立即被拒絕並回「已暫停」原因（與「已撤回」可區分）。
3. **Given** 一把已暫停的憑證，**When** 查看它，**Then** token 與既有設定（配額、標記等）皆未改變、未被鎖定（與撤回不同）。

---

### User Story 2 - 恢復一把憑證 (Priority: P1)

管理員把先前暫停的憑證恢復，該憑證的**同一把 token** 立即又能正常呼叫，無需重新發放或輪替。

**Why this priority**: 與暫停一體兩面；只有暫停沒有恢復則等同撤回。可逆性是本功能的全部價值。

**Independent Test**: 對一把已暫停憑證執行恢復 → 用**原本那把** token 呼叫 → 成功；不需要任何新 token。

**Acceptance Scenarios**:

1. **Given** 一把已暫停的憑證，**When** 管理員恢復它，**Then** 狀態回到 active，操作記入稽核。
2. **Given** 剛恢復的憑證，**When** 持有者用**原 token** 呼叫 API，**Then** 呼叫成功（不需 rotate / 重新領取）。

---

### User Story 3 - 狀態機防呆 (Priority: P2)

暫停 / 恢復只在合理的狀態間轉移，不會把已撤回或被系統隔離的憑證意外改動，避免管理員誤操作造成混亂。

**Why this priority**: 保護既有的撤回（終局）與隔離（異常偵測）語意不被破壞；屬正確性護欄，但核心暫停/恢復沒有它仍可示範。

**Independent Test**: 對 revoked / quarantined / 已是目標狀態的憑證嘗試暫停或恢復 → 一律以明確錯誤拒絕，不改動該憑證。

**Acceptance Scenarios**:

1. **Given** 一把已撤回的憑證，**When** 管理員嘗試暫停，**Then** 操作被拒絕並說明原因，憑證不變。
2. **Given** 一把 active（未暫停）的憑證，**When** 管理員嘗試恢復，**Then** 操作被拒絕（沒有可恢復的暫停狀態）。
3. **Given** 一把被系統隔離（quarantined）的憑證，**When** 管理員嘗試暫停 / 恢復，**Then** 操作被拒絕，維持既有隔離處理路徑不受干擾。

---

### Edge Cases

- **與撤回的區別**：暫停**不**換 token、**不**建立「重領鎖定」；撤回維持原本的終局語意。兩者在介面上需可清楚區分，避免管理員把「暫停」當「撤回」誤用。
- **即時性**：暫停後的拒絕必須即時生效（依當前狀態逐次檢查），不依賴 token 過期。
- **計量歸屬**：暫停期間被擋下的呼叫應記為「因暫停而拒絕」，可與「因撤回拒絕」「因配額拒絕」區分。
- **配額互動**：暫停與配額正交——暫停中不計用量；恢復後配額狀態延續原樣（不因暫停而重置或補償）。
- **自助領取的憑證**：自助來源的憑證同樣可被管理員暫停 / 恢復；恢復不觸發、也不解除任何既有重領鎖定（暫停本就不建立鎖定）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 管理員 MUST 能把一把進行中（active）的憑證暫停，使其狀態轉為「已暫停」。
- **FR-002**: 管理員 MUST 能把一把「已暫停」的憑證恢復為進行中（active）。
- **FR-003**: 暫停 MUST **保留同一把 token**、不輪替、不重新發放；恢復後原 token 立即可用。
- **FR-004**: 暫停 MUST **不**建立「重領鎖定」、**不**更動配額或其他既有設定（與撤回的終局處理有別）。
- **FR-005**: 「已暫停」憑證的 API 呼叫 MUST 立即被拒絕，並回傳可與「已撤回」「配額用罄」區分的「已暫停」原因。
- **FR-006**: 暫停與恢復 MUST 各自寫入稽核紀錄（誰、何時、對哪把憑證）。
- **FR-007**: 暫停 MUST 僅能從 active 狀態執行；恢復 MUST 僅能從「已暫停」狀態執行；對其他狀態（已撤回、隔離中、或已是目標狀態）的暫停/恢復請求 MUST 以明確錯誤拒絕且不改動該憑證。
- **FR-008**: 被擋下的「因暫停拒絕」呼叫 MUST 可在用量/呼叫紀錄中與其他拒絕原因區分。
- **FR-009**: 既有的撤回、隔離 / 解除隔離、配額與用量行為 MUST 不受本功能影響（零退化）。

### Key Entities *(include if feature involves data)*

- **憑證分配 (Allocation)**：既有實體。本功能為其生命週期新增一個「已暫停」狀態，並新增「暫停」「恢復」兩個可逆轉移；不新增資料表、不改動 token 與配額欄位語意。
- **呼叫紀錄 (Call Record)**：既有實體。新增一種拒絕結果「因暫停拒絕」，供用量切分與稽核區分。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 管理員可在不換 token 的前提下，於數秒內暫停一把憑證並使其呼叫被擋（手動 token 操作數為 0）。
- **SC-002**: 恢復後，**先前那把 token**（非新發）100% 立即可正常呼叫。
- **SC-003**: 暫停期間，該憑證 100% 的呼叫被以「已暫停」原因拒絕，且該原因可與撤回 / 配額原因區分。
- **SC-004**: 對非法狀態（已撤回 / 隔離中 / 已是目標狀態）的暫停或恢復一律被拒絕、目標憑證零改動。
- **SC-005**: 既有測試全數通過，撤回 / 隔離 / 配額 / 用量行為零退化。

## Assumptions

- 暫停僅限管理員操作；成員不能自助暫停自己的憑證（首版範圍）。
- 暫停為手動、即時；不含排程自動暫停 / 恢復（未來可加）。
- 暫停與隔離（quarantined）是不同概念：前者管理員手動、後者異常偵測器自動；兩條路徑互不干擾，恢復只處理「已暫停」。
- 暫停期間的呼叫不計入用量（與撤回 / 配額拒絕一致：拒絕的呼叫不計費）。
- 沿用既有「逐次呼叫檢查當前狀態」的執法點，使暫停即時生效。
