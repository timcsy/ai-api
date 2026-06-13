# Quickstart: 成本制配額

## 給管理員（怎麼用）

1. 進**分配管理 → 某分配 → 配額**，在既有「每月 token 上限」旁設「**每月花費上限（USD）**」（例 `5`）。留空＝不設（維持現況）。
2. 該分配當月**所有端點**的累計花費（chat token、OCR 頁、圖片張、即時字幕分鐘…，一律換算成 USD）達到 `5` 後，後續呼叫被擋、成員收到「已達本月花費上限」。
3. 即時字幕長連線進行中若花費衝破上限，連線會在數秒內被主動中止（已用時長照常計費）。
4. 成員在自己的「用量」頁可看到每個分配「本月已花 $X / 上限 $Y」，自己掌握、不會突然被擋還不知為何。

**注意**：花費上限只治理**已定價**的用量。某模型若還沒設價（`未定價`），它的呼叫花費算 0、不計入上限——要納管請先到「價目」設好該模型的價。

## 給維護者（驗收重點）

- **混合端點累計**：對一個設了花費上限的分配，混送 chat（token）+ OCR/realtime（非 token），確認累計達上限後一律 403 `cost_quota_exceeded`（contract 測 1）。
- **零回歸**：只設 token 上限（未設花費上限）的分配，行為與上線前完全一致（contract 測 2、SC-003）。
- **realtime 連線中**：低上限 + 持續送音訊 → 連線於約定時間內被 close、已累計落帳（mock provider WS，contract 測 5）。
- **自適應池隔離**：跑一輪 rebalance，確認 `quota_cost_usd_per_month` 不被改動（contract 測 6、SC-005）。
- **部署**：有 migration → `--set migrationJob.enabled=true`；`kubectl exec <pod> -- python3 -m alembic current` 應顯 `0020`。

## 驗收對照（spec Success Criteria）

| SC | 驗證 |
|---|---|
| SC-001 混合端點達上限 100% 擋 | contract 測 1 |
| SC-002 realtime 連線中超額約定時間內中止 | contract 測 5 |
| SC-003 只設 token 上限零回歸 | contract 測 2 + 既有配額測試 git diff 為空 |
| SC-004 成員/admin 看得到本月花費/上限 | 前端顯示 + 序列化測試 |
| SC-005 自適應池不碰花費上限 | contract 測 6 |
| SC-006 累計花費 = 成功呼叫 cost_usd 總和 | unit 測 `current_month_cost` |
