# Contracts: 應用分頁

## 1. `GET /me/allocations`（既有端點，加唯讀衍生欄）

每筆回應**新增**：
```jsonc
{
  "id": "...", "resource_model": "azure/gpt-5.4", "display_name": "GPT-5.4",
  "status": "active", "price": {...}, "token_prefix": "...",
  "agent_compatible": true   // 新增：該模型可走 Responses（Codex/Agent）→ true
}
```
- `agent_compatible` = 該分配模型的 `responses_support.state === "available"`（讀既有 capabilities 標記）。
- orphan / unknown / unavailable → `false`。
- 其餘欄位、排序、權限（`current_member` 隔離）**不變**。

## 2. 建金鑰捷徑 — 重用 `POST /me/credentials`（既有端點，無新契約）

Codex 卡「為 Codex 建金鑰」呼叫既有端點：
```jsonc
// request
{ "name": "Codex", "allocation_ids": ["<agent_compatible 分配 id…>"] }
// response（既有）：token 僅顯示一次
{ "id": "...", "token": "aiapi_...", ... }
```
- 前端 picker MUST 只列 `agent_compatible === true && status === "active"` 的分配（預先全選，可取消）。
- `allocation_ids` MUST ⊆ agent_compatible（前端保證；後端維持既有驗證行為不變）。

## 前端 UI 契約

### 導覽 + 路由
- `MAIN_NAV` 加 `{ to: "/apps", label: "應用" }`（成員可見）。
- `App.tsx` 加 `<Route path="/apps" element={<ApplicationsPage/>} />`。

### `/apps`（ApplicationsPage）— v1 單一 Codex 卡
- **狀態**：依 `/me/allocations` 算 `agentAllocs`：
  - >0 → 顯示「可用」+ 一鍵設定 + 「為 Codex 建金鑰」。
  - =0 → 顯示「目前沒有可用於 Codex 的模型」+ 指引連結（模型目錄 / 請 admin），**不**顯示建立按鈕。
- **一鍵設定**：渲染既有 `CodexInstallCard`（device-flow 一鍵）。
- **建金鑰捷徑**：開聚焦建立流程（picker = agentAllocs 預選、名稱預設「Codex」）→ `POST /me/credentials` → token 顯示一次。
- **多介面**：列 CLI（自動）/ VS Code 擴充（連結或可選自動）/ 桌面 App（連結，「裝好免再設定」）/ Cursor·JetBrains（連結）。

### `codex-install-card.tsx`（文案更新）
- 桌面 App 段：「△ 不建議」→ **「✓ 用一鍵安裝後也能用（共用 `~/.codex` 設定、免再設定）」**。
- 網頁版維持「✗ 不適用」。

### 收斂
- `member-overview.tsx`（dashboard）與 `routes/keys.tsx` **移除** `CodexInstallCard`（搬到 `/apps`）。

## 測試契約（連動更新）
- `mobile-nav.test.tsx`：`MAIN_NAV` 期望清單加「應用」。
- `app-shell.test.tsx`：若列舉目的地，補 `/apps` route stub。
- `codex-install-card.test.tsx`：若斷言「△ 不建議」字樣 → 改為新 ✓ 文案。
- 後端：`/me/allocations` 回 `agent_compatible`（available→true、unknown/unavailable/orphan→false）。
