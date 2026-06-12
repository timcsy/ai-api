# Contract: realtime 即時字幕 WebSocket 端點

**端點**：`GET /v1/realtime`（WebSocket upgrade）— OpenAI 相容 realtime transcription
**認證**：`Authorization: Bearer <應用金鑰>`（連線 header，沿用既有金鑰）或 OpenAI realtime 慣例的 subprotocol header（tasks 階段對齊 OpenAI 客戶端慣例）
**形態**：雙向 WebSocket。客戶端上行音訊、平台下行文字事件。

## 連線生命週期

```
client → (WS upgrade + Bearer key)
         platform: run_preflight(key → allocation → access → quota → model)
   ├─ 不通過 → close(code, reason)  ；不開始串流（FR-002/005/007）
   └─ 通過   → accept；開一條 platform↔Azure WS；進入雙向轉送
client → session.update {type:"transcription", model, audio.format}
client → input_audio_buffer.append {audio: <base64 PCM>}   （重複，串流）
platform→ conversation.item.input_audio_transcription.delta {delta}      （即時，SC-001 <1s）
platform→ conversation.item.input_audio_transcription.completed {transcript}
...
（任一端關閉 / 撤回 re-check 觸發）→ platform: 落帳 CallRecord(unit=minute) → close
```

## Client → Server 事件（平台接受並轉送上游）

| 事件 | 必要欄位 | 平台行為 |
|---|---|---|
| `session.update` | `type:"transcription"`, `model`, `audio.format{type,rate}` | 校驗 model 為 realtime 類型（否則 close，FR-007）；記下 sample_rate/format 供計量；轉送上游 |
| `input_audio_buffer.append` | `audio`（base64 PCM）| **累計 audio_bytes（計量來源，R2）**；轉送上游 |
| `input_audio_buffer.commit` | — | 轉送上游（manual turn detection）|

## Server → Client 事件（平台從上游轉回）

| 事件 | 內容 | 備註 |
|---|---|---|
| `conversation.item.input_audio_transcription.delta` | `delta`（增量文字）| 即時字幕主要輸出；SC-001 首段 <1s |
| `conversation.item.input_audio_transcription.completed` | `transcript`（完整）| 一段話完成；平台在此路徑可記觀測 |
| `error` | `error{code,message}` | 上游錯誤透明轉回；不洩漏上游金鑰（FR-006）|

## 連線關閉碼（平台主動關閉時）

| 情境 | 關閉碼/原因 | 對應 |
|---|---|---|
| 金鑰無效/撤回、無有效分配、配額已滿 | policy violation + 可理解 reason | FR-002, SC-005 |
| 模型非 realtime 類型 | unsupported + reason | FR-007 |
| 連線中分配被撤回/暫停/隔離 | revoked + reason | FR-005, SC-004 |
| 上游斷線/失敗 | upstream_error + 透明原因 | FR-009 |

## 計量契約

- 計量單位：`minute`；數量 = `ceil(Σ append PCM bytes / (rate × bytes_per_sample × channels) / 60)`（精確 rounding tasks 定）。
- 落帳時機：**連線關閉（任何原因，含異常）**——`audio_bytes` 即時累計確保不漏記（FR-004/SC-003）。
- 歸戶：preflight 解出的 allocation；費用 = `calculate_unit_cost`（既有）。

## 不洩漏契約（FR-006）

任何下行事件、錯誤、關閉原因 MUST NOT 含上游 endpoint / key / 內部部署名；上游錯誤轉譯為對使用者可理解的訊息。

## 契約測試（合併前必過）

1. 無效/撤回金鑰連線 → 被 close、未開始串流。
2. 非 realtime 模型 → close(unsupported)。
3. 有效連線 + 送 append → 收到 delta（mock provider WS 回預錄 delta）。
4. 連線關閉 → 寫一筆 `CallRecord(unit="minute")`、quantity 對得上送出的音訊時長。
5. 連線中 mock 撤回分配 → 平台在 N 秒內主動 close(revoked) + 已累計時長落帳。
6. 異常中止（client 直接斷）→ 仍落帳已累計時長（不漏記）。
7. 任何錯誤/關閉訊息不含上游 key/endpoint。
