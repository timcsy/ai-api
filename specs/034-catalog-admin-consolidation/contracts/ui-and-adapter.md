# 契約：UI 中樞 + adapter 輸出擴充（重用階段 23 端點）

**0 新端點。** 重用階段 23：`GET /admin/catalog/litellm/search`、`/suggest/{key}`、`POST .../litellm-check`、`.../litellm-apply`。本階段擴充 adapter 輸出與前端 UI 契約。

## A. adapter 輸出擴充（`litellm_registry`）

- **能力映射**：`metadata_from_entry(entry).capabilities` MUST 含為真的決策旗標（chat/function_calling/vision/reasoning/pdf/prompt_caching/web_search/audio/video/structured_output/computer_use）。
  - 契約測試：餵一個含 `supports_prompt_caching=true` 的 entry → capabilities 含 `prompt_caching`；推理 entry（`supports_reasoning=true`）→ 含 `reasoning`；皆無 → `["chat"]`。
- **raw 落地**：`POST /admin/catalog/models` 帶 litellm 對齊建立後，模型 `litellm_sync.raw` MUST 含完整 litellm entry（≥ `mode`、`max_output_tokens`、價格/能力旗標）。
  - 契約測試：建立 `azure/gpt-4o` 對齊模型 → `litellm_sync.raw.max_output_tokens == 16384`、`raw.mode == "chat"`。
- **採納更新 raw**：`litellm-apply` 套用後 MUST 更新 `litellm_sync.raw` 為最新 entry（與 snapshot/imported_version 同步）。

## B. 詳情頁 UI 契約（`model-detail.tsx`）

- **來源徽章**：每個可同步欄位（context_window / modality / capabilities）MUST 顯示來源（litellm / 借用 / 手動），資料取自 `litellm_sync.field_sources`。純手動模型（`litellm_sync=null`）顯示「手動」或不顯示徽章，不誤導。
  - 測試：渲染一個 field_sources 含 litellm+manual 的模型 → 對應徽章正確。
- **檢查更新入口**：詳情頁 MUST 有「檢查 LiteLLM 更新」按鈕，點擊掛載既有 `LiteLLMUpdateDiff`（同時列 metadata + 價格差異、選擇性採納、手動欄不可採納）。
  - 測試：詳情頁有該入口；點開呼叫 `litellm-check`。
- **唯讀原始資訊面板**：詳情頁 MUST 有可折疊「LiteLLM 原始資訊」面板，顯示 `litellm_sync.raw` 全欄；無 litellm_sync 時不顯示。
  - 測試：有 raw 的模型 → 面板展開見 `mode`/`max_output_tokens`；無 raw → 無面板。

## C. 價格帶入契約（`prices.tsx`）

- **退役硬編範本**：價格新增/編輯畫面 MUST NOT 再有硬編 `TEMPLATES` 下拉；改為「**從 LiteLLM 帶入建議價**」，用 provider+model 組 key 呼叫 `GET /admin/catalog/litellm/suggest/{key}` 填入建議價、仍可手改。
  - 測試：畫面無舊範本標籤（如「Azure / OpenAI — gpt-4o」）；有 LiteLLM 帶入入口；帶入後填入建議價，手改後儲存仍 append 版本。
- **查無 key**：suggest 404 時 MUST 優雅提示、不阻擋手填。

## D. 零回歸契約

- 既有 `GET /admin/catalog/models`、建立/更新/刪除、價目 API、`current_price_map`、proxy 計費、**成員端模型目錄 facet 篩選** MUST 行為不變；`litellm_sync=null` 的既有模型一切照舊；新增的 capability 字串不破既有 facet count / filter / 顯示。
