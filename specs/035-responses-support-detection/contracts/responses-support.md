# Contracts: responses 支援判斷

沿用既有「測試連線」慣例：**測試結果即回應，NEVER raise 5xx for upstream errors**。所有 admin 端點需 admin 認證、寫 audit。

## 1. runtime 軟化閘門 — `POST /v1/responses`（行為契約，非新端點）

- **state = unavailable（手動 blocked）**：事前擋。
  - HTTP 400，body 含 `error.type = "model_responses_disabled"`、清楚訊息（指出為手動停用）。
- **state = available 或 unknown**：不事前擋，直接走既有上游 `aresponses`。
  - 上游成功 → 正常 responses 回應（既有行為）。
  - 上游失敗（含模型實際不支援）→ 既有 `upstream_error` 路徑，回帶上游原因（**非**無資訊 400）。
- 計費、stored-response attribution、其餘管線**不變**。

> 路由慣例：沿用既有 `litellm-apply` 的 `/admin/catalog/models/{slug:path}/<suffix>`。
> 覆寫端點用 **POST**（非 PATCH）以避開 `PATCH /catalog/models/{slug:path}` 萬用路由的貪婪遮蔽。

## 2. admin 測試 responses — `POST /admin/catalog/models/{slug:path}/test-responses`

打一個極小真實 `aresponses` 呼叫（1-token）驗證可否橋接。

**Query**（可選）：`model`（覆寫測試用 representative slug；預設用該 catalog 項自身 slug）。

**回應 200**（結果即回應）：
```json
// 通過
{ "ok": true, "slug": "azure/gpt-5.4", "latency_ms": 412,
  "support": { "state": "available", "source": "tested" } }
// 不通（上游錯誤；仍 HTTP 200）
{ "ok": false, "slug": "azure/foo", "error_type": "upstream_error",
  "message": "<上游原因>", "support": { "state": "unknown", "source": null } }
```
- 通過 → `mark_tested_ok`（除非該模型已是手動 manual，手動優先則不降級，見 §4 互動）。
- 不通 → 不標可用（保持原狀態；若原為 unknown 維持 unknown）。
- **錯誤碼**：`404 not_found`（slug 不存在）。上游錯誤一律走 `ok:false`，不回 5xx。
- 寫 audit（action `responses_test`）。

## 3. admin 手動覆寫 — `POST /admin/catalog/models/{slug:path}/responses-support`

**Body**：
```json
{ "available": true }   // 或 false
```
**回應 200**：
```json
{ "slug": "azure/gpt-5.4", "support": { "state": "available", "source": "manual" } }
```
- `available=true` → `mark_manual_on`（`responses` + `responses:manual`）。
- `available=false` → `mark_manual_off`（`responses:blocked` + `responses:manual`）。
- 手動標記**覆寫**任何實測結果（來源顯示「手動」）。
- **錯誤碼**：`404 not_found`。
- 寫 audit（action `responses_manual_override`，details 含 available）。

## 4. 來源優先互動（測試 vs 手動）

- 讀取永遠：blocked > available；manual source 覆蓋 tested。
- 手動 `available=false` 後，即使「測試 responses」會通，runtime 仍事前擋（state=unavailable）；測試端點可回 `ok:true` 結果資訊，但**不**翻轉手動 blocked 狀態（手動優先）。

## 5. 成員目錄序列化（`GET /catalog` 既有端點擴充）

- `capabilities` 輸出**過濾掉**所有 `responses:*` 內部標記（保留 bare `responses`）。
- 新增欄位 `responses_support: { state, source }`（供徽章顯示來源 + 「Agent 相容」篩選）。
- 「Agent 相容（Responses）」徽章：當 `responses` ∈ capabilities（state=available）顯示，附來源（實測/手動）。
- 成員篩選「Agent 相容」：只列 `state=available` 者。

## 6. LiteLLM 採納（`POST /admin/catalog/litellm/apply/{slug}` 既有端點，merge-preserve）

- 採納 `capabilities` 欄時：`new = litellm 非 responses 能力 ∪ 既有 responses* 標記原樣保留`。
- registry 的 `metadata_from_entry().capabilities` **不**含任何 `responses*`。
- 結果：同步前後 responses 狀態**零增刪**（SC-004）。

## 前端 UI 契約

- **`model-detail.tsx`（admin）**：顯示目前 `state`（可用/不可用/未知）+ `source`（實測/手動/—）；「測試 responses」按鈕（呼 §2，顯示通/不通 + 原因）；可用/不可用切換（呼 §3）。
- **目錄（成員）**：available 模型顯示「Agent 相容（Responses）」徽章 + 來源；facet 篩選含「Agent 相容」。
- **i18n**：`catalog-labels.ts` 採 hyphen 詞彙（`function-calling` 等）+ 補齊缺漏標籤，隨本階段一起上線。
