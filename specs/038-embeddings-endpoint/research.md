# Phase 0 Research: 對成員開放 `/v1/embeddings`

## D1 — 路由：複製 chat router、改 endpoint 變數

**Decision**：新 `proxy/embeddings.py` 的 `POST /v1/embeddings` 結構與 `proxy/router.py` 的 `/chat/completions` **一致**，只差三處：
1. body 驗 `{model, input}`（input 為 str 或 list[str]）而非 `messages`。
2. 上游呼 `upstream.aembedding(model=upstream_model, input=input, api_key=..., api_base=..., api_version=...)`。
3. usage 只有 `prompt_tokens`/`total_tokens`（無 completion）→ `calculate_cost(prompt_tokens=…, completion_tokens=0)`。
其餘（`record_and_respond` 拒絕記帳、`run_preflight`、point-in-time `lookup_price_for_call`、`record_call`、`_error_payload`/`_outcome_for_code`）**原樣沿用**。掛載 `main.py`：`include_router(embeddings_router, prefix="/v1")`。

**Rationale**：`run_preflight(session, settings, token, requested_model)` 端點無關（回 provider/upstream_model/canonical_model/allocation/resolved），chat 與 responses 已共用——embedding 第三家複用，零授權重寫（原則 7）。

**Alternatives considered**：把 embeddings 塞進既有 `router.py`：耦合 chat/embedding body 解析；分檔較清楚（與 responses.py 同模式）。否決。

## D2 — embedding 回應 usage shape（已實測，FR-003）

**Decision**：用 `payload = result if dict else result.model_dump()` → `usage_obj = payload.get("usage") or {}` → `prompt_tokens = usage_obj.get("prompt_tokens")`。

**Rationale（已驗證，呼應「採用前先印一次回傳值」）**：實跑
`litellm.EmbeddingResponse().model_dump()` → keys `{data, model, object, usage}`，`usage = {prompt_tokens, total_tokens, completion_tokens:0, …}`。與 chat 的 `payload.get("usage")` 完全同形 → 同一段計費程式可用。缺 usage（少數 provider）→ `prompt_tokens=None` → `calculate_cost` 回 None（成本未定價，沿用 `has_unpriced` 既有渲染）。

## D3 — 計費：複用 token、不做一般化（FR-004）

**Decision**：`lookup_price_for_call(session, provider, model=slug去前綴, call_time=started_at)` + `calculate_cost(price, prompt_tokens, completion_tokens=0)`。embedding 的價在既有 `PriceList`（input_per_1k）即可；無 output → completion=0。`record_call(..., prompt_tokens, total_tokens, cost_usd)`。

**Rationale**：embedding 計費單位＝input token，與 chat 同；`calculate_cost` 對 completion=0/None 已正確（只算 input）。**不需階段 29 的計費一般化**——那留給非 token 端點（OCR/圖片/語音）。`PriceList`/`CallRecord` 零改、零 migration。

## D4 — 成員目錄加衍生 `kind`，前端範例切換（FR-007）

**Decision**：`api/catalog.py` 的成員序列化（`_to_detail`，必要時 `_to_summary`）加唯讀欄 `kind = model_kind(m)`（`services/model_kind.py`，讀既有 `litellm_sync.raw.mode`）。前端 `api-usage-example.tsx` 加 embedding 範例（`/v1/embeddings` 的 curl/python/js），`catalog-detail.tsx` 依 `m.kind === "embedding"` 切換顯示。

**Rationale**：要顯對的呼叫範例就得知道模型端點種類；`model_kind` 已是這個真相來源（Phase 26）。暴露 `kind`（而非只 `is_embedding`）對未來 image/audio 範例也可重用（原則 7）。零 migration。
**Alternatives considered**：前端從 capabilities/modality 推——embedding 與 chat 在 modality 撞型（同 model_kind 的陷阱），推不準。否決。

## D5 — 拒絕/錯誤 outcome 對映（FR-005/006）

**Decision**：沿用 `_outcome_for_code`（已含 `model_mismatch`/`model_forbidden`/`upstream_error`/quota/paused/quarantined…）。embedding 不需新 outcome——拒絕與失敗類別與 chat 相同。body 缺欄回 `bad_request`。

**Rationale**：embedding 的授權/失敗類別是 chat 的子集；沿用既有列舉，零新增。

## D6 — 零回歸（FR-008）

**Decision**：不改 chat/responses router、不改 preflight、不改計費結構/PriceList、不改既有目錄端點行為（只**加**一個衍生欄、值為計算）；新增一條路由 + 一個前端範例分支。
**Rationale**：SC-005 零回歸；新增面最小。
