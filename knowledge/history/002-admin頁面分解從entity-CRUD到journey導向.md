# 002：admin 頁面分解從 entity-CRUD 到 journey 導向
> 日期：2026-05-25

## 轉移
- 舊（superseded）：階段 5 一路把 admin 功能逐一加成 **11 個 entity-CRUD 入口**（按「系統有哪些表」切頁）。
- 新（spec 013 / 階段 5.1）：以「使用者旅程」重收斂成 **6 個入口**；舊 11 個 URL 以 React Router redirect
  保留（deep-link 不壞）。

## 為什麼變
落地當天作者即發現「完成一個常見任務要跑 4-6 頁、新 admin 不知從哪開始」。spec 問題陳述明講根因是
「建構時以資料模型為主軸做頁面分解、未先設計 user journey」。頁面該按「人要完成什麼」分解，不是按「系統有
哪些表」。修法只重組 UI + 加 1 個診斷端點（`GET /admin/diagnose/visibility`），**不動任何後端 schema/endpoint**。

## 狀態
✅ 已採用。目標達成（alice 用某 model 從 4-6 頁 → 2 頁）。同精神在階段 24（模型編輯收斂成單一中樞）重現。
