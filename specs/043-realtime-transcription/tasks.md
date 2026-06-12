# Tasks: realtime 即時字幕端點

**Input**: Design documents from `specs/043-realtime-transcription/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/realtime-transcription.md, quickstart.md

**Tests**: 包含（Constitution 原則 I Test-First 非協商）——契約/整合/單元測試先寫且先失敗，再實作。

**Organization**: 按 user story（P1/P2/P3）分階段，每個 story 以 mock provider realtime WS server 獨立可測。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同檔案、無未完成依賴，可並行
- **[Story]**: US1 / US2 / US3（對映 spec 的 P1/P2/P3）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 依賴與測試基礎建設

- [X] T001 將 `websockets` 提為直接依賴（`pyproject.toml`，已隨 image，宣告版本下限；PR 以 Constitution Deviation 說明）並確認 lockfile 更新
- [ ] T002 [P] 建立 mock provider realtime WS server test fixture（`tests/conftest.py` 或 `tests/support/realtime_mock.py`）：一個可在測試內啟動的假 realtime WS，依輸入送預錄 `...transcription.delta/.completed` 事件流，供所有整合/契約測試共用
- [X] T003 [P] 在計量層登記 `minute` 單位：確認 `services/pricing.py` 的 `calculate_unit_cost` 對 `unit="minute"` 無礙（純資料值、無 schema 變更），補單元測試於 `tests/unit/test_pricing.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 讓 WS 連線能建立並轉送的最小骨架——所有 user story 的前置

**⚠️ CRITICAL**: 本階段未完成前，US1–US3 無法開工

- [ ] T004 實作上游 realtime WS client helper（`src/ai_api/proxy/upstream.py`）：以 `websockets` 開一條到 Azure Foundry realtime endpoint 的連線、注入憑證（api_key/api_base），回傳可雙向收送的連線物件；金鑰不外洩
- [ ] T005 建立 WS 端點 scaffold（`src/ai_api/proxy/realtime.py`）：FastAPI `@app.websocket("/v1/realtime")` accept/close 骨架 + 掛載到 app router（暫不含 preflight/relay 完整邏輯，先讓連線可建立可關閉）
- [X] T006 `services/model_kind.py` 的 mode→kind 對映加 `realtime`（litellm realtime/transcription mode → `realtime` kind）；**改完重跑完整 `pytest tests/` 確認零回歸**（experience：「未知 mode 反例」整合測試會撞）

**Checkpoint**: WS 連線可建立、可開上游連線、目錄能辨識 realtime 類型——可開始 US1

---

## Phase 3: User Story 1 - 開發者用平台金鑰取得即時字幕 (Priority: P1) 🎯 MVP

**Goal**: 有效金鑰 → 建立 WS 連線 → 串流音訊 → 即時收文字 delta；無效/撤回/非 realtime 模型被拒。

**Independent Test**: 用 mock provider WS，有效金鑰連線送 append 收到 delta；無效金鑰被 close。

### Tests for User Story 1 ⚠️（先寫、先失敗）

- [ ] T007 [P] [US1] 契約測試：無效/撤回金鑰連線被 close、未開始串流（`tests/contract/test_realtime_transcription.py`）
- [ ] T008 [P] [US1] 契約測試：請求非 realtime 類型模型 → close(unsupported)（同檔）
- [ ] T009 [P] [US1] 整合測試：有效金鑰連線 + 送 `input_audio_buffer.append` → 收到 `...transcription.delta`（mock provider WS，`tests/integration/test_realtime_relay.py`）

### Implementation for User Story 1

- [ ] T010 [US1] 連線建立時跑既有 `run_preflight`（`src/ai_api/proxy/realtime.py`）：金鑰→分配→存取→配額→model binding；不通過則 close 並回相容錯誤碼（不洩漏上游）
- [ ] T011 [US1] 雙向 relay 迴圈（`src/ai_api/proxy/realtime.py`）：`client→backend` 與 `backend→client` 兩協程轉送（借鏡 litellm `RealTimeStreaming.bidirectional_forward` 結構），delta/completed 即時轉回客戶端
- [ ] T012 [US1] 模型類型校驗 + 錯誤轉譯（`src/ai_api/proxy/realtime.py`）：非 realtime kind → close(unsupported)；上游錯誤透明轉回但不含 key/endpoint（FR-006/007）
- [ ] T013 [US1] 連線生命週期結構化日誌（`src/ai_api/proxy/realtime.py`）：建立/關閉/原因，沿用既有 audit + 觀測（原則 IV）

**Checkpoint**: 客戶端能用平台金鑰即時取得字幕；MVP 成立（計量/撤回尚未接）

---

## Phase 4: User Story 2 - 即時字幕用量按時間計費並歸戶到分配 (Priority: P2)

**Goal**: 每次連線的用量以分鐘計、歸戶分配、計入配額，異常中止不漏記。

**Independent Test**: 連線送已知時長音訊後關閉 → 寫一筆 `CallRecord(unit="minute")`、quantity 對得上；client 直接斷也落帳。

### Tests for User Story 2 ⚠️（先寫、先失敗）

- [ ] T014 [P] [US2] 單元測試：PCM bytes → 秒 → 分鐘換算（含 rounding）（`tests/unit/test_realtime_metering.py`）
- [ ] T015 [P] [US2] 整合測試：連線正常關閉 → 一筆 `CallRecord(unit="minute")`、quantity 對得上、歸戶正確分配（`tests/integration/test_realtime_relay.py`）
- [ ] T016 [P] [US2] 整合測試：client 直接中斷（無正常握手）→ 已累計時長仍落帳（FR-004/SC-003）

### Implementation for User Story 2

- [ ] T017 [US2] RealtimeSession 計量狀態（`src/ai_api/proxy/realtime.py`）：解析 `session.update` 的 format（sample_rate/bytes_per_sample/channels）、在 relay 即時累計 `audio_bytes`
- [ ] T018 [US2] 斷線落帳（`src/ai_api/proxy/realtime.py`）：duration→minute→`CallRecord`（`calculate_unit_cost`、歸戶 allocation、token 欄 NULL、outcome 對映 close_reason）；**任何 close 路徑都落帳**
- [ ] T019 [P] [US2] 前端：admin `/prices` 單位下拉加 `minute`（`frontend/src/routes/admin/prices.tsx`，沿用階段 29 單位感知 UI），realtime 模型可設每分鐘價

**Checkpoint**: US1 + US2——即時字幕可用且用量可計費歸戶

---

## Phase 5: User Story 3 - 分配被撤回時進行中的連線隨即中止 (Priority: P3)

**Goal**: 連線期間分配被撤回/暫停/隔離 → 約定時間內主動斷線，已累計時長落帳。

**Independent Test**: mock 連線進行中撤回分配 → N 秒內 close(revoked) + 落帳。

### Tests for User Story 3 ⚠️（先寫、先失敗）

- [ ] T020 [P] [US3] 整合測試：連線進行中撤回分配 → N 秒內 close(revoked) + 已累計時長落帳（`tests/integration/test_realtime_relay.py`）
- [ ] T021 [P] [US3] 整合測試：分配被暫停/隔離 → 同樣主動斷線（同檔）

### Implementation for User Story 3

- [ ] T022 [US3] 旁路週期 re-check 協程（`src/ai_api/proxy/realtime.py`）：每 N 秒查分配當前狀態，非 active → 主動 close(revoked)；N 對齊既有撤回 SLO（常數集中、可調）
- [ ] T023 [US3] 與 US2 落帳整合（`src/ai_api/proxy/realtime.py`）：撤回觸發的 close 同樣走斷線落帳（已累計時長不漏）

**Checkpoint**: 三個 user story 全部獨立可用

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T024 [P] 前端：`frontend/src/routes/admin/model-detail.tsx` 顯示 realtime 類型（KIND_LABEL）+ `frontend/src/components/api-usage-example.tsx` 加 realtime WS 連線範例（FR-008）
- [ ] T025 [P] nginx WS upgrade config（`deploy/helm/ai-api/`）：`/v1/realtime`（或 `/v1`）加 `Upgrade`/`Connection: upgrade` + `proxy_http_version 1.1`
- [ ] T026 全綠關卡：`ruff check .` + mypy + 前端 tsc/build/test + 完整 `pytest tests/` 零回歸（既有 contract 測試 git diff 為空，SC-006）
- [ ] T027 部署後手動煙霧（quickstart.md，**需憑證環境**）：pod egress `wss:443` 實證、壞金鑰連線被 close、真打一次完整字幕（首字 <1s）→ 用量頁見一筆 `unit=minute` 歸戶分配；R2 計量對照 Azure 帳單校驗

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 無依賴，可立即開始
- **Foundational (Phase 2)**: 依賴 Setup；**BLOCKS 所有 user story**
- **User Stories (Phase 3–5)**: 皆依賴 Foundational
  - US1（MVP）建議先做；US2/US3 在 US1 的 relay 骨架上疊（同檔 `realtime.py`，故 US2/US3 內部多為順序、跨檔的測試/前端可 [P]）
- **Polish (Phase 6)**: 依賴所需 user story 完成

### User Story Dependencies

- **US1 (P1)**: Foundational 後即可——核心連線+轉送，MVP
- **US2 (P2)**: 邏輯上疊在 US1 的 relay（累計 audio_bytes 在轉送迴圈內）；測試/前端可獨立
- **US3 (P3)**: 旁路協程，與 US1 relay 並行；落帳與 US2 共用

### Within Each User Story

- 測試先寫且先失敗 → 實作 → 重構
- relay/計量/撤回多在同一檔 `proxy/realtime.py`，故同 story 內實作任務多為順序；不同檔（前端、測試）標 [P]

### Parallel Opportunities

- T002/T003（Setup）可並行
- 各 story 的測試任務（T007–T009、T014–T016、T020–T021）標 [P] 可並行先寫
- 前端任務（T019、T024）與後端不同檔，可並行
- T025 nginx config 與後端邏輯不同檔，可並行

---

## Parallel Example: User Story 1

```bash
# 先並行寫 US1 全部測試（先失敗）：
Task: "契約測試 無效金鑰被 close — tests/contract/test_realtime_transcription.py"
Task: "契約測試 非 realtime 模型 close — tests/contract/test_realtime_transcription.py"
Task: "整合測試 有效連線收 delta（mock provider WS）— tests/integration/test_realtime_relay.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational（CRITICAL）→ 3. Phase 3 US1 → **STOP & VALIDATE**（mock provider WS 跑綠 = MVP）→ 視情況先以 mock 驗收，真打留 T027。

### Incremental Delivery

1. Setup + Foundational → 基礎
2. US1 → 即時字幕可用（mock 驗）→ MVP
3. US2 → 計費歸戶 → 可上線（計費完整）
4. US3 → 連線中撤回 → 治理完整
5. Polish（前端目錄/範例 + nginx + 全綠 + 部署煙霧）

### 真打限制（誠實標記）

- T009/T015/T020 等整合測試**全用 mock provider WS**（CI 可重現，Constitution Deviation 的補救）。
- **T027 真連 Azure realtime WS 需憑證環境**（維護者實機跑 quickstart）——R1/R2 的協定接通 + 計量對照在此校驗，非 CI。

---

## Notes

- [P] = 不同檔、無依賴；relay/計量/撤回集中於 `proxy/realtime.py`，同 story 實作多順序。
- 每個 task 或邏輯群組後 commit；測試先失敗再實作。
- 改 `model_kind`（T006）後務必跑完整 `pytest tests/`（experience 教訓）。
- 既有端點零回歸鐵證：既有 contract 測試檔 git diff 為空（SC-006）。
