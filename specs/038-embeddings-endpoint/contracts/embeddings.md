# Contracts: `/v1/embeddings`

OpenAI 相容；沿用與 `/chat/completions` 同一條前置 pipeline（憑證/分配/狀態/配額/binding/存取政策/憑證解析）與既有 token 計費。

## 1. `POST /v1/embeddings`（成員端，掛 `/v1`）

**Header**：`Authorization: Bearer <應用金鑰>`
**Body**：
```jsonc
{ "model": "azure/text-embedding-3-large", "input": "hello" }   // input: string | string[]
```

**流程**（clone `proxy/router.py`）：
1. 解 bearer token（無效/缺 → 401，記 `CallRecord` rejected_unauthenticated）。
2. 解 body：缺 `model`(str) 或 `input` → 400 `bad_request`。
3. `run_preflight(session, settings, token, requested_model)`：
   - 拒絕 → 回對應 code（`model_mismatch` / `model_forbidden` / `allocation_*` / `quota_exceeded` / `provider_not_allowed` …）+ 記 `CallRecord`。
4. `upstream.aembedding(model=upstream_model, input, api_key, api_base, api_version)`：
   - 例外 → 502 `upstream_error`（帶上游原因）+ 記 `CallRecord(upstream_error)`。
5. 成功：`usage.prompt_tokens` → `lookup_price_for_call` + `calculate_cost(prompt_tokens, completion_tokens=0)` → `record_call(success, prompt_tokens, total_tokens, cost)` 歸戶分配 → 回 litellm EmbeddingResponse（OpenAI 相容）。

**回應**：
```jsonc
// 200
{ "object": "list", "model": "...", "data": [{ "object":"embedding","index":0,"embedding":[...] }],
  "usage": { "prompt_tokens": N, "total_tokens": N } }
// 401 / 403 / 400 / 502 → 既有 _error_payload {error:{code,message,request_id}}
```

**不變式**：底層供應商金鑰 MUST NOT 出現在回應/日誌/錯誤；每次（成功或拒絕/失敗）MUST 記一筆可辨識的 `CallRecord`。

## 2. 成員目錄序列化擴充（`GET /catalog/models/{slug}` 既有端點）

`_to_detail`（必要時 `_to_summary`）加唯讀：
- `kind`: `"chat"|"embedding"|"tts"|"image"|"stt"|"unknown"`（`model_kind`，讀既有 capabilities/litellm mode）。

其餘欄位、權限不變。

## 前端 UI 契約

- `api-usage-example.tsx`：新增「embedding」範例（`/v1/embeddings` 的 curl / python / js，body `{model, input}`）；以 prop（如 `kind` 或 `isEmbedding`）切換——embedding 模型顯 embedding 範例，否則顯 chat（+ responses 若支援，沿用既有 `supportsResponses`）。
- `catalog-detail.tsx`：依 `m.kind === "embedding"` 把對應旗標傳給 `ApiUsageExample`。

## 測試契約
- 後端 `tests/contract/test_embeddings.py`：成功+計費（記 input token + cost 歸戶分配，mock `upstream.aembedding`）、`model_forbidden`/`model_mismatch`（未授權/scope 外）、401（壞/缺 token）、`upstream_error`（mock raise，502）、`bad_request`（缺 input）。
- 前端：embedding 模型詳情顯 `/v1/embeddings` 範例、非 embedding 顯 chat。
