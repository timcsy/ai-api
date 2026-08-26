# 2026-06-03 · admin 下班時段收到自動隔離 email（階段 13 招牌場景）

## 為何（why）
異常偵測器在非辦公時間隔離一筆分配——沒有通知的話，真實使用者被擋直到 admin 隔天手動介入才發現。這是
spec 022 的核心驅動場景（US2）。

## 怎麼（how / 為何這樣選）
- 採「事件 → 立即寄信」+ **DB 紀錄當去重 gate**，**不建背景排程器**（多 replica 每窗每型別至多 N 封、實務可接受）。
- 30 秒內每個 recipient 收到含分配/成員/隔離原因（具體數字）/時間/解除頁連結的信，admin 在手機上就能判斷處理。
- 過程踩到 **SMTP 587 撞 NetworkPolicy egress**：本機/CI 全綠（loopback）、部署到 live cluster 按「發測試信」
  才回 `test_failed_connect`——階段 2.5 egress 只放 443/5432/53。解法：chart egress 加 587/465。

## 用了哪些概念
`Notifier` interface + `EmailNotifier`（LINE/Web Push 可後續平行加）；「新增對外連線要同步檢查 egress、本機
測不出」；「採用 SDK 前先 `print(type, repr(result))`」（`aiosmtplib.send` 回 `(errors_dict, msg)` 非印象中的
`(code, ...)`、靠 `errors == {}` 判成功）。

## 結果
→ experience「新增對外連線/新上游行為要真機才暴露」；[`history/lessons-archive.md`](../history/lessons-archive.md)
（fire-and-forget drain、Fernet 指紋取明文 hash）。
