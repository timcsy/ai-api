# Contracts: admin 依模型種類測試模型

沿用既有「測試連線 / 測試 responses」慣例：**結果即回應，NEVER raise 5xx for upstream errors**。需 admin 認證、寫 audit。路由沿用 `/admin/catalog/models/{slug:path}/<suffix>`（POST，避開 PATCH 萬用路由）。

## 1. 測試模型 — `POST /admin/catalog/models/{slug:path}/test`

依模型種類分派到對應最小真實呼叫。

**Body**（選填）：
```json
{ "acknowledge_billable": true }
```

**回應 200**（結果即回應；以下皆 HTTP 200）：

```jsonc
// 對話/embedding 通過
{ "ok": true, "slug": "azure/gpt-5.4", "kind": "chat", "latency_ms": 412 }

// 上游失敗（含模型實際不支援）
{ "ok": false, "slug": "...", "kind": "embedding", "error_type": "upstream_error", "message": "<上游原因>" }

// 供應商無可用憑證
{ "ok": false, "slug": "...", "kind": "chat", "error_type": "provider_unavailable", "message": "no active credential for provider 'azure'" }

// billable 種類未確認 → 不打上游
{ "ok": false, "slug": "...", "kind": "image", "needs_confirmation": true, "billable": true }

// 未支援種類（stt / unknown）→ 不打上游
{ "ok": false, "slug": "...", "kind": "stt", "supported": false, "message": "此類型（語音轉文字）尚不支援自動測試" }
```

**分派與閘門**（後端）：
1. 取模型（404 `not_found` 若 slug 不存在）。
2. `kind = model_kind(model)`。
3. `kind ∈ {stt, unknown}` → 回 `supported:false`，不打上游。
4. `kind ∈ {image, tts}` 且 `acknowledge_billable != true` → 回 `needs_confirmation:true`，不打上游。
5. 否則：解供應商憑證（無 → `provider_unavailable`，不打上游），依 kind 打對應最小呼叫：
   - `chat` → `acompletion(messages=[{user:"ping"}], max_tokens=1)`
   - `embedding` → `aembedding(input="ping")`
   - `tts` → `aspeech(input="hi", voice="alloy")`
   - `image` → `aimage_generation(prompt="a red dot", size="256x256", n=1)`
   成功回 `{ok:true, kind, latency_ms}`；任何上游例外回 `{ok:false, kind, error_type:"upstream_error", message:str(e)[:500]}`（**不 5xx**）。
6. 寫 audit `model_tested`（details `{kind, ok, latency_ms?, error_type?}`）；**不**寫成員 CallRecord。

**錯誤碼**：`404 not_found`（slug 不存在）。上游錯誤一律走 `ok:false`，不回 5xx。

## 2. 模型序列化擴充（admin `GET /admin/catalog/models` 既有端點）

`_to_dict` 加三個唯讀衍生欄：
- `test_kind`: `chat|embedding|tts|image|stt|unknown`
- `test_billable`: bool（kind ∈ {image, tts}）
- `test_supported`: bool（kind ∉ {stt, unknown}）

## 前端 UI 契約（`model-detail.tsx`）

- **「測試模型」按鈕**（與既有「測試 responses」並列）：
  - `test_supported == false`（stt/unknown）：按鈕停用或點了顯示「此類型尚不支援自動測試」說明。
  - `test_billable == true`（image/tts）：點按鈕先跳 `AlertDialog`「此測試會產生一次實際費用，要繼續嗎？」→ 確認後以 `{acknowledge_billable:true}` 呼叫；取消則不呼叫。
  - 其餘（chat/embedding）：直接呼叫。
- 結果以 toast 顯示：`ok` → 「測試通過（延遲 N ms）」；`!ok` → 顯示 `message`（上游原因 / 無憑證 / 未支援）。
- 後端回 `needs_confirmation`（理論上前端已先確認，作為防呆）→ 前端跳確認再重打。
