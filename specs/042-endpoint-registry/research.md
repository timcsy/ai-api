# Research: 統一端點架構 + moderation/search/image_edit

## R1：registry 範圍——只收非串流端點，chat/responses 刻意排除

- **Decision**：統一引擎/registry 只涵蓋**非串流請求/回應**端點：embeddings、ocr、images、rerank、audio（tts/stt），加新的 moderation、search、image_edit。**chat（`router.py`）與 responses（`responses.py`）不納入、零觸碰。**
- **Rationale**：chat/responses 都**串流**（`StreamingResponse`/`event_gen`），且計費發生在**串流中**（階段 11 教訓：在 `response.completed` 事件當下用 fresh session 記，不能事後）。引擎的形態是「呼叫上游 → 拿到完整結果 → 計量 → 記帳 → 回應」——串流端點的「結果」是一個逐步產生的事件流、計費時機在中途，**根本不符這個形態**。強塞會破壞 hard-won 的串流計費正確性（CancelledError/fresh-session）。保持獨立＝零回歸、且不違反 YAGNI（不為串流預留引擎抽象）。複製債真正所在是那 5 個非串流檔（~741 行、~80% 相同），收斂它們才是重點。
- **Alternatives considered**：把串流做成第四種 io_shape（`stream_out`）——理論可行，但計費時機（中途 vs 事後）破壞引擎的單一流程假設，且 Codex 特化邏輯多，風險遠大於收益。否決（標記為未來若真有需要再評估）。

## R2：三軸正交抽象——IOShape × Meter × call

- **Decision**：`EndpointSpec` 用三個獨立軸描述一個端點的差異：
  - **IOShape（輸入×輸出）**：`input` ∈ {`json`, `multipart`}；`output` ∈ {`json`, `binary`}。負責 (a) 從 request 解析出 `(model, fields)`、(b) 把上游結果包成 HTTP 回應。少數組合：json→json（embedding/ocr/image/rerank/moderation/search）、json→binary（tts）、multipart→json（stt/image_edit）。
  - **Meter**：`TokenMeter`（讀 `payload.usage` → prompt/completion/total，`calculate_cost`）或 `UnitMeter(unit, quantity_fn)`（`quantity_fn(fields, payload)→int`，`calculate_unit_cost`）。與 IOShape 正交。
  - **call**：一個小函式 `(fields, resolved, upstream_model) -> awaitable`，把解析出的欄位對映成該 litellm wrapper 的參數。**search 用 `search_provider+query`、image_edit 用 `image+prompt`、其餘 model+X**——各異的對映正是放在這裡（不假設統一）。
- **Rationale**：原則 7「守住軸正交」——把「怎麼收發」「怎麼計量」「怎麼呼叫上游」三件會各自獨立變動的事拆開，新端點只填這三格。`call` 用函式而非純宣告，保留參數對映彈性（search 證明不能假設都是 model+input）。
- **Alternatives considered**：(a) 純宣告式 arg-map（`{"query": "$.query"}`）——對 search/image_edit 的特殊對映表達力不足、徒增 DSL 複雜度；(b) 繼承一個 base handler class——比資料 + 小函式更重、更難一眼看出差異。皆否決。

## R3：共用引擎流程（不變的部分寫一次）

- **Decision**：`run_endpoint(spec, ...)`：
  1. `parse_bearer_token`（失敗→401 JSON）
  2. `spec.io.input.parse(request)` → `(model, fields)`（失敗/缺必填→400）
  3. `run_preflight(model)`（拒絕→記一筆 + 對應錯誤）
  4. `spec.call(fields, resolved, upstream_model)`（except→`upstream_error` 502 + 記）
  5. `payload = result if dict else result.model_dump()`（binary 例外：取 `.content`）
  6. `spec.meter.measure(fields, payload)` → 計量（token 或 quantity/unit）+ `cost`
  7. `record_call(...)`（成功）
  8. `spec.io.output.respond(payload | bytes)`
  錯誤路徑統一 `record_and_respond`（沿用既有 `_outcome_for_code`/`_error_payload`/`redact_string`）。
- **Rationale**：這正是 5 個既有檔逐字重複的骨架；抽成一條，端點只剩 spec。**TTS 的「bytes 當下記帳」自然落在步驟 6/7（非串流、在引擎主體內）**，維持階段 11 正確性。
- **Alternatives considered**：保留每端點 handler、只抽 helper——半套，重複仍在。否決。

## R4：三個新端點的上游形狀（實測）

- **moderation**：`litellm.amoderation(input, model, …)`；mode=moderation、cost=per-token。IOShape json→json、`TokenMeter`、`call=amoderation(model, input)`。
- **search**：`litellm.asearch(query, search_provider, …)`；mode=search、cost=`input_cost_per_query`。**簽章用 `search_provider` 非 `model`** → `call` 把分配解出的 provider/slug 對映成 `search_provider`（research 已驗）。IOShape json→json、`UnitMeter("query", lambda *_:1)`。
- **image_edit**：`litellm.aimage_edit(image, prompt?, …)`；mode=image_edit、cost=`output_cost_per_image`。IOShape multipart→json（沿用 stt 的上傳處理）、`UnitMeter("image", quantity_fn=產出圖數 `len(payload["data"])`）、`call=aimage_edit(model, image=(name,bytes), prompt=...)`。需補 `upstream.{amoderation,asearch,aimage_edit}` wrapper。
- **Rationale**：呼應「採用前印真實回傳」——三個函式存在、計費單位、特殊參數皆已 inspect 確認。

## R5：零回歸策略——既有測試當金鋼罩，不改斷言

- **Decision**：遷移 5 個端點時，**既有 contract/integration 測試一行斷言都不改**（`test_embeddings/ocr/images/rerank/audio.py`）。遷移完它們全綠＝外部行為逐字不變（FR-005、SC-001）。引擎/Meter/IOShape 另加單元測試。
- **Rationale**：重構的唯一正確驗收是「行為不變」，而行為的定義就是既有測試。改斷言＝偷偷改行為。
- **驗證**：遷移後 `pytest tests/` 全綠、`git diff` 顯示既有測試檔斷言未動（只可能動 import）。

## R6：零 migration / 零套件確認

- **Decision**：不新增表/欄/migration/套件。`alembic heads` 維持 `0019`。新單位 `image`/`query` 為 `call_records.unit`/`price_list.price_unit` 字串值。multipart（image_edit/stt）沿用 `python-multipart`（階段 29③ 已加）。新增 `upstream` 三個薄 wrapper（litellm 既有函式）。
- **驗證**：`alembic heads`=0019；`grep` 確認 `amoderation`/`asearch`/`aimage_edit` 為 litellm 內建。
