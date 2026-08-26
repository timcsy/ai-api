# 2026-08-25 · OAuth 沒走 speckit 被抓（流程教訓）

## 為何（why）
OAuth 是**新表 + migration + auth + 安全**的功能，正是 speckit 領域；但我在「做完」目標下直接動手，被維護者
抓到沒走 spec。

## 怎麼（how / 為何這樣補救）
- 補救＝**回填** `specs/057-*/{spec,plan,tasks}.md`（保留已測程式碼、納入流程，那份 spec 同時當 auth review 文件）。
- **auth 功能上 production 前停下讓維護者 review**——功能建好 + 測好 + 提 PR #106，停在 review gate，核准後才合併部署。
- 同期還有一則對照：使用者說「帳號管理很亂」，我先提「重構身分模型」被打斷——他要的是**批次 + 篩選**（實用面）
  不是概念重構。使用者說「亂」要先分辨是哪種亂（概念/找不到/缺結構/流程）。

## 用了哪些概念
「feature 級 + 安全相關一律先走 speckit + review gate；小改可直接動工」；「清單管理通用解 = 篩選 × 全選 × 批次」。

## 結果
→ experience「流程：feature 級動工前先走 speckit；auth 上 production 前停下 review」；階段 43/44。
OAuth 範圍凍結見 [`history/015-OAuth-redirect白名單從env到DB單例.md`](../history/015-OAuth-redirect白名單從env到DB單例.md)。
