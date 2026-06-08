# Phase 0 研究：模型目錄 ↔ LiteLLM 登錄表對接

所有不確定點已用**真機驗證 litellm 能力邊界**（呼應 experience「採用前先驗證 SDK 能力邊界」），無 NEEDS CLARIFICATION 殘留。

## Decision 1：用 `litellm.model_cost`（bundled）+ `get_model_cost_map`（live）兩份

- **Decision**：
  - **固定版（bundled）** = `litellm.model_cost` —— 隨 litellm 套件附帶的 dict（實測 **2776 筆**），含 `mode`、`max_input_tokens`/`max_output_tokens`、`input_cost_per_token`/`output_cost_per_token`/`cache_read_input_token_cost`、`supports_vision`/`supports_function_calling`。**讀記憶體即得、離線可用**。
  - **線上最新** = `litellm.get_model_cost_map(litellm.model_cost_map_url)`，URL 實測為 `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json`。
  - 單一模型查 `litellm.get_model_info(slug)`。
- **Rationale**：新增帶入（高頻、要快、要可離線）走 bundled；只有「檢查更新」才線上抓最新（決策 D）。litellm 版本＝provenance（實測 `importlib.metadata.version('litellm')` = `1.85.1`），寫進 `source_note`。
- **Alternatives rejected**：自己維護一份模型登錄表（重造輪子、又要追上游）；只用線上（離線/egress 失敗就壞，違反「新增要快」）。

## Decision 2：欄位對應（litellm → 我們的 catalog / 價目）

- **Decision**（adapter `litellm_registry.py` 的 mapping）：

  | 我們的欄位 | litellm 來源 | 換算 |
  |---|---|---|
  | `context_window` | `max_input_tokens`（缺則 `max_tokens`） | 直取 |
  | `modality_input` | `mode` + `supports_vision` | chat→`["text"]`（+vision→`["text","image"]`）；image_generation→`["text"]` |
  | `modality_output` | `mode` | chat→`["text"]`；image_generation→`["image"]`；audio→`["audio"]` |
  | `capabilities` | `supports_function_calling`/`supports_vision`/… | 旗標 → 我們的 capability 字串集合 |
  | 建議價 `input_per_1k` | `input_cost_per_token` | **× 1000**（per-token → per-1k）|
  | 建議價 `output_per_1k` | `output_cost_per_token` | × 1000 |
  | 建議價 `cached_input_per_1k` | `cache_read_input_token_cost` | × 1000（缺則略）|

  實測 `azure/gpt-4o`：input 2.5e-6→`0.0025`/1k、output 1e-5→`0.01`/1k、cached 1.25e-6→`0.00125`/1k、ctx 128000、mode chat、vision/function ✓。
- **Rationale**：對應一次、集中在 adapter，litellm 欄位若改版只改一處。`cost_tier`/`display_name`/`family`/`description` 等**非 litellm 欄位**維持手填（litellm 沒有對應或語意不同）→ 預設來源「手動」。
- **Alternatives rejected**：把 litellm 整包塞進 catalog（欄位語意不一、髒）。

## Decision 3：provenance + 快照存單一 JSON 欄

- **Decision**：`model_catalog` 加 nullable JSON 欄 **`litellm_sync`**：
  ```json
  {
    "base_model_key": "azure/gpt-4o",          // 對照基礎模型（自訂 slug 用）；同名匯入則 = slug
    "imported_version": "1.85.1",
    "field_sources": { "context_window": "litellm", "modality_input": "litellm", "capabilities": "manual", ... },
    "snapshot": { "context_window": 128000, "modality_input": ["text","image"], ... }   // 匯入當下 litellm 值
  }
  ```
- **Rationale**：一欄搞定「哪些欄來自 litellm、匯入時的值、對照基礎模型」，**additive nullable**——migration 極輕（非改 PK、非重建表，不踩階段 18 陷阱）。`field_sources` 讓「檢查更新」能(1)算差異 (2)**手動欄只提示不採納**。沿用本 model「list/dict 用 JSON 欄」既有慣例。
- **Alternatives rejected**：每欄加 `_source` column（爆欄、migration 大）；側表（多一個 entity，YAGNI——無獨立查詢需求，呼應 experience「M:N 不一定先建 entity」）。

## Decision 4：價格走既有 `PriceList` append，不新 schema

- **Decision**：帶入/採納建議價 = 新增一筆 `PriceList`（`input_per_1k_tokens_usd` 等、`effective_from`、`created_by`、**`source_note="litellm@1.85.1"`**）。計費 `current_price_map`/`calculate_cost` 不動。
- **Rationale**：`PriceList` 本就 point-in-time append-only + 有 `source_note` 欄——天生吻合「採納＝新版本、留痕、可回溯」（原則 2）。計費唯一真理不變（原則 5 / FR-009）。
- **Alternatives rejected**：用 litellm 即時算價（破壞可稽核 + 反映不了組織實際成本）。

## Decision 5：線上抓的 timeout + 回退 + egress

- **Decision**：「檢查更新」線上抓設**逾時（~5s）**；逾時/例外 → **回退 bundled `litellm.model_cost`** 並在回應明確標 `source: "bundled-fallback"` + log 原因。對外目標 `raw.githubusercontent.com:443`。
- **Rationale**：呼應 experience「**新增對外連線要檢查 NetworkPolicy egress——本機測不出來**」。egress 目前**埠 443 已開**（provider HTTPS），GitHub raw 多半可達；但若 egress 以目的 IP/網段限制則會擋 → 部署 checklist 明列「驗 `raw.githubusercontent.com:443` 可達」，且回退確保不卡。
- **Alternatives rejected**：無 timeout（admin 卡轉圈）；失敗硬報錯（體驗差，且我們有 bundled 可用）。

## Decision 6：測試策略（TDD + 不打真網路）

- **Decision**：
  - adapter 對應用 `litellm.model_cost` 真實值斷言（deterministic，bundled 隨套件固定）。
  - 線上抓 **mock `get_model_cost_map`**：成功回新值→diff 正確；丟例外/逾時→**回退 bundled** 路徑。
  - migration `0018` Postgres 整合測試（additive 欄、既有目錄/計費零回歸）。
  - 採納價格→斷言新增一筆 `PriceList` 帶 litellm `source_note`、舊版本仍在。
  - 前端：picker 帶入、diff 勾選採納、來源徽章。
- **Rationale**：憲章 I + III；外部依賴的「邊界行為」（timeout/回退）用 mock 驗，不依賴真網路（CI 穩定）。
