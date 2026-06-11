# Quickstart 驗收：計費一般化 + OCR 端點

> 前置：admin 已登入；有一個 OCR 模型（`mode=ocr`，如 `azure_ai/mistral-document-ai-*`）在目錄 + 對應 provider credential。

## US1 成員呼叫 OCR + 按頁計費歸戶（P1）

1. admin 為該 OCR 模型設每頁價（見 US2）。成員領一筆該模型分配 + 金鑰。
2. 成員 `POST /v1/ocr`，body `{model, document:{type:"document_url", document_url:"…pdf"}}`，帶金鑰。
3. 回 200 + 辨識文字（`OCRResponse`）。
4. 查用量：記一筆 `unit="page"`、`quantity=頁數`、`cost_usd=頁數×每頁價`、歸戶該分配。
5. 拒絕：金鑰範圍外模型 → 403；壞金鑰 → 401；缺 `document` → 400。

## US2 admin 設定/覆寫每頁價 + 可稽核（P2）

1. admin `POST /admin/prices`：`{provider, model, input_per_1k:"0", output_per_1k:"0", price_unit:"page", price_per_unit:"0.003", effective_from}`。
2. `GET /admin/prices` → 該列帶 `price_unit:"page"`、`price_per_unit:"0.003"`。
3. 成員呼叫 → cost = 頁數 × 0.003。
4. admin 改每頁價（新 `effective_from`）→ 之後呼叫用新價；**改價前已記的 CallRecord cost 不變**（point-in-time）。
5. 未定每頁價的 OCR 模型 → 呼叫仍回結果、記頁數、cost 0。

## US3 OCR 上游錯誤可診斷（P2）

1. 讓上游失敗（mock `aocr` raise / 真機打不存在的 deployment）。
2. 回 502 + 帶上游原因的錯誤;記一筆 `CallRecord(outcome=upstream_error, model, allocation)`;伺服器 log 有上下文;底層憑證不外洩。

## US4 目錄正確標 OCR + 顯示呼叫範例（P3）

1. 成員看該 OCR 模型詳情 → `kind=ocr`、顯示 `/v1/ocr` 呼叫範例（curl/python）。
2. chat / embedding 模型詳情 → 仍各自正確（kind 與範例不變）。

## 零回歸（SC-002 / SC-006）

- 既有 chat / embedding 呼叫的 token 計費結果、用量記錄**完全不變**。
- `python -m pytest tests/ -q` 全綠;`ruff` / `mypy` 乾淨;`alembic heads` = `0019`（單一 head）;無新套件。
- 前端 `npx tsc --noEmit && npm run build && npm test -- --run` 全綠。
- 真機煙霧：`/v1/ocr` 壞 token → 401（端點已註冊、走 nginx proxy）；`alembic current` = `0019`。
