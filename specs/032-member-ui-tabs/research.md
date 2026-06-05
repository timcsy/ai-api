# Phase 0 研究：會員介面分頁化

純前端重組。無新技術、無新套件、無後端。研究聚焦在「既有路由 / 元件 / 測試怎麼搬」的具體決策。

## Decision 1：用獨立路由頁，非 dashboard 內 tabs

- **Decision**：新增 4 條會員路由 `/keys`、`/allocations`、`/usage`（`/catalog` 已存在），各為獨立 URL；頂部 `MAIN_NAV` 加對應項。**不**用 dashboard 內的 `<Tabs>`。
- **Rationale**：會員已選「頂部導覽分頁(推薦)」。獨立 URL 才能深連結、書籤、重新整理（spec FR-001/SC-001），與既有 admin `/admin/observability/*` 子路由模式一致。
- **Alternatives rejected**：dashboard 內 `<Tabs>`——切頁不換 URL，無法深連結，且仍是「一個元件塞全部」的變形。

## Decision 2：路由命名與既有 `/dashboard/allocations/:id` 深連結相容

- **Decision**：
  - 分配列表頁用 **`/allocations`**（新），單筆詳情**維持** `/dashboard/allocations/:id`（不動，零風險）。
  - 金鑰頁 `/keys`、用量頁 `/usage`。
  - `/dashboard` 仍存在，改為「精簡總覽」。
- **Rationale**：`/dashboard/allocations/:id` 已是線上深連結（memory 載明邊緣路由敏感），改它要動 nginx 與既有書籤；保留即零回歸（FR-010/SC-005）。列表頁用新短路徑 `/allocations`，語意清楚。
- **Alternatives rejected**：把詳情改成 `/allocations/:id`——需加 redirect 且無實益；徒增風險。

## Decision 3：元件純搬移，不改內部邏輯

- **Decision**：既有自足元件直接搬到新頁，幾乎零改動：
  - **金鑰頁** `/keys`：`AppCredentialsCard` + 「API 端點」卡（從 dashboard 抽出）+ `CodexInstallCard` + token 提示 `Alert`。
  - **分配頁** `/allocations`：可自助領取區 + 「我的分配」卡列（含 `includeRevoked` switch、領取 dialog）——即 dashboard 現有 section 整段搬出。
  - **用量頁** `/usage`：`UsageSummary` + `TimeRangeSelect` + `MemberUsageCharts`。
  - **儀表板** `/dashboard`：新寫精簡總覽元件。
- **Rationale**：原則 5 集中管理——每塊已是獨立元件，搬移即達成「每件事單一所在地」，符合 YAGNI（憲章 V），不引入新抽象。
- **Alternatives rejected**：重寫元件——違反 YAGNI、徒增回歸面。

## Decision 4：精簡總覽資料來源全為既有端點

- **Decision**：總覽 `/dashboard` 用既有 query：
  - 本月用量/花費 → `UsageSummary`（已有）或其底層 `/me/usage`。
  - 活躍分配數 → `/me/allocations`（filter active）。
  - 活躍金鑰數 → `/me/credentials`（filter active）。
  - 待辦：無金鑰（`/me/credentials` 空）→ 連 `/keys`；有可領取（`/me/claimable-models` 非空）→ 連 `/allocations`。
  - 快速接入：`CodexInstallCard`（精簡呈現或連 `/keys`）。
- **Rationale**：零新端點（FR-010）。所有資料 hooks 已存在於 dashboard。
- **Alternatives rejected**：新增 `/me/summary` 聚合端點——違反「純前端、無後端」範圍與 YAGNI。

## Decision 5：「分配 vs 金鑰」一句話放法

- **Decision**：在 `/allocations` 與 `/keys` 頁首各放一個淺色說明列（`Alert` 或 `p.text-muted-foreground`）：「**分配**＝你能用哪些模型；**金鑰**＝拿來連線的鑰匙」。
- **Rationale**：FR-006/SC-003；原則 6 可達性。成本極低。

## Decision 6：金鑰卡「編輯」合一

- **Decision**：`AppCredentialsCard` 把「改名」「編輯 model」兩顆按鈕併為單一「**編輯**」，開單一 dialog：上方 `Input`（名稱）＋下方 checkbox 清單（可用 model），一次 PATCH 同時送 `name` + `add`/`remove`。`renameMut`/`patchMut` 合一或單次 PATCH（後端 PATCH 已支援 name + add + remove 同送，見 `test_credential_rename.py::test_rename_with_scope_change_together`）。「重新產生」「撤回」維持獨立。
- **Rationale**：FR-008；後端早已支援單一 PATCH 同送 name+scope，前端只是合 UI。
- **Alternatives rejected**：保留兩顆——正是要修的混亂。

## Decision 7：admin Provider「Rotate」中文化

- **Decision**：`routes/admin/providers.tsx` 面向使用者的字串 `Rotate`→「重新產生金鑰」、`Rotate Credential`→「重新產生上游金鑰」、toast「Rotate 失敗」→「重新產生失敗」。**保留**程式識別字（`rotateMut`、`rotateForm`、API path `/rotate`、zod schema 名）不變。
- **Rationale**：FR-009；憲章「識別字用英文、對外文案中文」。功能不變。

## Decision 8：測試策略（TDD）

- **Decision**：先改/加失敗測試再實作：
  - `app-shell.test.tsx`：斷言新導覽項「金鑰/分配/用量」存在且可導航。
  - `mobile-nav.test.tsx`：手機選單含新項。
  - `dashboard.test.tsx`：斷言儀表板**只**顯示總覽（不再有金鑰卡標題、用量圖表標題、分配卡列）；待辦提示連結正確。
  - 新增 `keys-page.test.tsx`、`allocations-page.test.tsx`、`usage-page.test.tsx`（各頁渲染對應元件 + 一句解釋）。
  - `legacy-redirects.test.tsx`：確認 `/dashboard/allocations/:id` 仍可達。
  - 金鑰卡：加/改測試斷言單一「編輯」dialog 同送 name+scope。
- **Rationale**：憲章 I Test-First（NON-NEGOTIABLE）。
