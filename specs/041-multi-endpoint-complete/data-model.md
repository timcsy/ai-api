# Data Model: 多端點全開 + 目錄誠實

> **無 schema 變更**：不新增表/欄/migration（`alembic heads` 維持 `0019`）。四端點沿用增量②（0019）的 `call_records.{quantity,unit}` 與 `price_list.{price_unit,price_per_unit_usd}`；新單位為字串值。

## 四端點的計量 / 計費

| 端點 | litellm mode | 計量單位 | 數量來源 | 計費函式 |
|------|--------------|----------|----------|----------|
| `/v1/images/generations` | image_generation | **token** | `ImageResponse.usage`（prompt/total tokens） | `calculate_cost`（token 路徑） |
| `/v1/rerank` | rerank | **query** | 固定 1（一次查詢） | `calculate_unit_cost(1, 每查詢價)` |
| `/v1/audio/speech`（TTS） | audio_speech | **character** | `len(input 文字)` | `calculate_unit_cost(len, 每字元價)` |
| `/v1/audio/transcriptions`（STT） | audio_transcription | **token** | `TranscriptionResponse.usage`（有則計，無則 cost 0） | `calculate_cost`（token 路徑） |

- 所有成功呼叫 `record_call(... quantity, unit, cost_usd, outcome=success, 歸戶 allocation)`。token 端點（image/STT）`unit=None`、走既有 token 欄；非 token 端點（rerank/TTS）`unit="query"/"character"` + `quantity`。
- 未定該單位價 → cost 0、仍記數量（FR-003）。
- 上游失敗 → `record_and_respond("upstream_error", …, 502)` + 記一筆（FR-004）。

## binary I/O（新形態）

- **TTS 輸出**：`HttpxBinaryResponseContent.content`（bytes）→ FastAPI `Response(content=bytes, media_type="audio/mpeg")`。**非串流**——計費在 bytes 取得當下於 handler 主體記（不放 finally；階段 11 串流教訓）。
- **STT 輸入**：FastAPI `UploadFile`（multipart）→ 讀 bytes → litellm `file=(filename, bytes)`。輸出 JSON。

## 計量單位（Unit）字串維度

- 既有值：`token`（NULL 表示）、`page`（OCR）。
- 本功能新增值：`query`（rerank）、`character`（TTS）。
- **加單位＝加字串值，不改 schema**（原則 7：易變的東西做成資料）。

## 目錄誠實（capabilities / kind）

### `_capabilities`（litellm_registry）

| mode | 修正前 capabilities | 修正後 capabilities |
|------|---------------------|---------------------|
| chat / completion / responses | `["chat", …]` | `["chat", …]`（不變，零回歸） |
| ocr / embedding / image / audio / rerank（無聊天類旗標） | **`["chat"]`（兜底假裝）** | `[]`（誠實） |

- 修法：`return caps or ["chat"]` → `return caps`。
- **現有資料**：已落地 `["chat"]` 的非 chat 模型需「檢查 LiteLLM 更新」重新採納才更新（資料面，不寫 migration）。

### kind（類型）— admin 詳情新增呈現

- 成員目錄序列化已有 `kind`（增量①/②）；admin 模型詳情序列化**補上 `kind`**（`model_kind`：chat/embedding/image/tts/stt/ocr/**rerank**/unknown）。
- `model_kind.Kind` 加 `"rerank"`；`mode=="rerank"` → `rerank`。
- 前端 admin 詳情顯「類型」欄（與「能力」分開＝軸正交）。

## 驗證規則（來自 FR）

- 四端點走同一條 preflight（FR-001）；計量歸戶（FR-002）；未定價→0（FR-003）；上游錯誤可診斷 + 憑證去敏（FR-004）。
- TTS 計費在 bytes 產出當下記、不漏（FR-012）。
- `_capabilities` 不假裝 chat、chat 零回歸（FR-015）；admin 詳情顯類型（FR-016）；重新同步更新既有（FR-017）。
- 零回歸：token 端點/計費/facet/篩選不變（FR-005、SC-005）；單一 head 0019（SC-006）。
