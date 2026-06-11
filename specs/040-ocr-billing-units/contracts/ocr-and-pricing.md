# Contracts: OCR 端點 + 價格端點每頁價擴充

錯誤封包沿用 `{"error": {"code", "message"}}`。

---

## 1. `POST /v1/ocr` —（新增）成員呼叫 OCR 模型

成員端點，走 Bearer 金鑰（同 `/v1/chat/completions`、`/v1/embeddings`）。

**Request**：
```json
{
  "model": "azure_ai/mistral-document-ai-2505",
  "document": { "type": "document_url", "document_url": "https://…/file.pdf" }
}
```
- `model`：catalog slug（金鑰範圍須含此模型）。
- `document`：litellm `aocr` 的 document dict（URL 或 base64；**非 multipart**）。缺 → 400 `bad_request`。

**Behavior**：`run_preflight` → `upstream.aocr` → `pages = len(OCRResponse.pages)`（或 `usage_info`）→ 查每頁價 → `cost = pages × 每頁價` → 記一筆 `CallRecord(unit="page", quantity=pages, cost_usd, outcome=success, 歸戶分配)`。

**Responses**：
- `200`：回 `OCRResponse`（`model_dump`：`pages` / `usage_info` / `model` …）。
- `401 unauthorized`：壞/缺金鑰。
- `403 model_mismatch` / `model_forbidden`：金鑰範圍外 / 未授權模型。
- `400 bad_request`：缺 `document`。
- `502 upstream_error`：上游失敗——帶上游原因、記一筆 `CallRecord(outcome=upstream_error, model, allocation)`；底層憑證不入訊息。

**計費**：`pages × 每頁價`；無每頁價 → cost 0、仍記 pages（FR-003）。非 token 配額此階段不擋（已知限制）。

---

## 2. `POST /admin/prices` —（擴充）支援每頁價

既有端點加**選填**每單位價欄位；token 價建立路徑不變。

**Request（token，不變）**：
```json
{ "provider": "azure", "model": "gpt-4o", "input_per_1k": "0.005",
  "output_per_1k": "0.015", "effective_from": "2026-06-11T00:00:00Z" }
```

**Request（非 token，新增）**：
```json
{ "provider": "azure_ai", "model": "mistral-document-ai-2505",
  "input_per_1k": "0", "output_per_1k": "0",
  "price_unit": "page", "price_per_unit": "0.003",
  "effective_from": "2026-06-11T00:00:00Z" }
```
- `price_unit` + `price_per_unit`：選填；給定 `price_unit` 時 `price_per_unit` 必填（否則 400）。token 欄對非 token 模型填 `0`。

**Responses**：
- `201`：建立成功，回該價列（序列化含 `price_unit` / `price_per_unit`，token 列為 null）。
- `400 bad_request`：`price_unit` 給了但 `price_per_unit` 缺。

**GET `/admin/prices` / `/admin/prices/history`**：序列化加 `price_unit` / `price_per_unit`（token 列為 null）。

---

## 3. 目錄（既有端點，衍生欄）

`GET /catalog/models/{slug}` 對 OCR 模型回 `kind="ocr"`（既有 `kind` 衍生欄，Phase 38；新增 `model_kind` 對 `mode=="ocr"` 的判定）。chat/embedding 不受影響。

---

## 契約測試要點（合併前必過）

- `/v1/ocr`：(a) 有效金鑰 + mock `aocr` 回 N 頁 → 200 + 記一筆 `CallRecord(unit="page", quantity=N, cost=N×每頁價, success, 歸戶)`；(b) 無每頁價 → cost 0、仍記 N 頁；(c) 金鑰範圍外 → 403；(d) 缺 token → 401；(e) 缺 document → 400；(f) mock `aocr` raise → 502 `upstream_error` + 記一筆。
- 價格端點：建立每頁價 → GET 回帶 `price_unit/price_per_unit`；`price_unit` 無 `price_per_unit` → 400；改每頁價後 point-in-time（新呼叫新價、舊紀錄不變）。
- 目錄：OCR 模型 `kind=="ocr"`；chat/embedding `kind` 不變。
- 零回歸：既有 token 計費契約測試全綠（chat/embedding cost 不變）。
