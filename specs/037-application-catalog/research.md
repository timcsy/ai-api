# Phase 0 Research: 應用分頁（應用目錄）—— Codex 為第一個應用

## D1 — 「Agent 相容」旗標放在 `/me/allocations`（衍生、零 migration）

**Decision**：`GET /me/allocations` 的每筆序列化（`_alloc_public`）加唯讀欄 `agent_compatible: bool`。list 端點本就載 `slug→display_name`（從 `ModelCatalog`），擴充成同時載 `slug→capabilities`，用 `responses_support.get_support(caps)["state"] == "available"` 計算。

**Rationale**：建金鑰捷徑要「只列 Agent 相容分配」、卡片狀態要「你有沒有可用於 Codex 的模型」——都需要逐分配知道其模型可否走 Responses。階段 25 的 `responses_support` 已是這個真相來源（存在 `capabilities` 標記），這裡只是把它**沿著既有 `/me/allocations` 序列化暴露**，查詢層計算、零 schema 變更。

**Alternatives considered**：
- **前端交叉比對 `/catalog/models`**（已含 `responses_support`）：要前端自己 join 兩個清單、且 catalog 受可見性過濾（可能看不到某些 slug）→ 易漏。否決。
- **新端點 `/me/agent-compatible-allocations`**：多一個端點，YAGNI；衍生欄更省。否決。

## D2 — 應用頁與路由

**Decision**：新 `routes/apps.tsx`（`ApplicationsPage`），`App.tsx` 加 `<Route path="/apps">`，`app-shell.tsx` 的 `MAIN_NAV` 加 `{ to:"/apps", label:"應用" }`。頁面 v1 只渲染一張 Codex 應用卡。

**Rationale**：與既有成員頁（金鑰/分配/用量/模型目錄）同層的頂部分頁，符合階段 22「每件事單一所在地」。
**測試連動**：`mobile-nav.test.tsx` 的 `MAIN_NAV` 期望清單要加「應用」；`app-shell.test.tsx` 若列舉目的地要補 route stub（呼應 experience「改 UI 顯示字串要連帶改測試」）。

## D3 — CodexInstallCard 收斂去重（FR-003）

**Decision**：`CodexInstallCard` 目前同時出現在 `member-overview.tsx`（dashboard）與 `routes/keys.tsx`（金鑰頁）。把它**移到 `/apps`**，從這兩處移除。元件本身保留（`/apps` 引用），其單元測試 `codex-install-card.test.tsx` 不受搬移影響。

**Rationale**：單一所在地（FR-003 / SC-004），避免兩處 drift。安裝是「應用」的事、不是「金鑰」或「儀表板」的事。
**注意**：dashboard / keys 頁若有測試斷言該卡存在，需改為斷言它**不在**那裡、或不檢查（搬家）。

## D4 — 建金鑰捷徑（重用 `POST /me/credentials`，無新端點）

**Decision**：Codex 卡「為 Codex 建金鑰」開一個聚焦的建立流程：分配 picker **只列 `agent_compatible === true`** 的分配（預先全選）、名稱預設「Codex」、呼叫既有 `POST /me/credentials`（body `{name, allocation_ids}`）。token 顯示一次（既有行為）。完整金鑰管理仍在金鑰頁的 `app-credentials-card`。

**Rationale**：把「應用金鑰」概念正門化（原則 1：scoped application credential = 一把 key 綁一組分配）。重用既有端點、零新後端面；預過濾 Agent 相容是捷徑的核心價值（避免成員挑到 Codex 接不上的模型）。

**Edge（FR-006）**：`agent_compatible` 分配數為 0 → 卡片狀態顯示「你目前沒有可用於 Codex 的模型」+ 指引（去模型目錄領取 / 請 admin 授權），**不**開建立流程。

## D5 — 桌面 App 文案 △→✓（FR-008，實測修正）

**Decision**：`codex-install-card.tsx` 目前「△ 技術上可以、但目前不建議」（針對在 App GUI 手動填 API key 會踩 openai/codex#24457）。改為 **「✓ 用一鍵安裝這條路，桌面 App 也能用」**——因為走「先跑 CLI 一鍵安裝 → App 讀共用 `~/.codex`」**實測可用**（2026-06-08 真機）。保留一句技術說明（共用設定、免再設定），移除「不建議」。網頁版仍「✗ 不適用」。

**Rationale**：實測為真理；舊 △ 是針對「App 自己手動設定」那條路，本功能推薦的是「CLI 安裝→App 共用設定」這條,△ 對此不成立。

## D6 — VS Code 擴充「順手自動裝」：先驗證再決定（FR-007/009）

**Decision**：v1 **預設給 marketplace 連結**；只有在能**可靠確認 Codex 的 VS Code extension id** 時，才在安裝腳本加「偵測到 `code` → `code --install-extension <id>`」的可選步驟。無法可靠確認則 v1 link-only。

**Rationale**：呼應 experience「採用前先驗證 SDK 的能力邊界…臆測導向的保險往往是 YAGNI 違反」——裝錯 extension id 比沒自動裝更糟。能可靠自動的（CLI 既有）才自動。桌面 GUI App / Cursor / JetBrains 一律連結（FR-009 不做萬能安裝器）。
**待辦**：實作時查證 Codex 官方 VS Code extension id；查不到 → link-only、不阻塞 v1。

## D7 — 零回歸（FR-010）

**Decision**：不改 device-flow、金鑰建立端點、計費、proxy；只加 `/me/allocations` 衍生欄 + 前端頁面/導覽/卡片搬移。
**Rationale**：SC-006 零回歸；新增面最小。
