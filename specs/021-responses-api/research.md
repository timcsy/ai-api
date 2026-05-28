# Phase 0 Research: Responses API / Agent 工具（Codex）相容

**Branch**: `021-responses-api` | **Date**: 2026-05-28

本檔解析 plan 階段的技術未知，所有決策皆標明理由與被否決的替代方案。

---

## R1. 路由架構：統一 litellm vs 混合 pass-through

**Decision**: **所有 provider 統一走 `litellm.aresponses()`**（含 `stream=True`），
不另寫 OpenAI/Azure 的原生 raw pass-through 路徑。保留「若真機驗證發現 litellm
對某 Codex 欄位失真，才針對 Azure 加狙擊式 raw pass-through」作為 fallback。

**Rationale**:
- 實測 `litellm.aresponses` 的參數涵蓋完整 Responses 介面：`input`、`instructions`、
  `tools`、`reasoning`、`include`、`store`、`previous_response_id`、`parallel_tool_calls`、
  `extra_headers`、`extra_query`、`stream` 等。Codex 依賴的進階欄位（加密 reasoning
  的 `include`、`store=false`、`previous_response_id`、工具）litellm 都能承載。
- 對 OpenAI/Azure，litellm 直呼原生 `/responses`，等同高保真 pass-through；對
  Anthropic/Gemini，litellm 自動橋接（含 streaming）。**單一路徑同時拿到保真與通用。**
- 符合憲章原則 V（YAGNI）：vision.md 原述「混合 pass-through」會產生兩條 code path，
  正中經驗教訓「同一概念兩份必 drift」。統一 litellm 是更簡的設計。
- 符合既有架構（階段 5 已以 litellm library form 支援多 provider），延續經驗教訓
  「build vs adopt：先確認形態」——本功能明確採 litellm **library form** 的
  `aresponses`，不啟用其 Proxy server。

**Alternatives considered**:
- *混合：OpenAI/Azure raw httpx pass-through + 其他 litellm*（vision.md 初版設想）：
  保真度最高但兩條路徑、與既有架構不一致、維護成本高。**否決**——litellm aresponses
  已能對 OpenAI 家族高保真，多一條 raw 路徑不符 YAGNI。列為 fallback 而非預設。
- *全部自寫 raw reverse-proxy（繞過 litellm）*：放棄多 provider 通用，違背願景。**否決**。

**對 spec/vision 的影響**：這是相對 vision.md「混合策略」的**精煉**——對外行為不變
（OpenAI 家族保真、其他降級），但實作收斂為單一 litellm 路徑。plan 採此為準。

---

## R2. Streaming 串流轉發與 usage 擷取

**Decision**: `aresponses(stream=True)` 回傳的事件非同步迭代器，以 FastAPI
`StreamingResponse`（`media_type="text/event-stream"`）原樣轉發為 SSE；同時在
轉發迴圈中擷取終局 `response.completed` 事件的 `usage`，串流結束後再 `record_call`。

**Rationale**:
- Codex 全程依賴 SSE 事件序列（`response.output_text.delta`、
  `response.function_call_arguments.*`、`response.output_item.done`、`response.completed`）。
- usage 僅出現在終局事件；必須邊轉發邊 sniff，待 `response.completed` 才有完整
  token 數可計費。
- client 中途斷線：迭代器拋出 `asyncio.CancelledError` / 連線中止時，以 `finally`
  確保已擷取到的 usage（即使不完整）仍 `record_call`（FR-017）。

**Alternatives considered**:
- *非串流（一次回傳）*：Codex 無法使用（會逾時且體驗差）。**否決**——streaming 是硬需求。
- *自行緩衝整段再回*：違背即時性與 FR-018。**否決**。

---

## R3. 計費資料模型擴充（reasoning / cached token）

**Decision**:
- `call_records` 加兩個 nullable 欄位：`reasoning_tokens`、`cached_tokens`（Alembic 0013）。
- `price_list` 加一個 nullable 欄位：`cached_input_per_1k_tokens_usd`（同一 migration）。
- token 對應：`input_tokens→prompt_tokens`、`output_tokens→completion_tokens`、
  `output_tokens_details.reasoning_tokens→reasoning_tokens`、
  `input_tokens_details.cached_tokens→cached_tokens`。
- 計費公式：
  `cost = (prompt_tokens − cached_tokens)/1k × input_price`
  `     + cached_tokens/1k × cached_price（缺則用 input_price）`
  `     + completion_tokens/1k × output_price`
  （`completion_tokens` 已含 reasoning，不重複加。）

**Rationale**:
- OpenAI 規定 `output_tokens` 已包含 reasoning_tokens，故 reasoning 只另存供分析、
  計費不重複（FR-011 不漏算）。
- `input_tokens` 已包含 cached_tokens，故對 cached 部分改套折扣價（FR-011）。
- 欄位皆 nullable：對話補全（chat/completions）路徑不填新欄位、零退化（呼應階段 9
  「admin 路徑零退化」做法）。
- migration 須在 Postgres 上跑（憲章原則 III + 經驗「datetime tz-aware」「PG-safe migration」）。

**Alternatives considered**:
- *不加欄位、用既有三欄*：使用者已明確要求精確分項，**否決**。
- *把 cached 折扣做成 PriceList 之外的設定表*：YAGNI 違反，**否決**——append-only
  價目版本加一欄即可，沿用既有 point-in-time 選取。

---

## R4. Server-side 對話狀態（store / previous_response_id）

**Decision**: 自建 `stored_responses` 表記錄歸屬與接續映射：
`response_id`(PK, 平台回傳值) / `allocation_id` / `provider` / `upstream_response_id`(上游原值)
/ `created_at` / `expires_at`。
- `store=true`：呼叫成功後寫一筆，回傳平台 `response_id`。
- `previous_response_id`：先在本表查歸屬——必須屬於當前分配（FR-015），否則拒絕；
  通過後翻譯為上游 `upstream_response_id` 再轉發（provider 端負責實際脈絡）。
- TTL：`expires_at` 預設 30 天；逾期接續回「找不到/已過期」；清理沿用既有 cronjob 模式。

**Rationale**:
- 歸屬隔離（FR-015）是原則「可追蹤性 + 憑證隔離」的硬要求——即便 provider 端自身
  store，平台仍必須有一張「response_id → 分配」的歸屬表來擋跨分配接續。
- 只存映射與歸屬（不存完整對話內容），因 provider 端已持有脈絡；平台僅當「歸屬守門員
  + id 翻譯」。較存全文輕量、且不重複保存敏感對話內容（YAGNI + 隱私）。
- 非 OpenAI provider 若不支援 server-side store，則該 provider 的 `store=true` 回明確
  不支援訊息（與 FR-005 同精神）。

**Alternatives considered**:
- *存完整對話內容自行 replay*：重、且要處理加密 reasoning 內容保存，隱私與體積成本高。
  **否決**——provider 已存脈絡，平台存映射即可。
- *直接透傳 provider response_id 不自建表*：無法做歸屬隔離（任何人可猜 id 接續他人對話），
  違反 FR-015。**否決**。

---

## R5. 模型 Responses 支援標記

**Decision**: 沿用 `model_catalog.capabilities`（既有 JSON list 欄位）新增 `"responses"`
標記；路由前檢查，未標記則回「此模型不支援此端點」。catalog 載入檔（YAML）對支援
Responses 的模型補上此 capability。**無 schema 變更。**

**Rationale**: 符合 YAGNI——既有 `capabilities` 正是放此類能力旗標的地方，不需新欄位。

**Alternatives considered**:
- *新增 `supports_responses` 布林欄*：多一欄一個 migration，`capabilities` 已足。**否決**。

---

## R6. 端點結構與共用 pipeline

**Decision**: 抽出共用前置 pipeline 為 helper（暫名 `proxy/preflight.py`：bearer →
allocation lookup+bind → 狀態 → quota → model binding → model access → credential 解析），
回傳「已驗證的呼叫上下文」。`/chat/completions` 改用它；新增 `/v1/responses`
（暫置 `proxy/responses.py`）也用它。兩端點只差請求驗證、上游呼叫、usage 擷取。

**Rationale**:
- 經驗教訓「同一概念兩份必 drift」「拒絕路徑必須在 raise 前綁定上下文」——共用 helper
  須沿用既有「先 lookup+bind allocation、再檢查狀態」順序，確保拒絕也帶 `allocation_id`。
- 重構既有 `/chat/completions` 屬行為保持（既有測試為安全網，符合 TDD）。

**Alternatives considered**:
- *複製 pipeline 到新端點*：必 drift，**否決**。

---

## R7. nginx / ingress SSE 不緩衝

**Decision**: frontend nginx 對 `/v1/responses`（及 `/v1/` 串流）加 `proxy_buffering off`
與 `proxy_read_timeout`/`proxy_cache off`；Traefik ingress 確認預設不緩衝 SSE（必要時
加對應 annotation）。以真機 Codex 串流驗證收尾。

**Rationale**: 搜尋顯示 Codex + proxy 環境最常見的失敗是 SSE 被中介緩衝→502/timeout
（FR-018 / SC-005）。經驗教訓「部署完成 ≠ 跑得起來」——須真機驗證，不能只靠單測。

**Alternatives considered**:
- *只信任單元測試*：無法捕捉緩衝/逾時問題，**否決**。

---

## 技術未知解析狀態

| 未知 | 狀態 |
|------|------|
| litellm 是否支援完整 Responses 介面 + streaming | ✅ 已確認（aresponses 參數涵蓋全表面） |
| usage 在 streaming 何處取得 | ✅ 終局 `response.completed` 事件 |
| 計費 schema 如何擴充 | ✅ R3（2 欄 call_records + 1 欄 price_list） |
| store/歸屬隔離如何實作 | ✅ R4（自建映射表） |
| 模型支援標記 | ✅ R5（既有 capabilities） |
| nginx SSE | ✅ R7（不緩衝 + 真機驗證） |

無殘留 NEEDS CLARIFICATION。
