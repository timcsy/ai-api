# Research: 計費一般化（非 token 單位）+ OCR 端點

## R1：PriceList 一般化——加兩個 nullable 欄，token 欄不動

- **Decision**：`price_list` 加 `price_unit`（varchar nullable，NULL ⇒ 沿用 token 語意）+ `price_per_unit_usd`（Numeric(12,8) nullable）。**token 價列維持原樣**（`price_unit` NULL、用既有 `input/output_per_1k_tokens_usd`）；**非 token 價列**（OCR）設 `price_unit="page"` + `price_per_unit_usd=<每頁價>`，既有的兩個 NOT NULL token 欄填 `0`（對 page-billed 模型無意義）。
- **Rationale**：純加欄＝最安全的加法式 migration。**不**把既有 token 欄改成 nullable——SQLite 不支援直接 ALTER COLUMN drop NOT NULL，得整表 rebuild（Alembic batch），對既有資料風險更大、複雜度更高。token 欄填 0 是小瑕疵但完全隔離、不影響 token 計費。
- **Alternatives considered**：
  - *獨立 per-unit 價表*：多一個 entity + join，違反 YAGNI（一個維度欄就夠）。
  - *把 token 欄改 nullable*：SQLite ALTER COLUMN 重建痛、爆炸半徑大。否決。

## R2：CallRecord 一般化——加 quantity + unit，token 呼叫留空

- **Decision**：`call_records` 加 `quantity`（Integer nullable）+ `unit`（varchar nullable，NULL ⇒ token 語意）。**token 呼叫**（chat/embedding）`unit` NULL、`quantity` NULL，沿用既有 token 欄；**OCR 呼叫** `unit="page"`、`quantity=頁數`、token 欄 NULL、`cost_usd` 照填。
- **Rationale**：加法式、token 路徑零改動。`unit` 是字串維度 → 未來 second/character/image 加單位＝加資料、不改 schema（原則 7、YAGNI）。
- **Alternatives considered**：把 token 數塞進 `quantity` 統一——會破壞既有 token 分析（input/output 分項），且 token 有兩個量（prompt/completion）無法用單一 quantity 表達。否決。

## R3：OCR 頁數來源——`len(OCRResponse.pages)`，退 `usage_info`

- **Decision**：計費 `quantity` = `len(response.pages)`（實測 `litellm.aocr` 回 `OCRResponse(pages: List[OCRPage], usage_info: Optional[OCRUsageInfo], ...)`）；若 `usage_info` 帶明確 pages 則優先用之；兩者皆無 → `quantity=None`、`cost=0`、仍記一筆（不無聲）。
- **Rationale**：呼應經驗「**採用 SDK 前先印一次真實回傳值**」——已 `inspect` 確認 `OCRResponse.pages` 存在，不憑印象。頁數即計費單位（對齊 `ocr_cost_per_page`）。
- **Alternatives considered**：信任輸入文件自報頁數——上游才知道實際處理頁數，以回應為準較準。

## R4：OCR 端點形狀——`POST /v1/ocr`，body `{model, document}`，複製 embeddings.py

- **Decision**：`proxy/ocr.py` 近乎複製 `proxy/embeddings.py`：`run_preflight` → `upstream.aocr(model, document, api_key, api_base, api_version)` → `pages` → 查每頁價 → `calculate_unit_cost` → `record_call(quantity, unit="page", cost)`；拒絕/錯誤沿用 `record_and_respond` + `_outcome_for_code`。`document` 為 JSON dict（litellm `aocr` 既定型別，URL 或 base64）→ **無 multipart/binary**。`upstream.py` 加 `aocr` wrapper（Phase 26 已加 aembedding/aspeech/aimage_generation，此為第 4 個，零新套件）。掛 `/v1`。
- **Rationale**：原則 7「加端點 ≈ 同一條 preflight + 對應 litellm 函式 + 記帳」；embeddings 已驗證此樣板。JSON document 避開 binary 是選 OCR 而非 TTS/STT 的關鍵理由。
- **Alternatives considered**：multipart 文件上傳——本階段明確避開（binary I/O 留後續）。

## R5：model_kind 加 ocr + 目錄誠實（呈現層）

- **Decision**：`model_kind.Kind` 加 `"ocr"`；`mode=="ocr"` → `ocr`。成員目錄已輸出 `kind`（Phase 38），故 OCR 模型自動帶 `kind="ocr"`；前端 `api-usage-example` 依 `kind==="ocr"` 顯 `/v1/ocr` 範例。
- **Rationale**：FR-010「不得把 OCR 假裝成 chat」——`kind` 欄是成員面的誠實訊號（OCR 顯 OCR、顯對的呼叫方式）。`litellm_registry._capabilities` 的 `or ["chat"]` 深層 un-fake 是更廣的清理（影響 capability facet），**不在本階段**；本階段以 `kind` 達成成員面誠實即可。
- **Alternatives considered**：本階段一併重構 `_capabilities`——範圍蔓延、且 capability 與 kind 是不同軸（守住軸正交，原則 7）。延後。

## R6：配額——非 token 呼叫此階段不被 token 配額擋下

- **Decision**：OCR 走完整 `run_preflight`（憑證 / 分配 / 模型存取 / 上游憑證），但**不**被「每月 token 配額」擋下（token 配額無法度量「頁」）；花費仍記錄、歸戶可見。每單位用量上限（每天 N 頁）為後續工作。
- **Rationale**：spec 已列為已知限制；硬把頁正規化成 token＝假統一（原則 7 反例）。誠實的最小範圍。
- **Alternatives considered**：用花費（USD）當通用配額軸——是合理的未來方向，但牽動配額模型重構，超出本階段。標記為後續。

## R7：litellm 建議每頁價——讀 `ocr_cost_per_page`，admin 設/覆寫進 PriceList

- **Decision**：litellm `model_cost[...]["ocr_cost_per_page"]`（OCR 模型已帶，Phase 24 存於 `litellm_sync.raw`）當**建議每頁價來源**；admin 透過價格端點設定/覆寫，快照進 PriceList（append-only、point-in-time）。計費只用 PriceList（建議缺漏/錯誤 → admin 覆寫）。
- **Rationale**：沿用 Phase 23/24「litellm 建議、PriceList 是真理」+ 原則 7「借計算不借帳本」。
- **Alternatives considered**：直接用 litellm cost 計費——違反「計費只信平台價目表」+ 不認得我們的分配。否決。

## R8：calculate_cost 一般化——新增 `calculate_unit_cost`，token 路徑不動

- **Decision**：保留 `calculate_cost(prompt_tokens, completion_tokens, price, ...)` 完全不動（token 零回歸）；新增 `calculate_unit_cost(quantity, price_per_unit) -> Decimal`（純 `quantity × price_per_unit`）。OCR 路徑呼叫後者。
- **Rationale**：不碰既有函式＝token 計費 byte-identical；新單位走新函式，職責清楚。
- **Alternatives considered**：把兩者合一個多型函式——徒增既有 token 路徑的回歸風險。否決（YAGNI + 零回歸優先）。
