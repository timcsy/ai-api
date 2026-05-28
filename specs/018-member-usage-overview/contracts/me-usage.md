# 契約: `GET /me/usage`

成員自己的用量彙總（嚴格 member-scope）。唯讀，需登入成員 session。

## 請求

```
GET /me/usage?from=<ISO8601>&to=<ISO8601>&group_by=<model|allocation>
```

| 參數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `from` | 否 | 本月 UTC 月初 | 區間起（含） |
| `to` | 否 | now(UTC) | 區間迄（不含） |
| `group_by` | 否 | 無 | 給定時回 breakdown，值 `model` 或 `allocation` |

- 認證：`current_member`（session cookie）。**無**任何可指定他人 member 的參數。
- `group_by=member` **不允許**（member-scope 下無意義）→ 422。

## 回應 200

```jsonc
{
  "from": "2026-05-01T00:00:00+00:00",
  "to":   "2026-05-28T12:00:00+00:00",
  "summary": {
    "total_tokens": 123456,
    "prompt_tokens": 80000,
    "completion_tokens": 43456,
    "total_cost_usd": 1.2345,
    "call_count": 42,
    "has_unpriced": false
  },
  "breakdown": [               // 僅當帶 group_by；否則此鍵不出現
    {
      "group_key": "azure/gpt-5.4-mini",
      "display_name": "GPT-5.4 mini (Azure deployment)",
      "total_tokens": 100000,
      "prompt_tokens": 65000,
      "completion_tokens": 35000,
      "total_cost_usd": 1.0,
      "call_count": 30
    }
  ]
}
```

- 無呼叫 → `summary` 全 0、`call_count: 0`、`has_unpriced: false`。
- `total_cost_usd` 為 point-in-time 加總（與 admin 計費同口徑）。
- `has_unpriced: true` 表示彙總含「呼叫當時無價目」的呼叫，花費為**低估**（UI 須提示）。

## 錯誤

| 狀況 | 狀態碼 | envelope |
|------|--------|----------|
| 未登入 | 401 | `{detail:{error:{code:"unauthorized", ...}}}` |
| `from >= to` | 400 | `{detail:{error:{code:"invalid_range", ...}}}` |
| 區間超過上限 | 400 | `{detail:{error:{code:"range_too_wide", ...}}}` |
| `group_by` 非法（含 `member`） | 422 | FastAPI 驗證錯誤 |

## 不變式

- **資料隔離**：回應只含登入成員自己的用量；不存在任何參數能取得他人資料。
- **只計成功呼叫**：失敗呼叫不計入 token / 花費 / 次數。
- **breakdown 守恆**：帶 `group_by` 時，各列 token / 花費 / 次數加總 = `summary` 對應值。
- **零退化**：既有 `/admin/usage` 與成員分配明細行為不變。
