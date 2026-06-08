# Phase 0 研究：模型目錄 admin 體驗整合 + 充分利用 LiteLLM

整合 + 擴充，建立在階段 23 之上。所有決策已用真機驗證 litellm 邊界，無 NEEDS CLARIFICATION 殘留。

## Decision 1：能力旗標映射 2 → ~10（決策相關子集）

- **Decision**：`litellm_registry._capabilities` 從目前 2 個（vision、function_calling）擴到約 10 個**會驅動「能不能用來做某事」決策**的旗標：
  `chat`（mode 推導）、`function_calling`、`vision`、`reasoning`、`pdf`（`supports_pdf_input`）、`prompt_caching`、`web_search`、`audio`（`supports_audio_input`/`output`）、`video`（`supports_video_input`）、`structured_output`（`supports_native_structured_output`）、`computer_use`。
- **Rationale**：這些直接對應成員「我能用這模型做 X 嗎」。**不**鏡像全部 34 個旗標（很多是內部協定細節，如 `supports_native_streaming`/`supports_service_tier`）——YAGNI。實測 `azure/gpt-4o` 命中 prompt_caching/vision/function_calling，推理模型會命中 reasoning。
- **Alternatives rejected**：全帶 34 個（雜訊、成員端篩選爆炸）；維持 2 個（資訊浪費，正是本階段要修的）。

## Decision 2：`litellm_sync` 多存完整 raw entry（無 schema、極小）

- **Decision**：`litellm_sync` 加一個 `raw` 鍵存**完整 litellm entry**；`snapshot`（映射後的 4 欄）維持給 diff 比對用、不變。
  ```jsonc
  { "base_model_key": "...", "imported_version": "...", "field_sources": {...},
    "snapshot": { context_window, modality_input, modality_output, capabilities },
    "raw": { /* 完整 litellm entry，~14 欄 */ } }
  ```
- **Rationale**：實測 litellm `model_cost` entry **很精簡**——`azure/gpt-4o` 僅 **14 欄、~429 bytes**（是 pricing/能力中繼，**不含** Codex `models.json` 那種 KB 級 base_instructions）。整包存進既有 JSON 欄成本可忽略，且讓「LiteLLM 原始資訊」唯讀面板有完整內容。diff 仍只比映射欄（穩定）。**無新欄、無 migration。**
- **Alternatives rejected**：另開資料表（YAGNI）；只存映射欄（唯讀面板就沒有完整資訊，違反「充分利用」目標）。

## Decision 3：max_output_tokens 走 raw + 唯讀顯示（不開主欄）

- **Decision**：`max_output_tokens`（實測 gpt-4o=16384）納入 `raw`，由唯讀面板顯示；**不**新增 catalog 主欄（無 migration）。
- **Rationale**：我們 catalog 的 `context_window` ＝ max_input；max_output 是有用但非篩選關鍵的資訊，放唯讀面板剛好。要升主欄＝migration，違反本階段「零 migration」界線。
- **Alternatives rejected**：加 `max_output_tokens` 欄（migration，超出範圍）。

## Decision 4：退役價格硬編 `TEMPLATES` → LiteLLM 建議價

- **Decision**：`prices.tsx` 移除硬編 `TEMPLATES`（6 筆）與「從常見範本帶入」下拉；改為「**從 LiteLLM 帶入建議價**」——用價格對話框已有的 provider + model 組 key（`{provider}/{model}`）呼叫**既有** `GET /admin/catalog/litellm/suggest/{key}`，填入建議價、仍可手改。
- **Rationale**：兩套帶入（硬編範本 vs LiteLLM）並存正是混亂源（原則 5）。統一到 LiteLLM 一個來源、覆蓋 2776 模型 >> 6 筆範本。**0 新端點**（重用階段 23 suggest）。查無 key 時優雅提示、不阻擋手填。
- **Alternatives rejected**：保留範本當 fallback（又回到兩套）；新增價格專用 litellm 端點（重複，suggest 已夠）。

## Decision 5：詳情頁＝單一中樞（徽章 + 檢查更新 + 唯讀面板）

- **Decision**：`model-detail.tsx`：
  - `CatalogModel` 型別加 `litellm_sync`（後端 `_to_dict` 已回傳）。
  - 每個可同步欄位（context/modality/capabilities）旁掛 `<FieldSourceBadge source={field_sources[field]}/>`（litellm/借用/手動）。
  - 「**檢查 LiteLLM 更新**」按鈕掛載既有 `LiteLLMUpdateDiff`（重用，零後端改動）。
  - 唯讀「**LiteLLM 原始資訊**」面板 `<LiteLLMRawPanel raw={litellm_sync.raw}/>`（可折疊）。
  - 列表列的「檢查更新」可保留或移除（建議移除，避免兩處；至少詳情頁要有）。
- **Rationale**：維護動作要在「編輯的地方」（原則 5 集中管理）。重用階段 23 元件，最小新增（2 個小展示元件）。
- **Alternatives rejected**：另做一個整合頁（YAGNI，詳情頁就是天然中樞）。

## Decision 6：零回歸——能力擴充要追所有 sink

- **Decision**：擴充 `capabilities` 後，grep 既有 `capabilities` 的所有讀取點（成員端目錄 facet、admin 顯示、過濾邏輯），確認新增字串不破圖、不破篩選。
- **Rationale**：呼應 experience「**新增資料欄位要追到所有讀寫與顯示點**」——能力是 list-of-strings，多了字串值要確認 facet count / filter / 顯示都容得下。
- **測試**：adapter 能力映射單元測試；成員端目錄既有測試零回歸；前端徽章/面板/價格帶入新測試。
