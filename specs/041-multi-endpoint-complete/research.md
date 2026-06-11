# Research: 多端點全開（圖片 / rerank / TTS / STT）+ 目錄誠實

> 所有形狀皆以 `inspect` / `print` 實測 litellm，未憑印象（經驗：採用前先驗證能力邊界 + 印一次真實回傳值）。

## R1：圖片生成——token 計費，沿用 embedding 樣板

- **Decision**：`/v1/images/generations` 複製 `embeddings.py`：`run_preflight` → `upstream.aimage_generation(model, prompt, …)` → `ImageResponse`（含 `data` + `usage`）→ 以 `usage` 的 token 計費（`calculate_cost`，同 chat/embedding）→ `record_call(prompt_tokens/total_tokens, cost)` → 回 `model_dump()`（`data` 為 b64/url，JSON）。
- **Rationale**：實測本平台圖片模型（Azure gpt-image）`mode=image_generation` 但**以 token 計價**（`ImageResponse.usage` 帶 token；增量② research 已證），故沿用 token 路徑、零計費層改動。`data` 是 JSON（b64_json/url），無 binary。
- **Alternatives considered**：per-image/per-pixel 單位——非本平台所需（dall-e 才是），YAGNI。

## R2：rerank——per-query 單位，JSON

- **Decision**：`/v1/rerank` body `{model, query, documents}` → `upstream.arerank(model, query, documents, …)` → `RerankResponse(id, results, meta)` → 計費 `unit="query"`、`quantity=1`、`calculate_unit_cost(1, 每查詢價)` → `record_call(quantity=1, unit="query", cost)` → 回 `model_dump()`。新增 `upstream.arerank` wrapper（沿用 `_extra`）。
- **Rationale**：實測 rerank 模型（`azure_ai/cohere-rerank-*`）`mode=rerank`、`input_cost_per_query`（每查詢）。輸入 query+documents、輸出 results 皆 JSON，無 binary。per-query 是增量②單位維度的**第二個非 token 單位**（繼 page），證明一般化非特例。
- **Alternatives considered**：per-token rerank 計費——cohere rerank 以查詢計價（`input_cost_per_token` 為 0），per-query 才對。

## R3：TTS——binary 音檔輸出（非串流），per-character

- **Decision**：`/v1/audio/speech` body `{model, input, voice}` → `upstream.aspeech(model, input, voice, …)` → `HttpxBinaryResponseContent` → 讀 `.content`（bytes）→ FastAPI `Response(content=bytes, media_type="audio/mpeg")` 回傳；計費 `unit="character"`、`quantity=len(input)`、`calculate_unit_cost(len, 每字元價)`；**在拿到 bytes 的當下就 `record_call`**（同請求內、非串流、無 finally）。
- **Rationale**：實測 `aspeech` 回 `HttpxBinaryResponseContent`，有 `.content`（bytes）。音訊體積小、一次讀回即可，**不需串流** → 避開「串流副作用放 finally 被 CancelledError 打斷」的坑（階段 11 教訓）：非串流時計費就在 handler 主體內，client 必定還連著。計量 = 輸入字數（對齊 `input_cost_per_character`）。
- **Alternatives considered**：串流回傳（`iter_bytes`）——徒增 CancelledError 記帳風險，且音訊不大、無此需要。否決。

## R4：STT——multipart 上傳，token 計費（per-second 延後）

- **Decision**：`/v1/audio/transcriptions` 收 **`UploadFile`（multipart）** → 讀 bytes → `upstream.atranscription(model, file=(upload.filename, data), …)` → `TranscriptionResponse(text, usage)` → **以 `usage` 的 token 計費**（有 token → `calculate_cost`，同 embedding；無 → cost 0）→ `record_call` → 回 `model_dump()`（JSON）。
- **Rationale**：實測 `TranscriptionResponse` 只有 `text` + `usage`，**無 `duration` 欄** → per-second 計費取不到秒數。算秒數需音訊解析（mp3 需第三方庫，stdlib `wave` 只認 WAV）——違反「不新增套件」。故 STT 走 **token 計費**：token-計價模型（`azure/gpt-4o-transcribe`，`usage` 帶 token）完整計費；純 per-second 模型（whisper-1，無 usage token）此階段記 cost 0（沿用未定價→0 慣例）。**per-second 真計量延後**（需音訊長度來源/新依賴）。
- **Rationale（multipart）**：FastAPI `UploadFile` 接 multipart；litellm `atranscription` 的 `file` 接 `(filename, bytes)` tuple（OpenAI SDK 慣例）。
- **Alternatives considered**：(a) 加音訊庫算秒數——違反零套件、scope 太大；(b) 信任 client 自報秒數——不可靠。皆否決；per-second 標記為後續。

## R5：誠實債——`_capabilities` 不假裝 chat + admin 詳情顯 kind

- **Decision**：`litellm_registry._capabilities` 的 `return caps or ["chat"]` → 改為 `return caps`（移除兜底）。chat-able mode（chat/completion/responses）仍在前面 `append("chat")`，故聊天模型不受影響（零回歸）；無聊天類旗標的非 chat 模型 → `[]`（誠實）。admin 模型詳情序列化加 `kind`（`model_kind`，成員面 catalog 已有 `kind`，admin 面補上），前端 admin 詳情顯「類型」。**現有已落地 `capabilities=["chat"]` 的非 chat 模型**：透過既有「檢查 LiteLLM 更新」重新採納即更新（資料面，不寫 migration）。
- **Rationale**：vision 階段 29 核心約束點名要修的 `or ["chat"]`；OCR 已開、使用者實際撞到（admin 詳情 OCR 顯「能力 chat」）。能力（旗標）vs 類型（端點種類）是不同軸（原則 7 軸正交）——admin 要同時看到「能力」與「類型」。
- **影響面（追所有 sink）**：`capabilities` 用於 facet 計算（`compute_facets`）、成員目錄篩選、前端能力徽章。空 `capabilities` 須確認不爆（facet 對空＝無能力 facet、篩選不命中）→ 回歸測試把關。
- **Alternatives considered**：把 kind 塞進 capabilities——破壞軸正交（OCR 不是一種「能力」），否決。

## R6：零 migration / 零套件確認

- **Decision**：本功能**不新增表/欄/migration/套件**。`alembic heads` 維持 `0019`。新單位 `query`/`character` 為 `call_records.unit` / `price_list.price_unit` 的字串值（增量② 已建欄）。需補 **`upstream.arerank` + `upstream.atranscription`** 兩個薄封裝（litellm 既有函式，同 aembedding；`aimage_generation`/`aspeech` Phase 26 已有）。
- **驗證**：`alembic heads`=0019；`grep` 確認 `aimage_generation`/`aspeech` 已存在、`atranscription`/`arerank` 需新增（皆 litellm 內建函式，零新套件）。
