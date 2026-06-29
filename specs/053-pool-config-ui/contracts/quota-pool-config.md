# Contract: 配額池設定（admin）

既有 admin-only 路由群擴充；錯誤格式沿用 `{"error":{"code","message"}}`。

## GET /admin/quota-pool/status（擴充）
回現有欄位（T/floor/reserved/distributable/members…）**改為來自 DB 單一真理**，並新增：
```json
{
  "config": { "total_tokens_per_month": 40000000, "floor_per_allocation": 200000,
              "updated_at": "...", "updated_by": "admin@x" },
  "pool_members": 53,
  "suggestion": { "recent_month_tokens": 20751332, "suggested_total": 41502664,
                  "suggested_floor": 200000 },
  "warning": null
}
```
- `warning`：當目前 T < 近月用量時帶說明字串，否則 null。

## PUT /admin/quota-pool/config（新增）
```json
// request
{ "total_tokens_per_month": 40000000, "floor_per_allocation": 200000 }
```
- 200：更新成功、回新 config；寫稽核 `pool_config_updated`。
- 422 `invalid_pool_config`：`T < floor × N`、負數、非整數 → 擋下、訊息說明。
- `T < 近月用量`：**不擋**，於 GET 的 `warning` 反映（或回應帶 `warning`）。

## 不變式（契約測試）
1. GET 的 config 值 == apply_rebalance 實際採用值（單一真理）。
2. DB 未設過 → GET/rebalance 沿用 env 值（lazy-seed）；之後 PUT 的值蓋過。
3. PUT `T < floor×N` → 422，未改 DB。
4. PUT 成功 → 稽核留一筆。
5. 既有 `POST /quota-pool/rebalance`、`GET rebalance-log` 行為不變。
