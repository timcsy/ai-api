# Data Model：行動裝置（手機）體驗強化（RWD）

**本功能不涉及資料模型**——純前端呈現層調整，無新表、無 migration、無 API/欄位變更、無實體。

以下僅記錄與本功能相關的**前端 UI 結構約定**（非資料庫實體），供任務與測試對齊。

## UI 結構約定（非持久化）

### 1. 響應式表格 `data-label` 約定

每個套用 `.responsive-table` 的表格，其 body 儲存格（`<TableCell>`）必須帶 `data-label="<欄名>"`，
欄名與該欄表頭（`<TableHead>`）文字一致。手機卡片化時 `data-label` 即每列卡片內的欄位標籤。

| 屬性 | 意義 | 規則 |
|------|------|------|
| `.responsive-table`（class） | 標記此表格啟用「手機卡片化」 | 掛在 `<Table>` 或其 wrapper |
| `data-label`（每 body 格） | 手機卡片內顯示的欄位標籤 | 必填；值＝對應表頭文字 |

> 桌機（≥768px）：`data-label` 無視覺作用，表格照常多欄呈現。

### 2. 導覽目的地清單（手機抽屜須涵蓋全部）

手機 `Sheet` 抽屜內須包含與桌機相同的全部導覽目的地，無遺漏：

- **主導覽**：我的儀表板（`/dashboard`）、模型目錄（`/catalog`）、管理員（`/admin`，僅 admin）
- **管理員子導覽**（僅 admin）：首頁、Model、成員、Tag、Provider 憑證、存取、通知、觀測
- **身分/操作**：目前登入 email、登出

> 此清單為 `contracts/ui-contracts.md` 之導覽契約的資料來源；US1 的 vitest 以「抽屜列出全部目的地」斷言。

## 狀態

僅一個前端 UI 狀態：手機導覽抽屜的開/合（`Sheet` open state）。非持久化、無後端往返。
