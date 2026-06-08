# Phase 1 資料模型：模型目錄 admin 體驗整合

**無新欄、無新表、無 migration。** 沿用階段 23 `model_catalog.litellm_sync`（JSON 欄）+ `price_list`。

## `litellm_sync`（JSON，既有）— 加 `raw` 鍵

```jsonc
{
  "base_model_key": "azure/gpt-4o",
  "imported_version": "1.85.1",
  "field_sources": { "context_window": "litellm", "modality_input": "litellm",
                     "modality_output": "litellm", "capabilities": "manual" },
  "snapshot": {                       // 映射後 4 欄，給 diff 比對（不變）
    "context_window": 128000,
    "modality_input": ["text", "image"],
    "modality_output": ["text"],
    "capabilities": ["chat", "vision", "function_calling", "prompt_caching"]
  },
  "raw": {                            // 【新】完整 litellm entry（~14 欄、<1KB），供唯讀面板
    "litellm_provider": "azure", "mode": "chat",
    "max_input_tokens": 128000, "max_output_tokens": 16384,
    "input_cost_per_token": 2.5e-06, "output_cost_per_token": 1e-05,
    "cache_read_input_token_cost": 1.25e-06,
    "supports_vision": true, "supports_function_calling": true, "supports_prompt_caching": true
  }
}
```

**規則**：
- `raw` 在建立帶入（`_build_litellm_sync`）與檢查更新採納（`litellm-apply`）時一併寫入/更新。
- `snapshot` 仍只存映射欄，diff 邏輯不變（穩定）。
- 純手動模型 `litellm_sync = null`（零回歸）。

## 能力映射擴充（`litellm_registry._capabilities`）

| 我們的 capability 字串 | litellm 旗標 |
|---|---|
| `chat` | `mode ∈ {chat, completion, responses}` |
| `function_calling` | `supports_function_calling` |
| `vision` | `supports_vision` |
| `reasoning` | `supports_reasoning` |
| `pdf` | `supports_pdf_input` |
| `prompt_caching` | `supports_prompt_caching` |
| `web_search` | `supports_web_search` |
| `audio` | `supports_audio_input` 或 `supports_audio_output` |
| `video` | `supports_video_input` |
| `structured_output` | `supports_native_structured_output` |
| `computer_use` | `supports_computer_use` |

只輸出**為真**的旗標；皆無則 `["chat"]`（同既有預設）。

## `price_list`（既有，不變）

價格帶入/採納仍走 `pricing.create_version`（append-only、`source_note`）。價格對話框「從 LiteLLM 帶入建議價」＝呼叫 `GET /admin/catalog/litellm/suggest/{provider}/{model}`，填入 `suggested_price`，仍可手改後新增版本。
