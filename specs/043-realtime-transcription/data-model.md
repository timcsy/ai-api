# Phase 1 Data Model: realtime 即時字幕端點

**核心結論：不新增表、不新增 migration。** realtime 連線本身是 in-memory 的生命週期物件（不落表）；用量沿用既有 `call_records`（增量② 0019 的 `quantity`/`unit`）+ `price_list`（`price_unit`/`price_per_unit_usd`），新單位 `minute` 為字串值。

## 1. RealtimeSession（in-memory，非持久化）

一次 WS 連線的執行期狀態，**不寫表**——只活在連線存活期間，斷線時把累計結果落成一筆 `CallRecord`。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `allocation_id` | str | preflight 解出的歸戶分配（計量落帳對象）|
| `credential_id` | str | 建立連線的應用金鑰（審計用）|
| `member_id` | str | 擁有者（審計用）|
| `resource_model` | str | 請求的 realtime 模型 slug |
| `upstream_model` | str | 對映到上游的模型字串 |
| `started_at` | datetime（tz-aware）| 連線建立時間 |
| `audio_bytes` | int | 累計收到的 PCM 音訊 bytes（計量來源，R2）|
| `sample_rate` / `bytes_per_sample` / `channels` | int | 由 `session.update` 的 format 決定，換算時長用 |
| `close_reason` | enum | `normal` / `client_abort` / `upstream_error` / `revoked` |

**衍生**：`duration_seconds = audio_bytes / (sample_rate × bytes_per_sample × channels)`；`quantity_minutes = ceil(duration_seconds / 60)` 或精確分鐘（tasks 階段定 rounding，對齊計費慣例）。

**狀態轉移**：`connecting`（preflight 中）→ `streaming`（轉送中、累計 audio_bytes、週期 re-check）→ `closing`（任一端關閉或撤回觸發）→ 落帳 `CallRecord` → `closed`。

## 2. CallRecord（既有，沿用）

斷線時寫**一筆**，與其他非 token 端點同機制：

| 欄位 | 值 |
|---|---|
| `allocation_id` | RealtimeSession.allocation_id（歸戶；異常中止仍寫）|
| `quantity` | 累計分鐘數（R2 自算）|
| `unit` | `"minute"`（新字串值，**非新欄位**，0019 已有 unit 欄）|
| `cost_usd` | `calculate_unit_cost(quantity, price_per_unit)`（既有函式）|
| `outcome` | 對映 close_reason（`success` / `upstream_error` …，沿用既有 enum）|
| token 欄 | NULL（非 token 端點，沿用 0019 的 NULL⇒非 token 語意）|

**FR-004 不漏記**：`audio_bytes` 在 relay 迴圈即時累計，故任何斷線路徑（正常/異常/撤回）落帳時都有值。

## 3. PriceList（既有，沿用）

realtime 模型的價以 `price_unit="minute"` + `price_per_unit_usd`（如 gpt-realtime-whisper $0.017）存一筆 point-in-time 版本（append-only）。admin 在既有 `/prices` 設定（單位下拉加 `minute`，沿用階段 29 unit billing 的單位感知 UI）。**LiteLLM 僅建議、PriceList 是計費真理**（不變）。

## 4. Allocation（既有，沿用）

歸戶對象 + 配額載體 + 連線中 re-check 的狀態來源（active / revoked / paused / quarantined）。**不改 schema**。

## 5. model_kind：realtime 類型

`services/model_kind.py` 的 mode→kind 對映加 `realtime`（litellm `mode` 為 realtime/realtime-transcription 時）。對應目錄誠實（FR-008）：realtime 模型顯正確類型、不假裝 chat。**改 model_kind 對映後須重跑全套件**（experience 教訓：有「未知 mode 反例」整合測試會撞）。

---

**Migration 結論**：**無**。沿用 0019 的 `call_records.{quantity,unit}` 與 `price_list.{price_unit,price_per_unit_usd}`；`minute` 是資料值非 schema 變更。RealtimeSession 不落表。
