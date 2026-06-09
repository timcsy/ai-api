# Quickstart: 應用分頁（手動驗收）

前置：起後端 + 前端、登入成員；該成員有數個分配（部分 Agent 相容[模型 responses 可用]、部分不是）。

## US1 — 應用分頁 + Codex 一鍵設定（P1 🎯）
1. 成員導覽點「應用」。
   - ✅ 進到 `/apps`，看到 Codex 卡（含「這是什麼」+ 一鍵設定）。
2. 取得一鍵設定指令/流程。
   - ✅ 與既有 device-flow 一鍵安裝一致；照做後 Codex 能呼叫本平台。
3. 看 dashboard 與金鑰頁。
   - ✅ 不再出現 Codex 安裝卡（已收斂到 `/apps`，無重複）。

## US2 — 建金鑰捷徑（scope 預選 Agent 相容）（P1）
1. Codex 卡按「為 Codex 建金鑰」。
   - ✅ picker **只列** Agent 相容分配（預先全選），非相容的不出現。
2. 完成建立。
   - ✅ 建出的金鑰 scope 只含 Agent 相容分配；token 只顯示一次。
3. 用一個**沒有任何 Agent 相容分配**的成員進 Codex 卡。
   - ✅ 顯示「目前沒有可用於 Codex 的模型」+ 指引；**沒有**建立按鈕（不讓他建無效金鑰）。

## US3 — 多介面說明（P2）
1. 看 Codex 卡介面區。
   - ✅ 分「能自動（CLI、可選 VS Code 擴充）」與「給連結（桌面 App、Cursor、JetBrains）」；後者標「裝好免再設定」。
2. 看桌面 App 呈現。
   - ✅ 「✓ 用一鍵安裝後也能用（共用設定）」；**無**舊「△ 不建議」字樣。
3. （若有做）一鍵安裝在偵測到 `code` 時。
   - ✅ 可選裝 VS Code 擴充；偵測不到則略過、不報錯。

## 零回歸 / 後端（SC-006）
1. `GET /me/allocations` 每筆有 `agent_compatible`（Agent 相容模型 true、其餘 false、orphan false）。
2. device-flow、金鑰建立、計費、proxy 行為不變；金鑰頁 `app-credentials-card` 完整管理仍在。
3. `alembic heads` 不變、無新 migration；`pip` / `npm` 依賴無新增。
4. **三平台煙霧**（沿用階段 19 習慣）：至少在一台跑「CLI 一鍵安裝 → Codex CLI 可用 → 開桌面 App 共用設定也可用」。
