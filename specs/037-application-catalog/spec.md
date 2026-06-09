# Feature Specification: 應用分頁（應用目錄）—— Codex 為第一個應用

**Feature Branch**: `037-application-catalog`
**Created**: 2026-06-08
**Status**: Draft
**Input**: 成員端新增「應用」分頁，把「我有金鑰了 → 接到哪些工具、怎麼設定」變成單一所在地。v1 放單一 Codex 卡：狀態（有沒有 Agent 相容的金鑰/分配）+ 一鍵設定（device-flow，CLI + 設定，可選順手裝 VS Code 擴充）+ 建金鑰捷徑（= device-flow，scope 預選 Agent 相容分配）+ 各介面連結（桌面 App / Cursor / JetBrains，「裝好免再設定」）。桌面 App 從「△ 不建議」改「✓ 用一鍵安裝後也能用（共用設定）」（實測）。不做萬能安裝器、不做一般 OpenAI 應用、零 migration、零套件。

## 背景與問題

成員拿到應用金鑰後最大的卡點是「**然後呢？要裝在哪、怎麼設定？**」。目前 Codex 安裝只是 dashboard 上的一張小卡，且沒回答「我這把金鑰接得上嗎（需要 Agent 相容模型）」「除了 CLI，桌面 App / IDE 擴充怎麼用」。平台是 OpenAI 相容 → 任何會講 OpenAI API 的客戶端都能指過來，但成員沒有一個地方看到「**有哪些工具能接、各自怎麼接、幫我建一把剛好夠用的金鑰**」。

**核心想法**：平台有三個目錄視角——**模型目錄**（有哪些模型）、**使用情境目錄**（能做哪些任務）、**應用目錄**（能接哪些工具）。本功能補上第三塊：一個「應用」分頁，第一個應用是 Codex。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 應用分頁 + Codex 一鍵設定（Priority: P1）🎯 MVP

成員在導覽進入「應用」分頁，看到 Codex 卡，按一鍵設定即可把 Codex 接上本平台（沿用既有 device-flow 一鍵安裝），不必離開頁面拼湊步驟。

**Why this priority**: 這是「有鑰匙 → 接得上工具」的核心一步，且 Codex 是最成熟的入口；把既有安裝卡升格成單一所在地立即見效。

**Independent Test**: 成員進「應用」分頁 → 看到 Codex 卡 + 一鍵設定 → 照做後 Codex 能呼叫本平台。

**Acceptance Scenarios**:

1. **Given** 已登入成員，**When** 點導覽「應用」，**Then** 看到應用清單，Codex 為其中一張卡（含「這是什麼」與設定入口）。
2. **Given** Codex 卡，**When** 取得一鍵設定指令/流程，**Then** 內容與既有 device-flow 一鍵安裝一致（CLI + 設定），成員照做即可用。
3. **Given** 原本在 dashboard 的 Codex 安裝卡，**When** 應用分頁上線，**Then** 該安裝內容收斂到應用分頁（單一所在地，不重複呈現）。

---

### User Story 2 - 建金鑰捷徑（scope 預選 Agent 相容）（Priority: P1）

成員在 Codex 卡按「為 Codex 建金鑰」，平台建立一把金鑰，且**只**把「Agent 相容（可走 Responses）」的分配納入 scope，避免成員手滑挑到 Codex 接不上的模型。

**Why this priority**: 把「應用金鑰」概念正門化——為某應用建一把剛好夠用的金鑰；預過濾 Agent 相容是這個捷徑的核心價值。

**Independent Test**: 成員按「為 Codex 建金鑰」→ 只看到/選到 Agent 相容分配 → 建出的金鑰 scope 不含非 Agent 相容模型。

**Acceptance Scenarios**:

1. **Given** 成員有數個分配（部分 Agent 相容、部分不是），**When** 用 Codex 建金鑰捷徑，**Then** 只列出/預選 Agent 相容的分配。
2. **Given** Codex 建金鑰捷徑，**When** 完成建立，**Then** 建出的金鑰 scope 僅含 Agent 相容分配；token 僅顯示一次（沿用既有應用金鑰行為）。
3. **Given** 成員沒有任何 Agent 相容分配，**When** 進 Codex 卡，**Then** 狀態清楚說明「你目前沒有可用於 Codex 的模型」並指引下一步（去領取/請 admin 授權），而非讓他建一把用不了的金鑰。

---

### User Story 3 - 多介面說明（CLI / IDE 擴充 / 桌面 App）（Priority: P2）

Codex 卡說明同一份設定可被多個介面共用：一鍵安裝裝好 CLI + 設定（可選順手裝 VS Code 擴充）；桌面 App / 其他 IDE 給下載/marketplace 連結，且裝好後**不必再設定**（共用同一份設定）。

**Why this priority**: 回答「除了 CLI，桌面 App / IDE 怎麼用」；把實測發現（桌面 App 走共用設定可用）正確呈現。

**Independent Test**: Codex 卡列出三種介面；桌面 App 標「✓ 用一鍵安裝後也能用（免再設定）」而非「不建議」；各介面連結可點。

**Acceptance Scenarios**:

1. **Given** Codex 卡，**When** 檢視介面說明，**Then** 清楚分「能自動的（CLI、可選 VS Code 擴充）」與「給連結的（桌面 App、Cursor、JetBrains）」，後者標「裝好免再設定」。
2. **Given** 桌面 App 的呈現，**When** 檢視，**Then** 為「✓ 用一鍵安裝後也能用（共用設定）」，**不**再出現舊的「△ 不建議」措辭。
3. **Given** 一鍵安裝流程，**When** 環境偵測到可用的 VS Code 指令，**Then** 可選擇順手安裝 VS Code 擴充；偵測不到則略過、不報錯。

---

### Edge Cases

- **成員沒有 Agent 相容分配**：Codex 卡狀態明示不可用 + 指引，不讓他建無效金鑰（US2-3）。
- **桌面 App / 其他 IDE 無法自動安裝**：明確只給連結 + 「免再設定」，不假裝能一鍵裝全部。
- **dashboard 舊安裝卡與應用分頁重複**：上線時收斂到單一所在地，避免兩處 drift。
- **既有 device-flow 行為**：建金鑰捷徑沿用既有 device-flow，不改其安全性（擁有者把關、per-device、輪詢單次交付）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 成員端 MUST 新增「應用」分頁（導覽可達），列出可接本平台的客戶端應用；v1 至少含 Codex。
- **FR-002**: Codex 卡 MUST 提供一鍵設定，內容與既有 device-flow 一鍵安裝一致（CLI + 設定）；成員照做後 Codex 可呼叫本平台。
- **FR-003**: 原 dashboard 的 Codex 安裝卡 MUST 收斂到應用分頁（單一所在地），不在兩處重複呈現同一安裝流程。
- **FR-004**: Codex 卡 MUST 提供「建金鑰捷徑」，建立的金鑰 scope MUST **只**含 Agent 相容（可走 Responses）的分配；token 僅顯示一次（沿用既有應用金鑰）。
- **FR-005**: 平台 MUST 能判定某成員的哪些分配為「Agent 相容」（據既有 responses 支援狀態），供建金鑰捷徑預過濾與卡片狀態顯示。
- **FR-006**: 成員無任何 Agent 相容分配時，Codex 卡 MUST 明示不可用並指引下一步，MUST NOT 讓成員建出用不了的金鑰。
- **FR-007**: Codex 卡 MUST 說明多介面共用同一份設定：一鍵安裝（CLI + 設定，可選 VS Code 擴充）；桌面 App / 其他 IDE 給連結 + 「裝好免再設定」。
- **FR-008**: 桌面 App 呈現 MUST 為「✓ 用一鍵安裝後也能用（共用設定）」，MUST NOT 沿用舊「△ 不建議」措辭。
- **FR-009**: 平台 MUST NOT 嘗試自動安裝桌面 GUI App 或各家 IDE 擴充（VS Code 以外）；能可靠自動的（CLI、可選 VS Code 擴充）才自動，其餘給連結。
- **FR-010**: 既有 device-flow、金鑰、計費、proxy 行為 MUST 零回歸；**無新表、無 migration、無新套件**。

### Key Entities *(include if feature involves data)*

- **應用（概念，v1 精選靜態）**：一個可接本平台的客戶端（v1：Codex）。屬性：名稱、一句說明、需要的能力（Codex＝Agent 相容）、設定方式（一鍵 / 連結）、各介面。
- **成員分配（既有）**：用「Agent 相容」與否（據既有 responses 支援狀態）決定能否用於 Codex、是否納入建金鑰捷徑 scope。
- **應用金鑰（既有 scoped application credential）**：建金鑰捷徑產出的金鑰，scope 為一組 Agent 相容分配。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 成員可在「應用」分頁**一個地方**完成「看到 Codex → 一鍵設定 → 接上平台」，不需離開頁面拼湊步驟。
- **SC-002**: 用「為 Codex 建金鑰」建出的金鑰，scope **100%** 只含 Agent 相容分配；非 Agent 相容模型零誤入。
- **SC-003**: 沒有 Agent 相容分配的成員，**零**情況下能建出用不了的 Codex 金鑰；都會看到明確指引。
- **SC-004**: Codex 安裝流程在 dashboard 與應用分頁**不重複**（單一所在地）。
- **SC-005**: 桌面 App 呈現為「✓ 可用（共用設定）」；舊「△ 不建議」措辭**完全移除**。
- **SC-006**: 計費 / device-flow / 金鑰 / proxy 零回歸；無新 migration、無新套件。

## Assumptions

- **建立在既有 device-flow（階段 19）+ scoped application credentials（階段 20）+ Agent 相容判定（階段 25 responses 支援）之上**；Codex 一鍵設定沿用既有安裝腳本與授權流程。
- **Agent 相容＝該分配的模型可走 Responses**（重用階段 25 既有 `responses_support` 狀態）；成員端分配清單可能需補一個衍生「Agent 相容」旗標供前端用（不新增表）。
- **v1 應用清單為精選靜態**（只 Codex），不做應用外掛框架；一般 OpenAI 應用（Continue / OpenWebUI / LibreChat）與其「手動建金鑰貼上」路徑留待應用變多時再做。
- **桌面 App「共用設定即可用」基於 2026-06-08 真機實測**；落地時三平台至少各驗一次（沿用階段 19 真機驗收習慣）。
- **平台/技術棧沿用既有，不新增套件、不新增表、不新增 migration**（預期；若 Agent 相容旗標需後端衍生，亦為唯讀計算欄、零 migration）。
