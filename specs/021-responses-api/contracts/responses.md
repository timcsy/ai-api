# Contract: `POST /v1/responses`

**Branch**: `021-responses-api` | 對應 FR-001~018

OpenAI Responses API 相容端點。本契約定義平台對外行為；上游細節（litellm /
provider）不在此規範。憲章原則 II（契約優先）：實作前此契約須過審。

---

## 認證

- Header: `Authorization: Bearer <allocation-token>`（同 `/v1/chat/completions`）。
- 缺 / 格式錯 → `401 unauthorized`。

## 請求（application/json）

Responses 形態，主要欄位（透傳上游，平台不窄化）：

| 欄位 | 必填 | 說明 |
|------|------|------|
| `model` | ✅ | 模型 slug（可含 `provider/` 前綴） |
| `input` | ✅ | string 或 items 陣列 |
| `stream` | ✕ | `true` 時回 SSE（Codex 預設 true） |
| `tools` / `tool_choice` / `parallel_tool_calls` | ✕ | function calling |
| `reasoning` / `include` | ✕ | 推理設定、加密 reasoning include |
| `store` | ✕ | `true` 時平台保存回應並回傳可接續的 `response_id` |
| `previous_response_id` | ✕ | 接續先前回應（須屬同一分配） |
| `instructions` / `max_output_tokens` / `temperature` / `top_p` / `text` / `metadata` | ✕ | 透傳 |

## 前置檢查（依序，沿用既有 pipeline）

1. Bearer token 解析 → 否則 `401 unauthorized`
2. JSON 解析 + `model`(string)、`input`(存在) 驗證 → 否則 `400 bad_request`
3. provider allowlist → 否則 `403 provider_not_allowed`
4. allocation lookup + bind（拒絕也帶 allocation_id）
   - revoked → `403 allocation_revoked`
   - quarantined → `403 allocation_quarantined`
   - paused → `403 allocation_paused`
5. 月度配額 → 超過 `403 quota_exceeded`
6. model binding → 不符 `403 model_mismatch`
7. model access policy → 不符 `403 model_forbidden`
8. 模型 capability 含 `responses` → 否則 `400 model_not_responses_capable`
9. （若帶 `previous_response_id`）歸屬檢查 → 不符 `403 response_forbidden`；
   不存在/過期 `404 response_not_found`
10. credential 解析 → 無 `503 provider_unavailable`

## 回應

### 非串流（`stream` 省略 / false）

`200` + Responses 物件（JSON）。含 `id`（若 `store=true` 為平台 `response_id`）、
`output[]`、`usage{input_tokens,output_tokens,total_tokens,output_tokens_details,
input_tokens_details}`。

### 串流（`stream=true`）

`200`，`Content-Type: text/event-stream`，原樣轉發上游 SSE 事件序列：
`response.created` → `response.output_item.added` →
`response.output_text.delta` / `response.function_call_arguments.delta` →
`response.output_item.done` → `response.completed`（含終局 `usage`）。

- 端到端不緩衝（FR-018）。
- client 斷線：已產生用量仍記錄（FR-017）。

## 錯誤封包

統一沿用既有 `{ "error": { "code", "message", "request_id" } }`（經驗教訓「錯誤封包
shape 一致」）。`message` 經 redact，**絕不含 provider key**（FR-008）。

| HTTP | code | 觸發 |
|------|------|------|
| 400 | `bad_request` | body 非法 / 缺 model 或 input |
| 400 | `model_not_responses_capable` | 模型未標記支援 responses |
| 401 | `unauthorized` | 憑證缺/無效/已撤回（新請求） |
| 403 | `allocation_revoked` / `_quarantined` / `_paused` | 分配狀態 |
| 403 | `quota_exceeded` | 超月度配額 |
| 403 | `model_mismatch` / `model_forbidden` | 綁定 / 存取政策 |
| 403 | `response_forbidden` | `previous_response_id` 非本分配（歸屬隔離） |
| 404 | `response_not_found` | `previous_response_id` 不存在 / 已過期 |
| 502 | `upstream_error` | 上游失敗 |
| 503 | `provider_unavailable` | 無可用 credential |

## 計費（成功路徑）

- token 對應與公式見 data-model R3。
- usage 來源：非串流取回應 body；串流取終局 `response.completed`。
- 每次呼叫（成功 / 拒絕）皆 `record_call` 並歸戶分配（FR-007）。

## 契約測試要點

- 各前置檢查的拒絕路徑回正確 code 且帶 `allocation_id`。
- `model_not_responses_capable` 對未標記模型生效。
- 歸屬隔離：A 分配的 `response_id` 被 B 拒（`response_forbidden`）。
- 負向：回應 / 串流 / 錯誤 / 日誌不含 provider key。
- 計費分項：reasoning / cached token 正確落帳與計價。
