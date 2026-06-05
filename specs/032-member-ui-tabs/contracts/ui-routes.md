# UI 契約：會員路由 + 導覽

本功能不暴露 API 契約（純前端）。此處定義**前端路由與導覽**契約，作為測試斷言依據。

## 會員路由表（`App.tsx`，皆於 `ProtectedRoute > AppShell` 下）

| 路徑 | 元件 | 狀態 | 內容 |
|---|---|---|---|
| `/` | `Navigate → /dashboard` | 既有，不變 | — |
| `/dashboard` | `DashboardPage`（精簡總覽） | **改** | member-overview：用量摘要 + 金鑰數 + 分配數 + 快速接入 + 待辦 |
| `/keys` | `KeysPage` | **新** | API 端點卡 + `AppCredentialsCard` + `CodexInstallCard` + 一句解釋 |
| `/allocations` | `AllocationsPage` | **新** | 可自助領取 + 我的分配卡列 + 一句解釋 |
| `/usage` | `UsagePage` | **新** | `UsageSummary` + `TimeRangeSelect` + `MemberUsageCharts` |
| `/dashboard/allocations/:id` | `AllocationDetailPage` | 既有，**不動** | 單筆分配詳情（深連結保留） |
| `/catalog`、`/catalog/*` | `CatalogPage` / `CatalogDetailPage` | 既有，不變 | 模型目錄 |

**契約測試**：每條新路徑直接以 URL 開啟（render at path）須載入對應元件並可重新整理；`/dashboard/allocations/:id` 維持可達。

## 導覽契約（`app-shell.tsx` `MAIN_NAV`）

桌機頂部 + 手機選單共用同一 `MAIN_NAV`，會員可見順序：

```
我的儀表板(/dashboard) · 金鑰(/keys) · 分配(/allocations) · 用量(/usage) · 模型目錄(/catalog)
```

- admin 額外 `管理員(/admin)` 項與 `ADMIN_SUBNAV` 不變。
- **契約測試**：`app-shell.test.tsx` 斷言會員看到 5 項且文字為「金鑰/分配/用量」（非「我可用的模型」）；點擊各項導到對應路徑。`mobile-nav.test.tsx` 斷言手機 `Sheet` 選單含同 5 項。

## 一句解釋契約

- `/allocations` 與 `/keys` 頁首各含文字節點：含「分配」與「金鑰」且表達「分配＝能用什麼；金鑰＝拿來連線的鑰匙」之意。
- **契約測試**：各頁 `getByText(/分配＝.*金鑰＝/)` 或等義 matcher 命中。

## 精簡總覽契約（`/dashboard`）

斷言**存在**：本月用量/花費摘要、活躍金鑰數、活躍分配數、安裝 Codex 快速接入、待辦提示。
斷言**不存在**（已搬走）：`AppCredentialsCard` 完整表格、「用量圖表」標題 + `MemberUsageCharts`、「我的分配」整列卡片。
待辦連結：無金鑰 → `href`/導航至 `/keys`；有可領取 → 至 `/allocations`。

## 金鑰卡「編輯」合一契約（`app-credentials-card.tsx`）

- 每把使用中金鑰的操作列為：**編輯** · 重新產生 · 撤回（不再有獨立「改名」「編輯 model」兩顆）。
- 「編輯」開單一 dialog：名稱 `Input` + 可用 model checkbox；按「儲存」送單一 `PATCH /me/credentials/{id}` 帶 `name`（若變更）+ `add`/`remove`（差集）。
- **契約測試**：點「編輯」→ 改名 + 勾選變更 → 儲存 → 斷言發出一次 PATCH 且 body 同時含 `name` 與 scope 差集。

## admin Provider「Rotate」中文化契約（`routes/admin/providers.tsx`）

- 對外可見文字：按鈕「重新產生金鑰」、dialog 標題「重新產生上游金鑰」、submit「重新產生」、toast「重新產生失敗」。
- 程式識別字（`rotateMut`、`rotateForm`、`rotateSchema`、API path `/admin/providers/{id}/rotate`）**不變**。
- **契約測試**：providers 頁無 `getByText("Rotate")`；有中文等義按鈕。
