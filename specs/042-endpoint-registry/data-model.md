# Data Model: 統一端點架構（內部結構，無 DB 變更）

> **無 DB 變更**：不新增表/欄/migration（`alembic heads` 維持 `0019`）。本檔描述**程式內的結構**（EndpointSpec / Meter / IOShape）與 8 筆註冊資料。

## EndpointSpec（端點描述，每端點一筆）

```
EndpointSpec:
  path: str               # "/embeddings" "/moderation" "/audio/speech" …
  io: IOShape             # (input, output) 形態組合
  required: list[str]     # 必填欄位（解析後驗證；缺→400 bad_request）
  call: Callable          # (fields, resolved, upstream_model) -> awaitable[result]
  meter: Meter            # TokenMeter | UnitMeter(unit, quantity_fn)
  model_field: str = "model"   # 請求中 model 的位置（multipart 在 form）
```

## IOShape（I/O 形態，少數可重用）

| input | output | 用於 | parse | respond |
|-------|--------|------|-------|---------|
| json | json | embedding/ocr/image/rerank/moderation/search | `await request.json()`，model 取 body | `JSONResponse(payload)` |
| json | binary | tts | 同上 | `Response(bytes, audio/mpeg)` |
| multipart | json | stt/image_edit | `Form(model)` + `File(file/image)` | `JSONResponse(payload)` |

- `parse(request) -> (model, fields)`：fields 是給 `call` 與 `meter` 用的解析結果（含上傳 bytes）。
- `respond(result)`：json 回 payload dict；binary 取 `result.content`（或 bytes）回 `Response`。

## Meter（計量策略，與 IOShape 正交）

- **TokenMeter**：`measure(fields, payload)` 讀 `payload["usage"]` → `{prompt_tokens, completion_tokens, total_tokens}`；cost = `calculate_cost(price, …)`。用於 embedding/image/stt/moderation。
- **UnitMeter(unit, quantity_fn)**：`quantity = quantity_fn(fields, payload)`；cost = `calculate_unit_cost(quantity, price.price_per_unit if price.price_unit==unit else None)`。
  - ocr：`unit="page"`, `len(payload["pages"])`
  - rerank：`unit="query"`, `1`
  - tts：`unit="character"`, `len(fields["input"])`
  - search：`unit="query"`, `1`
  - image_edit：`unit="image"`, `len(payload["data"])`

## 8 筆註冊（registry）

| path | io(in→out) | meter | call → upstream | 來源 |
|------|-----------|-------|-----------------|------|
| `/embeddings` | json→json | Token | `aembedding(model, input)` | 遷移 |
| `/ocr` | json→json | Unit(page) | `aocr(model, document)` | 遷移 |
| `/images/generations` | json→json | Token | `aimage_generation(model, prompt)` | 遷移 |
| `/rerank` | json→json | Unit(query) | `arerank(model, query, documents)` | 遷移 |
| `/audio/speech` | json→binary | Unit(character) | `aspeech(model, input, voice)` | 遷移 |
| `/audio/transcriptions` | multipart→json | Token | `atranscription(model, file)` | 遷移 |
| `/moderation` | json→json | Token | `amoderation(model, input)` | **新** |
| `/rerank`→`/search` | json→json | Unit(query) | `asearch(search_provider, query)` | **新** |
| `/images/edits` | multipart→json | Unit(image) | `aimage_edit(model, image, prompt)` | **新** |

> `/chat/completions`、`/responses`：**不在 registry**（串流端點，`router.py`/`responses.py` 保持獨立）。

## 不變式（來自 FR）

- 引擎流程：parse → preflight → call → 計量 → record_call → respond；錯誤路徑統一記一筆（FR-001）。
- 端點差異只在 spec（FR-002）；計量可插拔（FR-003）；I/O 形態可重用、加同形態端點不需新 handler（FR-004）。
- 既有 5 端點外部行為零回歸、既有測試不改斷言全綠（FR-005、SC-001）。
- 三新端點走相同 preflight/未定價→0/上游錯誤去敏（FR-010）；無 DB 變更（FR-011）；未涵蓋 mode 顯示「未知」（FR-012）。
