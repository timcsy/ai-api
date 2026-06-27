# Contract: OpenAI 相容模型發現端點 `/v1/models`

新增端點、非破壞性（既有 `/v1/*` 不動）。認證沿用其他 `/v1` 端點：`Authorization: Bearer <application-key>`。錯誤格式沿用平台慣例 `{"error": {"code", "message"}}`。

## `GET /v1/models`

列出呼叫金鑰 scope 內、狀態 active 的分配對應模型。

### Request
- Header：`Authorization: Bearer <token>`（必要）
- 無 query/body。

### Response 200
```json
{
  "object": "list",
  "data": [
    { "id": "azure/gpt-5.4", "object": "model", "created": 1716000000, "owned_by": "azure" },
    { "id": "azure/text-embedding-3-large", "object": "model", "created": 1716000000, "owned_by": "azure" }
  ]
}
```
- `data` 依 `id` 升序；金鑰內不重複。
- 空 scope 金鑰 → `{"object":"list","data":[]}`（200，非錯誤）。
- 未定價模型仍出現（不因缺價隱藏）。
- 已 paused/revoked/quarantined 的分配對應模型**不**出現。

### Response 401（unauthorized）
缺/空/無效 Bearer：
```json
{ "error": { "code": "unauthorized", "message": "missing bearer token" } }
```
不洩漏任何模型資訊。

---

## `GET /v1/models/{id}`

取回單一模型（`{id:path}` 容許 slug 內 `/`）。

### Request
- Header：`Authorization: Bearer <token>`（必要）
- Path：`id`＝模型識別碼（正規 slug，如 `azure/gpt-5.4`；亦接受唯一可 strip 相符的 bare slug）。

### Response 200
```json
{ "id": "azure/gpt-5.4", "object": "model", "created": 1716000000, "owned_by": "azure" }
```

### Response 404（not_found）
id 不在金鑰 scope 內、或對應分配非 active：
```json
{ "error": { "code": "not_found", "message": "model azure/foo not found" } }
```
（不區分「不存在」與「無權限」，避免洩漏存在性。）

### Response 401
同上。

---

## 不變式（契約測試斷言）

1. **scope 一致（SC-001）**：list 的 `data[].id` 集合 == 該金鑰 active 分配的 `resource_model` 集合。
2. **識別碼可路由（SC-002）**：list 任一 `id` 原樣作為 `model` 送 `/v1/chat/completions`（或對應端點），preflight 不回 `model_mismatch`（identifier 對得上；provider 可用性另計）。
3. **scope 隔離**：兩把 scope 不同的金鑰得到不同 `data`；A 的金鑰列不出 B 專屬模型。
4. **401**：無/錯 Bearer → 401，body 無模型資訊。
5. **排除非 active**：分配 paused/revoked → 該模型不在 list；retrieve 該 id → 404。
6. **未定價仍列**：scope 內無價目的模型出現在 list。
7. **retrieve 對稱**：list 中存在的 id → retrieve 200 且同物件；list 中不存在的 id → retrieve 404。
8. **既有端點零回歸**：`/v1/chat/completions`、`/v1/responses` 等既有 contract 測試不改、全綠。
