# Contracts: 三個新端點 + EndpointSpec 內部契約

成員端點走 Bearer 金鑰。錯誤封包 `{"error":{"code","message"}}`。皆在 nginx 既有 `location /v1`（無需改 nginx）。

---

## 1. `POST /v1/moderations`（內容審核，token）

**Request**：`{ "model": "...", "input": "要審核的文字" }`（缺 input → 400）。
**Behavior**：引擎 json→json + `TokenMeter` + `call=amoderation(model, input)`。
**Responses**：`200` 回審核結果（JSON）；`401`/`403`/`400`/`502`。

## 2. `POST /v1/search`（網路搜尋，每查詢）

**Request**：`{ "model": "...", "query": "要搜尋的問題" }`（缺 query → 400）。
**Behavior**：引擎 json→json + `UnitMeter("query", 1)` + `call` 把分配解出的 provider 對映成 `asearch` 的 `search_provider`、`query` 直傳。
**Responses**：`200` 回搜尋結果（JSON）；無每查詢價 → cost 0 仍記；`401`/`403`/`400`/`502`。

## 3. `POST /v1/images/edits`（圖片編輯，multipart，每張圖）

**Request**：`multipart/form-data`，欄位 `model` + `image`（圖片檔）+ 選填 `prompt`。缺 image → 400。
**Behavior**：引擎 multipart→json（沿用 stt 上傳）+ `UnitMeter("image", len(data))` + `call=aimage_edit(model, image=(name,bytes), prompt=...)`。
**Responses**：`200` 回編輯後圖片（JSON：b64/url）；無每張圖價 → cost 0 仍記；`401`/`403`/`400`/`502`。

---

## 4. EndpointSpec 內部契約（架構，US1）

- 引擎 `run_endpoint(spec, ...)` 對 8 筆 spec 一致執行：parse → preflight → call → 計量 → record_call → respond；錯誤統一 `record_and_respond`。
- 新增同形態端點 = 在 `registry.py` 加一筆 `EndpointSpec`（path / io / required / call / meter），**不改 engine.py / endpoint_spec.py**。
- 串流端點（`/chat/completions`、`/responses`）不在 registry，保持獨立 handler。

---

## 契約測試要點（合併前必過）

- **重構零回歸（金鋼罩）**：`test_{embeddings,ocr,images,rerank,audio}.py` **斷言一行不改**、遷移後全綠。
- moderation：mock `amoderation` 回 `{...,usage}` → 200 + token 計費歸戶；缺 input→400；壞 token→401；上游錯誤→502+記。
- search：mock `asearch` 回結果 + seed 每查詢價 → 200 + 記 `unit="query"` cost=每查詢價；缺 query→400；無價→0；上游錯誤→502。
- image_edit：mock `aimage_edit` 回 `{data:[...]}` + multipart 上傳 image + seed 每張圖價 → 200 + 記 `unit="image"` quantity=產出圖數；缺 image→400；上游錯誤→502。
- 引擎單元：`TokenMeter`/`UnitMeter` 計量正確；IOShape json/binary/multipart parse+respond 正確。
- 加端點=加資料：以一筆 spec 註冊一個假端點即可被引擎處理（不需改 engine）。
- 串流零觸碰：`/chat/completions`、`/responses` 既有測試全綠。
