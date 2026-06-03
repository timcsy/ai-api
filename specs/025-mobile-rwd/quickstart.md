# Quickstart：360px 手機驗收清單

本功能的視覺正確性無法以 jsdom 單元測試（無版面引擎），以此清單在 **360px 寬**手動驗收。
工具：Chrome DevTools 裝置工具列設 360×800（或真機）。每頁三問：**(A) 整頁無水平捲動？
(B) 無中文字字斷行？(C) 無長字串撐破卡片？** 另含各頁專屬檢查點。對應 SC-001/003/004/005/007。

> 桌機零回歸（SC-006）：另在 ≥768px 目視每頁與實作前一致，並確認 `npm --prefix frontend run test` 全綠。

## 前置

```bash
npm --prefix frontend run dev   # 或對 live 環境（ai-ccsh.tew.tw）以手機開啟
```
以 admin 與一般成員兩種身分各驗一輪（成員只看得到成員端頁）。

## 殼層 / 導覽（US1）

- [ ] 頂部出現漢堡鈕；inline 主導覽與 email 在手機隱藏，未把登出擠出畫面
- [ ] 點漢堡 → 抽屜開啟，列出**全部**目的地：我的儀表板 / 模型目錄 / 管理員 + 管理員子導覽
      8 項（首頁/Model/成員/Tag/Provider 憑證/存取/通知/觀測）+ email + 登出
- [ ] 管理員子導覽（若仍橫排）各項不字字斷行、可橫向捲動到最後一項
- [ ] 長 email 帳號登入時，頂部列不溢出

## 管理員頁（US2 + US3）

逐頁三問 (A)(B)(C) + 專屬點：

- [ ] **首頁 home**：quarantine 警示卡、設定清單、系統資訊兩欄 grid 在手機堆疊單欄；圖表單欄不溢出
- [ ] **用量 usage**：下載按鈕列換行不溢出；篩選列換行；8 欄表→**卡片式堆疊**（每列一卡、欄位齊全）；
      tag 下鑽展開的明細表亦不溢出
- [ ] **分配 allocations**：頂部工具列（兩開關 + 新增鈕 + 標題）換行不溢出；7 欄表→卡片；
      「已不在 catalog」徽章不字字斷行；隔離原因 popover 在手機可開可讀
- [ ] **成員 members**：7 欄表→卡片；email 不撐破
- [ ] **成員詳情 member-detail**：登入方式/狀態/管理員三欄資訊堆疊單欄；內層分配表→卡片
- [ ] **供應商 providers**：7 欄表→卡片；列上多操作（測試/輪替/停用）收於選單、一螢幕寬可達
- [ ] **價目 prices**：6 欄表→卡片；新增 dialog 表單兩欄堆疊單欄
- [ ] **Tag tags**：頂部 3 顆按鈕 + 標題換行不溢出；表→卡片
- [ ] **Tag 規則 tag-rules**：條件欄長 regex 不撐破；表→卡片
- [ ] **存取 access**：兩個表→卡片；CIDR/pattern `<code>` 不溢出
- [ ] **模型詳情 model-detail**：Provider/Cost tier/Context 三欄資訊堆疊；編輯 dialog 兩欄堆疊
- [ ] **通知 notifications**：SMTP host/port、寄件者 email/name 兩欄堆疊單欄；密碼指紋不溢出
- [ ] **觀測 observability**：次級 tab 列不字字斷行、可捲動

## 成員端頁（US2 + US3）

- [ ] **儀表板 dashboard**：端點 URL / gateway URL 的 inline `<code>` 不撐破卡片（break-all）；
      claim 卡與分配卡 flex 換行、徽章不字字斷行；本月用量大數字不溢出
- [ ] **型錄 catalog**：（已正確）grid 單欄；model 卡模態串與價格串不溢出
- [ ] **型錄詳情 catalog-detail**：關係卡 flex 換行；價格三欄換行不溢出；token dialog `<pre>` 可橫捲
- [ ] **分配詳情 allocation-detail**：標題長 display_name 不擠掉狀態徽章；憑證卡按鈕群換行；
      五欄「最近呼叫」→卡片或可橫捲、不擠爆
- [ ] **登入 login / 404**：（簡單置中）無溢出

## 「已做對、別動」回歸抽查（FR-009/011）

- [ ] 圖表（首頁/用量）仍自動縮放、heatmap 仍可橫捲
- [ ] token/curl `<pre>` 仍可橫捲且不撐破頁
- [ ] catalog grid、成本 Badge、time-range-select 行為不變

## 桌機零回歸（SC-006）

- [ ] ≥768px 逐頁目視：導覽、表格、grid、工具列與實作前一致
- [ ] `npm --prefix frontend run test` 全綠（含既有 109 + 本功能新增）
- [ ] `npm --prefix frontend run lint && build` 通過、無新依賴

## 對應成功標準

| 清單區塊 | 對應 SC |
|---------|--------|
| 每頁 (A) 無水平捲動 | SC-001、SC-005 |
| 導覽全部可達 | SC-002 |
| 每頁 (B) 無字字斷行 | SC-003 |
| 每頁 (C) 長字串不撐破 | SC-004 |
| 表格每列操作一螢幕寬可達 | SC-007 |
| 桌機零回歸 | SC-006 |
