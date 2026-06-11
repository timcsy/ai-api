# Contracts: 四端點 + 目錄誠實

成員端點走 Bearer 金鑰（同 `/v1/chat/completions`）。錯誤封包 `{"error":{"code","message"}}`。掛在 nginx 既有 `location /v1`（無需改 nginx）。

---

## 1. `POST /v1/images/generations`（圖片，token）

**Request**：`{ "model": "...", "prompt": "a red dot" }`（缺 prompt → 400）。
**Behavior**：preflight → `upstream.aimage_generation` → `ImageResponse` → token 計費（`usage`）→ 記用量。
**Responses**：`200` 回 `ImageResponse`（`data`：b64_json/url，JSON）；`401`/`403`/`400`/`502`（upstream_error）同 embeddings。

## 2. `POST /v1/rerank`（rerank，per-query）

**Request**：`{ "model": "...", "query": "...", "documents": ["...", "..."] }`（缺 query 或 documents → 400）。
**Behavior**：preflight → `upstream.arerank` → `RerankResponse` → `unit="query"`、`quantity=1` 計費 → 記用量。
**Responses**：`200` 回 `RerankResponse`（`results` 排序）；無每查詢價 → cost 0 仍記；`401`/`403`/`400`/`502`。

## 3. `POST /v1/audio/speech`（TTS，per-character，**binary 輸出**）

**Request**：`{ "model": "...", "input": "要唸的文字", "voice": "alloy" }`（缺 input → 400）。
**Behavior**：preflight → `upstream.aspeech` → `HttpxBinaryResponseContent.content`（bytes）→ `unit="character"`、`quantity=len(input)` 計費（在 bytes 取得當下記）→ 回音檔。
**Responses**：
- `200`：**body = 音檔 bytes**，`Content-Type: audio/mpeg`（非 JSON）。
- `401`/`403`/`400`/`502`：JSON 錯誤封包（錯誤路徑仍 JSON）。

## 4. `POST /v1/audio/transcriptions`（STT，token，**multipart 上傳**）

**Request**：`multipart/form-data`，欄位 `model`（字串）+ `file`（音檔）。缺 file → 400。
**Behavior**：preflight（model 取自 form）→ 讀 `UploadFile` bytes → `upstream.atranscription(file=(name, bytes))` → `TranscriptionResponse(text, usage)` → token 計費（`usage` 有則計、無則 cost 0）→ 記用量。
**Responses**：`200` 回 `{text, ...}`（JSON）；`401`/`403`/`400`/`502`。

> 註：STT model 來自 multipart form 欄位（非 JSON body）；preflight 接受該 model 字串。

---

## 5. admin 模型詳情（既有端點，加衍生欄）

`GET /admin/catalog/models/{slug}`（或既有 admin 詳情端點）回應**加 `kind`**（`model_kind`：…/`rerank`/…）。`capabilities` 對非 chat 且無聊天旗標的模型回 `[]`（不再 `["chat"]`）。chat 模型 `capabilities`/`kind` 不變。

---

## 契約測試要點（合併前必過）

- images：mock `aimage_generation` 回帶 usage → 200 + 記 token 計費歸戶；拒絕/上游錯誤。
- rerank：mock `arerank` 回 results → 200 + 記 `unit="query"` quantity=1 cost=每查詢價；無價→0；缺 query/documents→400；上游錯誤→502+記。
- TTS：mock `aspeech` 回 bytes 物件 → 200 + `Content-Type: audio/mpeg` + body=bytes + 記 `unit="character"` quantity=len 計費；缺 input→400；上游錯誤→502（JSON）。
- STT：mock `atranscription` 回 `{text,usage}` + multipart 上傳 file → 200 + 記 token 計費；缺 file→400；上游錯誤→502。
- 誠實債：`_capabilities` 對 ocr/embedding entry（無旗標）→ `[]`；對 chat entry → 含 `"chat"`（零回歸）。
- kind：rerank 模型 `kind=="rerank"`；admin 詳情含 `kind`。
- 授權：四端點壞/缺 token → 401。
- 零回歸：既有 chat/embedding/ocr 計費契約全綠。
