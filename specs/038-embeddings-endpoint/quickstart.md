# Quickstart: `/v1/embeddings`（手動驗收）

前置：起後端 + 前端；目錄有一個 embedding 模型（litellm mode=embedding，如 `azure/text-embedding-3-large`）且其 provider 有可用憑證；成員有該模型的分配 + 應用金鑰。

## US1 — 成員呼叫 embedding + 計量歸戶（P1 🎯）
1. 用金鑰 `POST /v1/embeddings`：
   ```
   curl https://<base>/v1/embeddings -H "Authorization: Bearer <key>" \
     -H "Content-Type: application/json" -d '{"model":"azure/text-embedding-3-large","input":"hello"}'
   ```
   - ✅ 回 OpenAI 相容向量（`data[0].embedding`）。
2. 查用量 / `CallRecord`。
   - ✅ 一筆 `success`：input token + 成本（input_per_1k × prompt_tokens）+ 歸戶到該分配。
3. 用 scope **不含**該模型的金鑰呼叫。
   - ✅ `model_mismatch` / `model_forbidden`，擋下、不外洩供應商金鑰。
4. 用壞/撤回金鑰呼叫。
   - ✅ 401。

## US2 — 上游錯誤可診斷（P2）
1. 讓上游回錯（如 deployment 名錯）打 embedding。
   - ✅ 回 502 帶上游原因（非無資訊）；`CallRecord` 記 `upstream_error` + 上下文。

## US3 — 詳情顯示如何呼叫（P2）
1. 看一個 embedding 模型的目錄詳情。
   - ✅ 「如何呼叫」顯示 `/v1/embeddings` 範例（curl/python/js，body `{model, input}`），不是只給 chat。
2. 看一個 chat 模型詳情。
   - ✅ 仍顯 chat（+ responses 若支援）範例，未被 embedding 範例取代。

## 零回歸 / 後端（SC-005）
1. 既有 `/chat/completions`、`/v1/responses` 行為、計費、配額、稽核不變。
2. 計費正確：input_per_1k × prompt_tokens；缺 usage → 成本未定價（不炸）。
3. `alembic heads` 不變、無新 migration；`pip` / `npm` 依賴無新增。
