# Quickstart: 階段 10 使用體驗打磨收尾

## 後端驗證

```bash
# /me/allocations 回 display_name（成員 session）
curl -s http://localhost:47821/me/allocations -H "Cookie: <member session>" | python3 -m json.tool
# 預期：每筆含 "display_name"（orphan 為 null）、既有 "price" 不變
```

## 測試

```bash
uv run pytest tests/contract/test_me_allocations.py -v
cd frontend && npm test -- --run \
  src/__tests__/dashboard.test.tsx \
  src/__tests__/dashboard-quota.test.tsx \
  src/__tests__/admin-allocations-pause.test.tsx
# 全套
uv run pytest -q && cd frontend && npx tsc --noEmit && npm test -- --run
uv run ruff check .
```

## UI 驗證（真實成員 / admin）

1. 成員登入 → 儀表板「我的分配」卡片：顯示**模型名稱**（slug 為輔）+ **現價（每 1M）**；缺價目標「未定價」
2. 可自助領取卡片：點卡片導到 `/catalog/{slug}`；點「領取」鈕不導頁、正常領取
3. 以無分配成員登入 → 看到「① 領取 ② 複製 ③ 貼進 Authorization」三步引導
4. 比對儀表板「API 端點」與模型詳情「如何呼叫」的網址 → 一致
5. token 提示文案 → 涵蓋自助領取情境
6. admin → 分配 → 調整配額 → 站內 Dialog（預填、擋非法輸入、空白=無限額）

## 驗收對應
- US1 → /me/allocations display_name + 卡片名稱/現價 RTL
- US2 → claimable 卡片導頁 RTL
- US3 → 空狀態引導 RTL
- US4 → 端點單一 helper 一致
- US5 → admin 配額 Dialog RTL
- US6 → token 文案
