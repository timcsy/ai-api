# Phase 0 Research: admin 依模型種類一鍵測試模型是否可用

## D1 — 模型種類判定（chat / embedding / tts / image / stt / unknown）

**Decision**：新 helper `services/model_kind.py:model_kind(model) -> str`，判定順序：
1. **litellm mode 優先**（取自既有 `model.litellm_sync["raw"]["mode"]`，Phase 24 已存完整 entry）：
   - `chat` / `completion` → `chat`
   - `embedding` → `embedding`
   - `image_generation` → `image`
   - `audio_speech` → `tts`
   - `audio_transcription` → `stt`（未支援，給說明）
   - 其他（`rerank`/`moderation`/`audio_*` 變體…）→ `unknown`
2. **退路：modality**（手動模型 `litellm_sync` 為 null 時）：
   - `modality_output == ["image"]` → `image`
   - `modality_output == ["audio"]` → `tts`
   - `modality_input` 含 `audio` 且輸出 text → `stt`
   - 其餘（輸出 text）→ `chat`

**Rationale（關鍵陷阱）**：`litellm_registry._modality` 把 **embedding 也映成 `output=["text"]`**（與 chat 撞型）——所以**光看 modality 無法區分 chat 與 embedding**，必須靠 litellm `mode`。`litellm_sync.raw` 已存完整 litellm entry（含 `mode`），直接讀即可，不必另查 registry。手動建立的 embedding 模型（無 `litellm_sync`）會落入 `chat` 退路、被當對話測——已知限制，且測對話呼叫打 embedding 模型會自然失敗、給出可辨識訊號，不致靜默誤判（quickstart 註記；admin 可改用 litellm 對接消除）。

**Alternatives considered**：
- **把 embedding 的 `modality_output` 改成 `["embedding"]`**：要動 `_modality` + 既有資料回填，破壞 Phase 24 約定、可能影響目錄 facet，違反「零 migration / 零回歸」。否決。
- **新增 `mode` 為一等 catalog 欄**：階段 24 已明確「不升 mode 為一等公民」；YAGNI。否決。

## D2 — upstream wrapper（補三種呼叫）

**Decision**：`proxy/upstream.py` 新增三個 async wrapper，沿用既有 `acompletion`/`aresponses` 的「`extra={api_key, api_base?, api_version?}` + drop None kwargs」注入模式：
- `aembedding(*, model, input, api_key, api_base=None, api_version=None, **kwargs)` → `litellm.aembedding`
- `aspeech(*, model, input, voice, api_key, api_base=None, api_version=None, **kwargs)` → `litellm.aspeech`
- `aimage_generation(*, model, prompt, api_key, api_base=None, api_version=None, **kwargs)` → `litellm.aimage_generation`

**Rationale**：`hasattr(litellm, ...)` 已驗證四個函式（含 atranscription）皆存在於既有 litellm 套件——**零新套件**。沿用既有注入模式保持一致、provider 路由（`provider/slug` 前綴）與既有相同。
**驗證待辦（呼應 experience「採用前先印一次回傳值」）**：實作時對 `aspeech`/`aimage_generation` 各 `print(repr(...))` 一次確認回傳 shape（成功判定靠「無例外 + 有 bytes/url」即可，不細解析內容）。

## D3 — 測試呼叫的最小 payload（每種類）

**Decision**：
- **chat**：`acompletion(messages=[{role:"user", content:"ping"}], max_tokens=1)`（同 test-connection）
- **embedding**：`aembedding(input="ping")`
- **tts**：`aspeech(input="hi", voice="alloy")`（最短文字 + 預設聲線；voice 必填）
- **image**：`aimage_generation(prompt="a red dot", size="256x256", n=1)`（最小尺寸、單張）

**Rationale**：對話/embedding 幾乎免費；tts/image 是 billable（見 D4）。`size="256x256"` 為常見最小尺寸（部分新模型僅支援較大尺寸 → 若上游拒絕，回帶上游原因即可，仍是「結果即回應」）。

## D4 — billable 種類的成本閘門（前後端雙保險，FR-004）

**Decision**：測試端點 `POST /admin/catalog/models/{slug:path}/test` body `{acknowledge_billable?: bool}`：
- 先判 `kind`。`stt`/`unknown` → 回 `{ok:false, kind, supported:false, message}`，**不打上游**。
- `kind ∈ {image, tts}`（billable）且 `acknowledge_billable` 非 true → 回 `{ok:false, kind, needs_confirmation:true, billable:true}`，**不打上游**。
- 其餘（chat/embedding，或 billable 已確認）→ 打對應上游，回 `{ok, kind, latency_ms}` 或 `{ok:false, kind, error_type, message}`。
前端：讀模型的 `test_billable`（衍生欄），billable 種類按「測試模型」先跳 `AlertDialog`「此測試會產生一次實際費用」→ 確認後才帶 `acknowledge_billable:true` 呼叫。

**Rationale**：成本閘門**前端 UX + 後端強制**雙層——前端給確認對話框（好體驗），後端對 billable 未確認一律拒打（防直接打 API 誤觸成本），符合 FR-004 可測性（後端可被 integration 驗）。

## D5 — 測試呼叫的計費/用量歸屬（FR-007）

**Decision**：沿用既有測試慣例（`test_provider_connection` / Phase 25 `test-responses`）——測試是**真實上游呼叫但只寫 audit、不寫成員 `CallRecord`**。新增 `AuditEventType.model_tested`（details：`{kind, ok, latency_ms?, error_type?}`），歸戶 `ActorType.admin` / `target=model_catalog/{slug}`。

**Rationale**：與既有兩個測試端點一致；測試呼叫經 audit **可辨識、可追溯到 admin 與時間**，不是匿名影子呼叫（滿足 FR-007「不產生無歸屬影子用量」的意圖——歸屬在 audit 而非成員計費）。寫成員 CallRecord 反而污染成員/平台用量視圖（admin 測試非成員用量）。`AuditEventType` 為 `Enum(native_enum=False)`（VARCHAR），加值零 migration。

**Alternatives considered**：寫一筆特殊 CallRecord（synthetic allocation/subject）→ 需處理計費、污染用量聚合、且無對應分配；複雜度高。否決。

## D6 — 前端入口與既有「測試 responses」並列（FR-008）

**Decision**：model-detail 頁在既有「Agent 相容（Responses）」卡之外（或其旁），加一個「測試模型」動作；按鈕文案/行為依 `test_kind`（對話/embedding 直接打；圖片/TTS 先確認；stt/unknown 顯示「此類型尚不支援自動測試」並停用或點了給說明）。**不**動既有「測試 responses」。

**Rationale**：responses（軸③ gateway 端點）與「模型本身一般呼叫能不能用」是兩個問題，兩顆按鈕並列、各答各的（FR-008）。

## D7 — 零回歸（FR-009）

**Decision**：不改 proxy 熱路徑、不改計費、不改既有端點行為；只新增 upstream wrapper、一個 helper、一個 admin 端點、一個 audit 值、admin `_to_dict` 加兩個衍生唯讀欄。
**Rationale**：SC-005 零回歸；新增面最小。
