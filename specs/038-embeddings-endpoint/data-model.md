# Phase 1 Data Model: `/v1/embeddings`

**無 schema 變更、無新表、無 migration。** 沿用既有 `CallRecord` + token 計費；成員目錄加一個唯讀衍生欄。

## 既有實體（複用，不改 schema）

- **`CallRecord`**：embedding 呼叫記一筆——`prompt_tokens`（input）、`total_tokens`、`cost_usd`、`outcome`（`success` / `upstream_error` / 各 rejected_*）、`allocation_id`（歸戶）、`model`、`request_id`、`started_at`。**completion_tokens 留空/0**（embedding 無輸出 token）。
- **`PriceList`（point-in-time）**：embedding 的價沿用既有（`input_per_1k`）；`calculate_cost(prompt_tokens, completion_tokens=0)` 只算 input。
- **`Allocation` / 應用金鑰**：授權與計量單位仍是「分配」；金鑰 scope 決定可用哪些 embedding 模型（同 chat）。
- **`ModelCatalog`**：embedding 模型（`model_kind==embedding`）為目標；本功能只讀。

## 衍生欄（成員目錄序列化，唯讀、無 migration）

- `ModelCatalog` 序列化（`api/catalog.py` `_to_detail`，必要時 `_to_summary`）加 `kind: "chat"|"embedding"|"tts"|"image"|"stt"|"unknown"`（呼 `services/model_kind.model_kind(m)`，讀既有 `litellm_sync.raw.mode`）。供前端選對的「如何呼叫」範例。

## 請求/回應（暫態，OpenAI 相容）

```jsonc
// POST /v1/embeddings  (Authorization: Bearer <app key>)
{ "model": "azure/text-embedding-3-large", "input": "hello" }   // input: str | str[]
// 200（litellm EmbeddingResponse）
{ "object": "list", "model": "...", "data": [{ "object":"embedding", "index":0, "embedding":[...] }],
  "usage": { "prompt_tokens": N, "total_tokens": N } }
```

## 不變式

- 每次成功呼叫 MUST 記一筆 `CallRecord`（input token + 成本 + 分配歸戶）；MUST NOT 無歸屬。
- 計費 MUST 走既有 token 路徑（input_per_1k）；MUST NOT 新增非 token 單位或改 schema。
- `kind` 衍生欄 MUST 唯讀計算，MUST NOT 寫回 DB / 新增欄表。
- 授權/拒絕/上游錯誤 MUST 與 chat 共用同一條 preflight 與既有 outcome 列舉。
