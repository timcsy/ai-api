# Phase 0 Research: realtime 即時字幕端點

本檔釘死 spec 刻意延後到規劃階段的三個技術未知。研究方式：inspect 本地 litellm realtime 模組（藍本）+ OpenAI/Azure realtime transcription 官方協定 + 既有專案設施盤點。**端到端真連 Azure realtime WS 安排在 implement 階段於有憑證環境**（用戶已有 Azure Foundry 部署 + key）——本階段把「協定 / relay 結構 / 計量方法 / 基礎建設方案」釘到可實作的程度。

---

## R1：直連 provider realtime WS 的協定與 relay 結構

**Decision**：自寫薄 relay，借鏡 litellm `RealTimeStreaming` 的雙向轉送結構，但**不經 litellm**、改接我們的分配計費。協定走 OpenAI 相容 realtime transcription：

- 客戶端 ↔ 我們（FastAPI `@app.websocket`）：客戶端送 `session.update`(`type:"transcription"`, `model`, `format`)、`input_audio_buffer.append`(base64 PCM)、`input_audio_buffer.commit`；我們回 `conversation.item.input_audio_transcription.delta`（增量）/`.completed`（完整）。
- 我們 ↔ Azure（`websockets` async client）：以 Azure Foundry realtime endpoint + key 開 WS，雙向轉送事件。
- relay 骨架（借自 litellm `realtime_streaming.py:RealTimeStreaming`）：`bidirectional_forward()` = 同時跑 `client→backend` 與 `backend→client` 兩個轉送協程；在 `backend→client` 路徑上**攔截** `conversation.item.input_audio_transcription.completed` 做我們的記帳/觀測。

**Rationale**：litellm 的 realtime 是 Proxy form（client 直連 provider、音訊不經 gateway），用它會失去原則 2 可追蹤性與原則 3 即時撤回（experience 第 40 條）。但它的**轉送結構**是成熟藍本，借結構、自接計費＝站在肩膀上又守原則。OpenAI 相容協定讓任何會講 realtime 的客戶端（會議/字幕工具）能直接接（願景「主流工具開箱即用」）。

**Alternatives considered**：
- litellm Proxy form realtime relay → 否決：client 直連、不認得「分配」（experience 第 40 條、principles 原則 5）。
- litellm `_arealtime`（library 低階入口）→ 否決：內部 API、不穩定、且仍偏 Proxy 取向；自寫薄 relay 控制權更清楚（原則 7 適配層）。
- 從零摸 realtime 協定 → 否決：litellm `RealTimeStreaming` 已把 beta↔GA 事件 remap、轉送骨架做過，借鏡省大量試錯。

---

## R2：per-minute 計量的來源

**Decision**：**我們自己從客戶端 `input_audio_buffer.append` 的 PCM bytes 累計音訊時長**，斷線時換算分鐘記一筆 `CallRecord(quantity=分鐘, unit="minute")`，不依賴 provider 回 usage 事件。時長 = Σ(append PCM bytes) / (sample_rate × bytes_per_sample × channels)。

**Rationale**：
- OpenAI realtime transcription 官方文件**未保證 usage / 計量事件**（WebFetch 實證：transcription guide 無 usage 欄位）；gpt-realtime-whisper 按**音訊分鐘**計費（$0.017/min）。
- 自己從 append bytes 算時長＝**自包含、不受 provider 是否回 usage 影響**，且**天然滿足 FR-004「異常中止不漏記」**——已 append 的音訊就算數，連線怎麼斷都已累計。
- 對應 experience「STT per-second 計量沒 duration 來源就降級」的延伸：這次 duration 來源是「我們轉送的音訊量」，可控可算，不必賭 provider 回什麼。
- 沿用增量②（0019）的 `call_records.quantity/unit` + `calculate_unit_cost`，`minute` 為新字串單位——**零 migration**。

**Alternatives considered**：
- 信 provider 的 usage 事件 → 否決：文件不保證有；若有則作為**校驗**而非主來源（implement 階段真打時對照）。
- 連線 wall-clock 時間（含靜音）→ 否決：可能與 provider 按「音訊時長」計費不一致，傾向高估；以實際 append 的音訊量為準較貼近計費基礎。
- 按 transcript 字元/token → 否決：gpt-realtime-whisper 按分鐘非按 token，單位不符。

**Implement 階段待校驗**：真打一次 Azure，比對「我們算的分鐘」vs「Azure 帳單/若有的 usage 事件」，必要時加校正係數（admin 可覆寫價，沿用 PriceList 是計費真理）。

---

## R3：FastAPI WS relay + nginx WS upgrade + egress + 連線中撤回

**Decision**：
- **端點**：FastAPI `@app.websocket("/v1/realtime")`（或對齊 OpenAI 路徑），starlette 內建、`websockets` 15.0.1 已在 image。
- **連線建立 preflight**：WS accept 前（或 accept 後第一個 `session.update`）跑既有 `run_preflight`（金鑰→分配→存取→配額→model binding）；不符即關閉連線回相容錯誤碼。
- **連線中撤回**：在 relay 迴圈旁跑一個**週期性協程**，每 N 秒 re-check 該分配狀態（沿用既有撤回查詢），狀態非 active（撤回/暫停/隔離）即主動 close WS。N 對齊既有撤回 SLO（具體值 tasks 階段定，預設與既有一致）。
- **nginx**：在既有 `location /v1`（或新 `location /v1/realtime`）加 `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_http_version 1.1;`——標準 WS upgrade。
- **egress**：pod 需可達 `wss://<foundry>.services.ai.azure.com:443`；既有 443 egress 已開（OCR 那次驗過 `raw.githubusercontent.com:443`），WS over 443 同通——**部署煙霧實證**。

**Rationale**：FastAPI/starlette 原生 WS + websockets client 都已在 image，無基礎建設缺口；nginx WS upgrade 是標準配置；撤回用「旁路週期協程」而非阻塞 relay，乾淨且符合原則 3（長連線不能只在建立時檢查一次）。對應 experience「串流端點事後記帳在 client 還連著時做」——計量綁在連線存活期累計、斷線點落帳。

**Alternatives considered**：
- 撤回檢查塞進每個 audio 事件 → 否決：耦合轉送熱路徑、頻率不可控；旁路週期協程更清楚。
- 不做連線中撤回（只建立時檢查）→ 否決：違反原則 3 即時撤回（長連線的核心風險）。
- 走 SSE 而非 WS → 否決：realtime transcription 是雙向（音訊上行 + 文字下行），SSE 只能單向下行。

---

## 研究結論彙整（給 Phase 1 / tasks）

| 未知 | 結論 | 落地 |
|---|---|---|
| 協定 + relay 結構 | OpenAI 相容 transcription 事件流；借 litellm `RealTimeStreaming` 雙向轉送骨架自寫 | `proxy/realtime.py` + `upstream` WS client |
| 計量來源 | 自算 append 音訊時長 → `unit="minute"`，不賭 provider usage | `services` 計量 + `CallRecord(quantity,unit)`（0019，零 migration）|
| 基礎建設 + 撤回 | FastAPI WS + websockets（已在 image，提直接依賴）；nginx WS upgrade；旁路週期協程 re-check 撤回 | `realtime.py` + helm nginx config |
| 真打驗證 | 安排 implement 階段於有憑證環境（Constitution Deviation：不進 CI，部署煙霧）| quickstart 驗證腳本 |
