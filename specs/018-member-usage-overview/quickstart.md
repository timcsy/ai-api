# Quickstart: 成員自助用量總覽

## 後端驗證

```bash
# 以成員 session 取自己的用量摘要（本月）
curl -s http://localhost:47821/me/usage \
  -H "Cookie: <member session cookie>" | python3 -m json.tool
# 預期：{ from, to, summary:{total_tokens, total_cost_usd, call_count, has_unpriced} }

# 帶 group_by 取 model 拆分
curl -s "http://localhost:47821/me/usage?group_by=model" \
  -H "Cookie: <member session cookie>" | python3 -m json.tool
# 預期：多一個 breakdown[]，各列加總 = summary

# 指定區間
curl -s "http://localhost:47821/me/usage?from=2026-05-01T00:00:00%2B00:00&to=2026-05-28T00:00:00%2B00:00" \
  -H "Cookie: <member session cookie>"
```

## 測試

```bash
uv run pytest tests/integration/test_usage_member_scope.py \
              tests/integration/test_me_usage.py -v
cd frontend && npm test -- --run src/__tests__/dashboard-usage.test.tsx
# 全套
uv run pytest -q && cd frontend && npx tsc --noEmit && npm test -- --run
uv run ruff check .
```

## UI 驗證（真實成員）

1. 無痕視窗 → `http://localhost:47822` → 以 `b10907777@school.edu` / `VerySafePass123` 登入
2. 先用憑證打幾次 `/v1/chat/completions` 產生用量（見前次實測）
3. 回儀表板 → 頂部出現**用量摘要**：本月總 token / 估算花費 / 呼叫次數
4. （P2）切時間區間、看 model 拆分；（P3）看各分配「本月已用 / 配額」
5. 若有未定價呼叫 → 摘要顯示「含未定價項目，花費為低估」

## 驗收對應
- US1（摘要）→ 後端 summary + 儀表板摘要 RTL
- US2（拆分/區間）→ `group_by` breakdown + 區間測試
- US3（配額）→ 分配「已用/配額」顯示
- 資料隔離 → `test_usage_member_scope` 的 A/B 隔離測試
