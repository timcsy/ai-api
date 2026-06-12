# Implementation Plan: realtime 即時字幕端點

**Branch**: `043-realtime-transcription` | **Date**: 2026-06-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/043-realtime-transcription/spec.md`

## Summary

對成員開放一個 **WebSocket 即時字幕端點**：客戶端以分配到的金鑰建立持續連線、串流 PCM 音訊，平台**自寫薄 relay**（借鏡 litellm `RealTimeStreaming` 結構、但接我們的「分配」計費）直連 Azure Foundry 的 gpt-realtime-whisper，即時把 `conversation.item.input_audio_transcription.delta/.completed` 事件轉回客戶端。連線建立跑既有 preflight；連線期間**自行從 append 的音訊 bytes 累計時長**（不依賴 provider usage 事件，天然滿足異常中止不漏記），斷線時記一筆 `unit="minute"` 的 CallRecord 歸戶分配；連線期間定期 re-check 分配狀態，被撤回/暫停/隔離即主動斷線。這是專案**第一個長連線 / WebSocket 端點**，刻意獨立於階段 31 的非串流 registry（比照 `responses.py` 的 SSE 獨立 handler）。

## Technical Context

**Language/Version**: Python 3.11+（後端為主）/ TypeScript strict + React 19（前端僅目錄顯示 realtime 類型 + 連線範例，極少量）  
**Primary Dependencies**: FastAPI（WebSocket — starlette 內建，**專案首次使用**）、SQLAlchemy 2.x async、Pydantic v2（皆既有）；**`websockets`（直連 Azure realtime WS 的 async client，提為直接依賴——已隨 uvicorn/litellm 在 image，現宣告為直接依賴）**；既有 `proxy/preflight.py`、計費（`services/pricing.py` 的 `calculate_unit_cost`）、audit。**realtime 不經 litellm**（其 realtime 是 Proxy form / client 直連，違原則；借其 `RealTimeStreaming` 結構自寫薄 relay）。  
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；**不新增表、不新增 migration**——沿用增量②（0019）的 `call_records.{quantity,unit}` 與 `price_list.{price_unit,price_per_unit_usd}`，新單位 `minute` 為字串值。  
**Testing**: pytest——契約/單元用 starlette `TestClient.websocket_connect` 測「client ↔ 我們」這段；整合測試起一個 **mock provider realtime WS server**（送預錄事件流）驗 relay 轉送 / 時長累計 / 連線中撤回斷線；**真連 Azure realtime WS = 部署後手動煙霧**（見 Constitution Deviation）。  
**Target Platform**: Linux server（k3s-tew / ns ai-ccsh / helm release ai-api）  
**Project Type**: web service（後端為主，前端極少量）  
**Performance Goals**: 首段文字 < 1 秒（SC-001）；per-minute 計量精度到秒換算分鐘。  
**Constraints**: 長連線 WebSocket（與既有 HTTP-only pipeline 形態不同）；連線中撤回 re-check（SLO 對齊既有分配撤回）；nginx 需 WS upgrade proxy；pod egress 需可達 `wss://*.services.ai.azure.com:443`（既有 443 egress 已開，需煙霧實證）。  
**Scale/Scope**: org-internal 課堂/會議並發連線（小規模）；單一新端點 + 薄 relay + 計量 + 前端目錄微調。

## Constitution Check

*GATE: 評估每條核心原則。*

- **I. Test-First（NON-NEGOTIABLE）**：✅ 可遵守。starlette `websocket_connect` 可在測試中建立 client 連線、mock 一個 provider WS server，先寫失敗測試（連線拒絕、轉送、時長累計、撤回斷線）再實作。TDD 流程不受 WS 形態阻礙。
- **II. API 契約優先**：✅ 遵守。realtime 的契約是 **WS 事件流**——`contracts/realtime-transcription.md` 先定 client→server（`session.update`/`input_audio_buffer.append`）與 server→client（`...transcription.delta/.completed`、錯誤/關閉碼）事件，契約測試合併前必過。
- **III. 整合測試覆蓋外部依賴 + CI 可重現**：⚠️ **部分偏離（見 Complexity Tracking / Deviation）**。憲法要求「不得僅以 mock 取代真實邊界、整合測試 CI 可重現」；但真連 Azure realtime WS 是**長連線 + 需憑證 + 即時音訊串流**，無法在 CI 可重現執行。補救：整合測試用 **mock provider WS server** 驗我們這側全部行為；真實邊界以**部署後手動煙霧**驗（比照既有 chat/responses 上游——本專案既有端點的上游真打本就走 mock + 部署煙霧，非 CI 真打）。
- **IV. 可觀測性**：✅ 遵守。連線建立/結束/被撤回斷線、累計時長、計量結果、上游失敗原因皆結構化記錄（沿用既有 audit + CallRecord 透明度，FR-009）；不洩漏上游金鑰（FR-006）。
- **V. 簡潔優先（YAGNI）**：✅ 大致遵守，一個 justified 新依賴。薄 relay 只做單向 transcription、不做雙向對話/工具；**`websockets` 提為直接依賴**是直連 provider WS 的必需（已在 image），於 Deviation 明列。不為未來雙向對話預留抽象。

**結論**：可進 Phase 0。一個 Deviation（CI 無法真打 realtime 上游）+ 一個 justified 依賴（websockets），均於下方明列。

## Project Structure

### Documentation (this feature)

```text
specs/043-realtime-transcription/
├── plan.md              # 本檔
├── research.md          # Phase 0：三個技術未知的決策
├── data-model.md        # Phase 1：realtime session + CallRecord(minute) 計量
├── quickstart.md        # Phase 1：客戶端怎麼連 + 開發者驗證步驟
├── contracts/
│   └── realtime-transcription.md   # WS 事件契約（client↔server）
└── tasks.md             # Phase 2（/speckit.tasks，非本指令產出）
```

### Source Code (repository root)

```text
src/ai_api/
├── proxy/
│   ├── realtime.py        # 新增：WS 端點 handler + 薄 relay（類比 responses.py，獨立於 registry）
│   ├── upstream.py        # 加：開一條到 Azure realtime 的 async WS client（websockets）
│   ├── preflight.py       # 沿用：連線建立時跑（既有）
│   └── registry.py        # 不動（registry 專收非串流同步端點，realtime 不進）
├── services/
│   ├── pricing.py         # 沿用 calculate_unit_cost（unit="minute"）
│   ├── model_kind.py      # 加：realtime kind 判定（mode → realtime）
│   └── model_test.py      # 不動（realtime 不適用 recipe 表的一次性測試；目錄誠實由 model_kind 涵蓋）
└── api/
    └── （realtime WS route 掛載，nginx 既有 /v1 之下加 WS upgrade）

deploy/helm/ai-api/        # nginx WS upgrade（Upgrade/Connection header）config

frontend/src/
├── routes/admin/model-detail.tsx   # realtime kind 顯示（沿用 KIND_LABEL）
└── components/api-usage-example.tsx # realtime 連線範例（WS）

tests/
├── contract/test_realtime_transcription.py   # WS 事件契約
├── integration/test_realtime_relay.py        # mock provider WS：轉送/計量/撤回斷線
└── unit/test_realtime_metering.py            # 音訊 bytes → 時長換算
```

**Structure Decision**：realtime 為**獨立 WS handler**（`proxy/realtime.py`），不納入階段 31 的 `engine/registry`——後者的三軸（IOShape × Meter × call）建在「一請求一回應一筆帳」的同步假設上，realtime 是長連線、破壞該假設（同 `responses.py` 的 SSE 也獨立於 registry）。計量沿用既有 unit billing（`minute` 為新字串單位），**零 migration**。

## Complexity Tracking

> 僅列 Constitution Check 的偏離與須說明的複雜度。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| **原則 III**：realtime 上游真打無法進 CI（整合測試以 mock provider WS server 取代真實邊界） | realtime 是長連線 WS + 需 Azure 憑證 + 即時音訊串流，CI 無法可重現執行；本專案既有上游端點（chat/responses）本就走 mock + 部署煙霧 | 在 CI 真連 Azure realtime WS → 需在 CI 注入生產憑證（安全面）、起即時音訊源、維持長連線，flaky 且昂貴，違反「CI 可重現」初衷 |
| **原則 V / 新依賴**：`websockets` 提為直接依賴 | 直連 Azure realtime WS 需 async WebSocket client；litellm 的 realtime 是 Proxy form（不採），故自寫 relay 必需一個 WS client | 靠 transitive（uvicorn/litellm 帶入）→ 上游一移除即斷，違反「依賴要顯式」；改用 aiohttp → 更重且 image 未必有，websockets 已在 image |
