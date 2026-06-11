# Quickstart 驗收：統一端點架構 + 三新端點

## US1 既有端點零回歸（P1·重構金鋼罩）
1. 把 embeddings/ocr/images/rerank/audio 遷移成 registry 內的 EndpointSpec、刪 5 個複製檔。
2. `python -m pytest tests/ -q` 全綠；**`git diff` 顯示 `test_{embeddings,ocr,images,rerank,audio}.py` 斷言一行未改**（只可能動 import）。
3. 成員呼叫任一既有端點 → 回應/計量/計費/錯誤/歸戶與重構前逐字相同。
4. 串流端點 `/chat/completions`、`/responses` 完全未動、測試全綠。

## US2 moderation（token）
1. 領 moderation 模型金鑰 → `POST /v1/moderations {model, input}`。
2. 回審核結果;記一筆 token 計費歸戶。**程式增量＝registry 加一筆 spec + upstream 加一個 wrapper**。

## US3 search（每查詢）
1. 領 search 模型金鑰 → `POST /v1/search {model, query}`。
2. 回搜尋結果;記 `unit="query"` cost=每查詢價。(admin 可在價格頁設每查詢價,同 OCR 每頁價)
3. 驗 `call` 把 provider 對映成 `search_provider`——上游參數各異由 spec 承載、引擎不特例化。

## US4 image_edit（multipart，每張圖）
1. 領 image_edit 模型金鑰 → `POST /v1/images/edits`（multipart：`model` + `image` + `prompt`）。
2. 回編輯後圖片;記 `unit="image"` quantity=產出圖數。

## 「加端點＝加資料」驗收（SC-002）
- 在 `registry.py` 加一筆假端點 spec → 引擎自動處理（不需改 `engine.py`/`endpoint_spec.py`）。

## 零回歸 / 收尾（SC-001/005/006）
- `python -m pytest tests/ -q` 全綠;`ruff check .`（含 tests）+ `mypy` 乾淨;`alembic heads`=`0019`（無新 migration）;無新套件。
- 前端 `npx tsc --noEmit && npm run build && npm test -- --run` 全綠。
- 真機煙霧:三新端點壞 token → 401（皆走 `location /v1`）;既有 8 端點壞 token → 401 不變。
