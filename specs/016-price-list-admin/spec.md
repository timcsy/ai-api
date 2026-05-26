# Feature Specification: 價目表管理 UI (Price List Admin)

**Feature Branch**: `016-price-list-admin`
**Created**: 2026-05-26
**Status**: Draft
**Input**: User description: "價目表管理 UI：admin 在介面檢視各 (provider, model) 目前生效價目與歷史版本、新增價目版本（append-only point-in-time 不覆寫歷史）；從 catalog 帶出模型清單、缺價目標未定價；保留既有 YAML+CLI 匯入。不做供應商自動同步、多幣別、編輯刪除既有版本"

## 問題陳述

價目表（`price_list`，計費用的 point-in-time 價格來源）目前**只有後端**：admin 必須手寫 YAML 再跑 `python -m ai_api.cli.load_prices <yaml>` 載入，介面上看不到也改不了。

更實際的問題：YAML 只含階段 3a 時的舊 Azure 模型（`gpt-4o`、`gpt-4o-mini`）。階段 5 之後 catalog 改用多 provider 與新 slug（如 `azure/gpt-5.4-mini`、Anthropic、Gemini 等），這些模型在價目表裡**沒有任何價格**。計費時系統以「呼叫時記錄的 model（去 provider 前綴）」查價，查無即無價 → **這些模型的用量成本算出來是 0**。帳目因此有洞，違反「分配本質要求帳目清楚」。

本 feature 讓 admin 在介面**檢視**每個模型目前生效的價格與歷史版本、**新增**價格版本（append-only，沿用 point-in-time，不覆寫歷史也不影響歷史帳），並**一眼看出哪些模型未定價**。既有的 YAML + CLI 批次匯入保留。

本 feature **不改既有計費 / point-in-time 查價機制**——只是把「維護價目」從 CLI-only 補上一個 admin UI 與對應 API。**不新增資料表**（沿用既有 `price_list`）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin 檢視價目與未定價模型 (Priority: P1)

Admin 想知道目前每個 catalog 模型的生效價格是多少、以及哪些模型還沒定價（會導致成本算成 0）。

**Why this priority**：看不到現況就無從補價；「未定價」可見性直接點出帳目破洞。

**Independent Test**：載入價目頁，看到每個 catalog 模型一列、顯示其目前生效的 input/output 單價或「未定價」標示；對只有舊價目的環境，新模型顯示「未定價」。

**Acceptance Scenarios**：
1. **Given** 價目表有某 (provider, model) 的價格，**When** admin 開價目頁，**Then** 該模型顯示目前生效的 input/output 每 1K tokens 單價與生效日
2. **Given** 某 catalog 模型在價目表中無任何價格，**When** admin 開價目頁，**Then** 該模型明確標示「未定價」
3. **Given** 同一模型有多個歷史價格版本，**When** admin 檢視，**Then** 顯示的是「目前生效」（`effective_from <= 現在` 的最新）那一筆

### User Story 2 — Admin 新增價目版本 (Priority: P1)

Admin 想為某模型（特別是未定價的新模型）設定價格，或為既有模型發布調價，且不破壞歷史帳。

**Why this priority**：這是補帳的動作；沒有它就只能繼續手寫 YAML。

**Independent Test**：對一個未定價模型新增一筆價格版本（input/output 單價 + 生效日），儲存後該模型在頁面顯示新價格；該模型之後的呼叫用新價、先前的歷史用量帳不變。

**Acceptance Scenarios**：
1. **Given** admin 在價目頁，**When** 對某 (provider, model) 新增一筆價格（input、output 每 1K tokens、生效日、來源備註），**Then** 版本被建立且不覆寫任何既有版本
2. **Given** 某模型已有 5/1 生效的價格，**When** admin 新增一筆 6/1 生效的新價，**Then** 6/1 後的呼叫用新價、5/1–5/31 的歷史用量成本仍用舊價（point-in-time 不變）
3. **Given** admin 嘗試對同一 (provider, model, 生效日) 重複新增，**Then** 被拒並提示「該生效時間已有版本」
4. **Given** admin 輸入負數或非法單價，**Then** 被拒並提示格式錯誤

### User Story 3 — Admin 檢視某模型的歷史價格 (Priority: P2)

Admin 想稽核某模型過去各時間點的定價，確認歷史帳的計價依據。

**Why this priority**：稽核與信任用，非補帳必要；排在檢視+新增之後。

**Acceptance Scenarios**：
1. **Given** 某模型有多個價格版本，**When** admin 展開該模型，**Then** 依生效日列出所有版本（含 input/output 單價、生效日、來源備註、建立資訊）
2. **Given** 檢視歷史，**When** 顯示，**Then** 標示出哪一筆是「目前生效」

### Edge Cases

- **catalog 模型多、價目少**：頁面以 catalog 為主清單，逐一標「已定價 / 未定價」
- **價目表有、但 catalog 已無的模型**（舊模型移除）：仍可在歷史中看到，不報錯（用於稽核舊帳）
- **未來生效日**（`effective_from` 在未來）：可新增；「目前生效」仍取 `<= 現在` 的最新，未來版本標示為「排程生效」
- **provider/model 對應**：價目以「呼叫時記錄的 model 字串（去 provider 前綴）+ provider」為 key，與計費查價一致；UI 從 catalog 帶出正確 key，避免 admin 拼錯
- **CLI 同時在用**：UI 新增與 CLI 匯入寫的是同一張表；重複 (provider, model, 生效日) 兩邊都受同一唯一性約束保護
- **單價精度**：保留既有高精度（每 1K tokens，可到小數點後多位）

## Requirements *(mandatory)*

### Functional Requirements

**檢視**
- **FR-001**: 系統 MUST 讓 admin 列出 catalog 模型，逐一顯示其「目前生效」價格（input/output 每 1K tokens 單價 + 生效日）或「未定價」
- **FR-002**: 「目前生效」MUST 定義為 `effective_from <= 現在` 中 `effective_from` 最新的一筆（沿用既有 point-in-time 查價語意）
- **FR-003**: 系統 MUST 明確標示沒有任何價格版本的模型為「未定價」
- **FR-004**: 系統 MUST 能列出某 (provider, model) 的所有歷史價格版本，並標示哪一筆目前生效

**新增**
- **FR-005**: admin MUST 能為某 (provider, model) 新增一筆價格版本：input 單價、output 單價、生效日、來源備註
- **FR-006**: 新增 MUST 是 append-only：不覆寫、不刪除任何既有版本
- **FR-007**: 系統 MUST 拒絕重複的 (provider, model, 生效日)，並回明確錯誤
- **FR-008**: 系統 MUST 驗證單價為非負數值；非法輸入拒絕並提示
- **FR-009**: 新增價格 MUST 不影響任何**已發生**呼叫的成本（point-in-time，歷史帳不變）
- **FR-010**: 新增價格 MUST 寫稽核事件（誰、何時、哪個 model、生效日）

**相容性**
- **FR-011**: 既有計費 / point-in-time 查價 MUST 不因本 feature 改變行為
- **FR-012**: 既有 YAML + `load_prices` CLI 批次匯入 MUST 仍可用，與 UI 寫同一張表
- **FR-013**: 價目以「呼叫時記錄的 model 字串（去 provider 前綴）+ provider」為 key，與計費查價的比對一致；UI MUST 從 catalog 帶出此 key，降低 admin 拼錯風險

### Key Entities

- **PriceList（既有，不改 schema）**：append-only point-in-time 價格。屬性：provider、model（去 provider 前綴的識別字）、input 每 1K tokens 單價、output 每 1K tokens 單價、生效日、來源備註、建立資訊。唯一性：(provider, model, 生效日)。**本 feature 不新增欄位或資料表**，只新增檢視 / 新增的 API 與 UI。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: admin 能在價目頁一眼看出**所有未定價的 catalog 模型**（100% 標示），不需查 DB 或 YAML
- **SC-002**: admin 能在 **2 分鐘內**為一個未定價模型新增價格並在頁面看到生效
- **SC-003**: 為現行多 provider 模型補齊價格後，觀測→用量的成本**不再為 0**
- **SC-004**: 新增 / 調價對**已發生**呼叫的成本零影響（point-in-time 回歸測試通過）
- **SC-005**: 重複 (provider, model, 生效日) **100%** 被擋並有明確提示
- **SC-006**: 既有計費與 CLI 匯入測試**零回歸**

## Assumptions

- 幣別沿用既有 **USD per 1K tokens**，不做多幣別 / 匯率（YAGNI）
- 價格**只新增不編輯/刪除**（append-only）；改價 = 發新生效日版本（保 point-in-time 與稽核）
- 不做「從供應商自動同步價目」（YAGNI；人工 / CLI + UI 即可）
- 價目 key 沿用計費查價現況：`provider` + `model = 呼叫 model 字串去掉 "<provider>/" 前綴`（已於 `proxy/router.py` 確認 `requested_model.split("/",1)[-1]`）
- UI 位置與既有 admin 資訊架構一致（放在觀測或 Model 區，由 plan 階段決定），不新增頂層 sub-nav（沿用階段 5.1 精簡原則）
- 不做成本預測 / 估價試算（只維護價目本身）
