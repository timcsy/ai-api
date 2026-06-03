# Research：行動裝置（手機）體驗強化（RWD）

本功能無 spec 殘留的 NEEDS CLARIFICATION（寬表格取向已於 specify 階段定為**卡片式堆疊**）。
以下為實作前的技術決策，逐條 Decision / Rationale / Alternatives。

---

## R1：寬表格手機呈現機制 — 單一 CSS `.responsive-table` + `data-label` 約定

- **Decision**：在 `index.css` 定義**一個** `.responsive-table` class，封裝「`< md` 時把 `<table>`
  轉成卡片堆疊」的 CSS（`thead` 隱藏、每 `tr` 變卡片有框與間距、每 `td` 變 `flex justify-between`、
  `td::before { content: attr(data-label) }` 顯示欄名）。各寬表格只需：(a) 在 `<Table>`/wrapper 掛
  `.responsive-table`；(b) 每個 body `<TableCell>` 加 `data-label="<欄名>"`。桌機（≥768px）CSS 不生效、
  維持原生表格。
- **Rationale**：
  - **零回歸面最小**——桌機完全不變（CSS 只在 `< md` 生效）；既有所有儲存格 renderer（badge、按鈕、
    link、`DropdownMenu`、可展開 `TagRow`）原封不動，僅多一個 `data-label` 屬性。
  - **單一來源、不 drift**（FR-008）——卡片版面邏輯集中在一個 class，不是每表各寫一套 JSX。
  - **可測**——vitest 可斷言「每 body 格帶 `data-label`」（卡片可讀性的契約）＋「`.responsive-table` 已套用」。
  - shadcn `<TableCell>` 透傳 `...props`，`data-label` 直接可用，無需改元件庫。
- **Alternatives**：
  - **column-config 元件 `<DataTable columns rows>`**（單一 config 渲染兩種版面）：理論最「單一來源」，
    但要把 6+ 個含複雜儲存格（可展開列、多按鈕、徽章）的手寫表全部重構進 config，**回歸風險高、工大**，
    違反「桌機零回歸優先」與 YAGNI。→ 否決。
  - **隱藏次要欄（`hidden sm:table-cell`）**：使用者已明確選卡片式堆疊（要看到全部欄位）。→ 否決。

## R2：手機導覽收合 — shadcn `Sheet` 抽屜 + 漢堡鈕（`< md` 顯示）

- **Decision**：新增 `components/ui/sheet.tsx`（標準 shadcn Sheet，基於**既有** `@radix-ui/react-dialog`）。
  `app-shell.tsx` 在 `< md`：隱藏 inline 主導覽與 email，顯示漢堡鈕（`lucide-react` `Menu`，已有）；點擊
  開啟 `Sheet` 抽屜，內含全部主導覽 + 管理員子導覽目的地 + 身分/登出。`≥ md` 維持現有橫排（不變）。
  既有橫向子導覽列補 `shrink-0 whitespace-nowrap` 防中文字字斷行。
- **Rationale**：Sheet 是行動導覽標準 pattern；**零新 npm 依賴**（Radix Dialog 已是相依，`dialog.tsx`
  已存在於專案）；桌機路徑 `≥ md` 完全不動（零回歸）。漢堡開合與「抽屜含全部目的地」皆可 vitest 驗。
- **Alternatives**：
  - 頂部導覽改可橫向捲動：可達性差（後段易漏看）、與「email 擠掉控制項」問題無解。→ 否決。
  - 自寫 dropdown 選單：等於重造 Sheet，違反 YAGNI 且少了 focus-trap/a11y。→ 否決。

## R3：斷點策略 — 沿用 Tailwind 預設；手機=base，桌機版面掛 `sm:`/`md:`

- **Decision**：沿用 Tailwind 預設斷點。規則統一：
  - **多欄資訊區塊 / 表單列 / 工具列**：base 為單欄／可換行，桌機版面掛 **`sm:`（640px）**
    （`grid-cols-1 sm:grid-cols-N`、`flex-wrap`）。→ 手機（360–414，< sm）一律堆疊。
  - **導覽收合**與**表格卡片化**：以 **`md:`（768px）** 為界（`< md` 收合/卡片、`≥ md` 原樣）。
  - 平板（768–1023）取得接近桌機的完整版面。
- **Rationale**：360–414px 手機全部 < sm(640)，用 base 即手機樣式、`sm:`/`md:` 還原現況 → 桌機零回歸
  最容易保證（所有改動都是「在更小斷點新增手機行為」，桌機 class 不變）。表格/導覽用 `md:` 因其在
  640–767 窄平板仍偏擠，給到 768 較穩。
- **Alternatives**：自訂斷點 → 無必要、徒增心智負擔（YAGNI）。→ 否決。

## R4：全站擠壓根因 — `container.padding` 加手機斷點

- **Decision**：`tailwind.config.ts` 的 `container.padding: "2rem"` 改為
  `padding: { DEFAULT: "1rem", sm: "2rem" }`。
- **Rationale**：現值固定 2rem（左右共 64px），360px 手機有效寬僅 ~296px，**放大全站每一頁**的擠壓。
  手機降為 1rem（共 32px）釋出寬度；`sm:` 以上維持 2rem（桌機零回歸）。一行、最高槓桿。
- **Alternatives**：逐頁改 padding → drift、漏改。→ 否決。

## R5：機械式反模式掃除 — `grid-cols-1 sm:`、`flex-wrap`、`truncate`/`break-all`

- **Decision**：依稽核清單逐處套用既有 Tailwind 工具：
  - 無前綴的 `grid-cols-2/3`（資訊區、dialog 表單列）→ `grid-cols-1 sm:grid-cols-N`。
  - 標題列／工具列／徽章列無 `flex-wrap` → 補 `flex-wrap`（這些在表格容器外、真的會溢出）。
  - 長動態字串（email/slug/指紋/端點 URL）→ `truncate`（容器配 `min-w-0`，呼應經驗教訓
    「grid/flex 子項要 truncate 必須 min-w-0」）或 `break-all`（inline `<code>` URL）。
  - 橫排含中文且會被壓窄者 → `whitespace-nowrap` + 父 `min-w-0` 或 `flex-wrap`，杜絕字字斷行。
- **Rationale**：皆既有工具、零依賴、桌機（`sm:` 還原）不變；以稽核 file:line 為清單一次掃完
  （呼應「加欄位要 grep 所有 sink」的方法論）。
- **Alternatives**：無——這是必要的細修批次。

## R6：TDD 在 RWD 的可測邊界 — 元件行為走 vitest，純視覺走 360px 手動清單

- **Decision**：
  - **可程式化斷言**（先寫失敗 vitest）：手機導覽 Sheet 開合並列出**全部**目的地；`.responsive-table`
    各 body 格帶 `data-label`（且桌機 `<table>` 與手機卡片結構並存於 DOM）；指定需截斷處的 class 存在。
  - **純視覺**（jsdom 無版面引擎、無法測寬度/溢出/折行）：以 `quickstart.md` 的 **360px 逐頁手動清單**
    覆蓋 SC-001/003/004/005/007。
- **Rationale**：誠實面對 jsdom 不計算 layout 的限制；憲章 TDD 要求「凡有行為先測」——有 DOM 行為者
  一律先測，純 CSS 視覺以可重現的手動清單驗收，並在 plan/quickstart 明示分工，非規避。
- **Alternatives**：導入 Playwright + 真實瀏覽器量測視覺 → 3b.7 已 descope（不重啟）、與「零新依賴/工具」
  衝突、CP 值低。→ 否決（沿用既有決策）。

## R7：「已做對、別動」清單（防回歸，FR-009/011）

- **Decision**：以下既有正確響應式區域**不更動**：
  - shadcn `<Table>` 內建 `overflow-auto` wrapper（卡片化是**新增** `.responsive-table` 行為、不移除既有）。
  - recharts `ResponsiveContainer width="100%"`（圖表自動縮）。
  - heatmap 的 `overflow-x-auto`、token/curl `<pre>` 的 `overflow-x-auto break-all`。
  - catalog 的 `grid-cols-1 md:grid-cols-[260px_1fr]`、成本 Badge 的 `shrink-0 whitespace-nowrap`、
    `time-range-select` 的 `flex-wrap`。
- **Rationale**：稽核已確認這些在手機正確；改動只會帶來回歸。明確列清單避免「順手改壞」。

## R8：桌機零回歸保證策略（FR-010 / SC-006）

- **Decision**：(a) 所有改動皆為「在 `< sm`/`< md` 新增手機行為」，桌機斷點 class 不動；
  (b) 既有全套 vitest（109）須維持綠；(c) 卡片化 CSS 以 `.responsive-table` 的 `@media (max-width: …)`
  包覆，`≥ md` 完全不生效；(d) quickstart 含「≥768px 目視與實作前一致」一項。
- **Rationale**：把「零回歸」變成可檢查的結構性保證（改動方向單向、測試守門、CSS 媒體查詢邊界明確）。

---

## 小結

- 零新 npm 依賴、零後端/DB 變更、桌機零回歸。
- 新增檔：`ui/sheet.tsx`（shadcn，基於既有 Radix Dialog）、`index.css` 的 `.responsive-table` 區塊。
- 修改：`tailwind.config.ts`（container padding）、`app-shell.tsx`（手機導覽）、各路由手機斷點 class。
- 測試分工已明確：元件行為 vitest（先 Red）＋ 360px 手動驗收清單。
