# Research: OpenAI 相容 `/v1/models` ＋ Copilot 上卡

所有問題皆有既有先例可循，無遺留 NEEDS CLARIFICATION。

## R1：`/v1/models` 的 scope 來源——金鑰 active 分配，而非 catalog 瀏覽過濾

- **Decision**：列舉**呼叫金鑰 scope 內、狀態為 `active` 的分配**對應的模型。資料路徑：`parse_bearer_token` → `AllocationService.lookup_credential_by_token(token)` → credential → 新增 `list_active_scope_allocations(credential)`（`Allocation` JOIN `CredentialAllocation`，過濾 `Allocation.status == active`）。**不**再套 `ModelAccessService.visible_to_member`（catalog 用的 credential gate ∩ access policy）。
- **Rationale**：分配本身**就是**存取授權（原則 1：額度/歸戶綁分配）。金鑰能 scope 到某分配，代表該成員已被授予該 model——再疊一層 catalog 政策是重複、且兩條判斷可能分歧（catalog 的 credential gate 看「provider 有無 active ProviderCredential」是**瞬時 infra 狀態**，不該決定「這把金鑰被授予什麼」）。語意對齊 spec FR-002「這把金鑰能用哪些模型」與階段 34「如何使用**這把**金鑰」。
- **active 過濾（FR-006）**：排除 `paused`/`revoked`/`quarantined` 分配，避免「列得出卻打不通」。`revoked` 金鑰本身在 `lookup_credential_by_token` 已被 `revoked_at IS NULL` 擋下（→ 401）。
- **未定價模型（FR-007）**：因 scope 來源不碰 pricing，未定價模型自然仍列出。
- **Alternatives considered**：
  - 重用 `/catalog/models` 的 `visible_to_member`（成員全部可見目錄）——**否決**：那是「瀏覽整個目錄」語意（成員層、session 認證），與「這把金鑰能用什麼」（金鑰層、Bearer 認證）不同軸；且會把 provider 瞬時不可用算進可發現性。
  - 額外加 provider-credential 可用性過濾以保證 100% 可呼叫——**否決**：provider 暫時無 credential 是 infra 瞬時狀態，真打時自然回 `provider_unavailable`（502/503），不該讓模型「忽隱忽現」；SC-002 的「100% 路由成功」其括號已界定為**識別碼對得上**（見 R2），非 provider 永遠在線。

## R2：模型識別碼形式——正規 slug（含 provider 前綴）

- **Decision**：`id` 回傳 `Allocation.resource_model`（正規 slug，如 `azure/gpt-5.4`），即 preflight 的 `canonical_model`／路由鍵。
- **Rationale**：`run_preflight` 對帶前綴的請求**精確比對** `resource_model`（`resolve_scope_allocation`：`"/" in model` 即只走 exact match）。回傳正規 slug → 客戶端原樣送回 → 必中 exact path → SC-002 成立。bare slug 是「自帶 catalog 的 client（Codex）」的相容別名，不該當作對外正典識別碼（見 experience「前置 client 自帶模型目錄…正規 slug／provider 前綴是 litellm 路由必需」）。
- **Alternatives considered**：回傳 bare slug（`gpt-5.4`）——**否決**：bare 只有「唯一 strip 相符」時才 alias，金鑰若同時有 `azure/X`+`openai/X` 會歧義（`resolve_scope_allocation` 回 None）；正規 slug 永遠無歧義。

## R3：OpenAI `GET /v1/models` 回應 schema 與欄位取值

- **Decision**：
  - List：`{"object": "list", "data": [ <model>, ... ]}`。
  - Model object：`{"id": <resource_model>, "object": "model", "created": <unix ts>, "owned_by": <provider>}`。
  - `created`：取該分配對應 `model_catalog.created_at` 的 epoch（join 既有目錄；查無則用分配 `created_at`）——穩定、非必要精準。
  - `owned_by`：provider 前綴（`azure`/`openai`/`anthropic`/`gemini`…），以 `parse_provider(resource_model)` 取。
- **Rationale**：OpenAI SDK（`client.models.list()` → `SyncPage[Model]`）只強依賴 `id` 與 `object`；`created`/`owned_by` 為慣例欄位，給穩定值即可。多數客戶端（含 Copilot）只用 `id` 構選單。
- **Alternatives considered**：附帶平台自有 metadata（modality/capabilities/price）——**否決**：OpenAI `Model` 無這些欄位，混進去非標準、客戶端也不讀；要看詳情走既有 `/catalog/models`。保持 `/v1/models` 純 OpenAI 相容（YAGNI）。

## R4：retrieve 單一模型語意

- **Decision**：`GET /v1/models/{id:path}` 用 `resolve_scope_allocation(credential, id)`（沿用 exact + 唯一 bare alias），命中且該分配 active → 回該 model object；否則 404 `{"error":{"code":"not_found",...}}`。`{id:path}` 容許 slug 內的 `/`（`azure/gpt-5.4`）。
- **Rationale**：與 list 同一條 scope/identifier 邏輯（單一真理，不另寫比對）；404 不洩漏 scope 外存在性（對齊 catalog `get_model` 的 404-on-deny 模式）。
- **Alternatives considered**：retrieve 只接受 exact、不 alias——可，但與呼叫端 `resolve_scope_allocation` 行為一致更好（同進同出）。採一致。

## R5：GitHub Copilot 接入形態 + 驗證計畫

- **Decision**：以「**VS Code GitHub Copilot 指向 OpenAI 相容自訂端點**」為驗證標的。卡內容在維護者真機驗證**可日常使用**後才正式上架；無法可靠驗證的功能誠實標限制（FR-010）。
- **已知行為 / 坑（來自既有 experience + 本次盤點）**：
  - Copilot 會打**模型清單**（本功能補的 `/v1/models`）與 **embeddings**（階段 29① 已開）→ 兩者就緒是上卡前提。
  - Copilot 的 `apiType=responses`（伺服器端對話狀態）**同金鑰跨 model 切換**會撞 per-allocation 隔離 → `response_forbidden`；過期 → `response_not_found`。抉擇已定：**明確吐錯、不靜默降級**（experience「接不上的續接請求要明確拒絕」）。本功能把訊息做**可操作**並在卡上事先說明（US3）。
  - 驗收非自動化單測可涵蓋 → SC-004 為**部署後真機**驗收（沿用階段 19 SC-006、32 realtime 真打、34 SC-007 模式）。
- **Rationale**：Copilot 非主驗客戶端，先確認「列模型 + 對話」端到端通，再上卡，避免「列了卻處處紅字」（願景階段 34 排除項原文）。
- **Alternatives considered**：直接上卡不驗證——**否決**，違 FR-010 與願景「確認能日常用再上卡」。先做 device-flow 式一鍵安裝——**否決/延後**：Copilot 無 Codex 那種 CLI 一鍵管道，v1 給「設定步驟 + 建金鑰捷徑」即可（YAGNI）。
