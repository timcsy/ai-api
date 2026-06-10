# Quickstart 驗收：管理員成員管理批次化 + 安全刪除

> 前置：admin 已登入後台；環境有 dev DB。以下走 US1–US3 + 零回歸。

## US1 安全刪除單一成員（P1）

1. 建一位成員，領一筆 active 分配，用其金鑰打幾次 API（產生 CallRecord）。
2. 成員列表對該成員按「刪除」→ 確認視窗應顯示「將移除 N 筆分配、M 把憑證；正在使用的金鑰會立即失效；過往用量會保留」。
3. 確認 → 成員消失。
4. **驗孤兒保留**：查資料庫該成員的 CallRecord 仍在、`allocation_id IS NULL`、`subject` 仍是該成員 email。
5. 查稽核 → 有一筆 `member_deleted`。
6. 防呆：對「自己」按刪除 → 被擋（`cannot_delete_self`）；若系統只剩一位 admin，刪該 admin → 被擋（`last_admin`）。

## US2 批次刪除（P2）

1. 建 5 位成員（部分有分配）。
2. 列表勾選其中 4 位 → 出現批次動作列「已選 4 位」+「批次刪除」。
3. 按批次刪除 → 確認視窗顯示位數與連帶影響 → 確認。
4. 回摘要：deleted/failed 計數 + 逐筆 results；未選的第 5 位仍在。
5. 故意把其中一位設成「自己」或唯一 admin → 該筆 `failed` + 原因，其餘照常刪除。

## US3 批次預建 local_password（P3）

1. 開「批次新增成員」對話框，貼：
   ```
   new1@example.com
   <一個已存在的 email>
   not-an-email
   new1@example.com
   ```
2. 提交 → 回摘要：`new1` = created（附邀請連結）、已存在 = exists、`not-an-email` = invalid、第二個 `new1` = duplicate。
3. 列表出現 1 位新成員（new1）；點邀請連結可走設定密碼流程。
4. 查稽核 → 有一筆 `member_created`（new1）。

## 零回歸（SC-006）

- 既有「無分配成員」單筆刪除 → 仍 204、行為不變。
- 既有單筆「新增成員」對話框 → 不變。
- 分配、計費、用量視圖 → 不受影響。
- 後端 `python -m pytest tests/ -q` 全綠；`ruff check src/ai_api`、`mypy` 乾淨；`alembic heads` 仍為 `0018`、無新套件。
- 前端 `npx tsc --noEmit && npm run build && npm test -- --run` 全綠。
