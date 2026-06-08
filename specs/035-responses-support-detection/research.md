# Phase 0 Research: responses 支援判斷（實測 + 手動雙來源）

## D1 — responses 狀態 + 來源的儲存承載（零 migration）

**Decision**：以既有 `model_catalog.capabilities`（JSON list）的**內部標記約定**承載，集中於單一 helper `src/ai_api/services/responses_support.py`：

| 標記字串 | 意義 |
|---|---|
| `responses` | responses 可用（既有；徽章/proxy 既有皆已認得此值） |
| `responses:blocked` | admin 手動標「不可用」（唯一事前封鎖） |
| `responses:tested` | 來源＝實測 |
| `responses:manual` | 來源＝手動 |

讀出狀態（helper `get_support(caps) -> {state, source}`）：
- `responses:blocked` 在 → `state=unavailable, source=manual`
- 否則 `responses` 在 → `state=available`；`source = tested if responses:tested else manual if responses:manual else None`
- 皆不在 → `state=unknown, source=None`

寫入（helper 提供四個轉換，皆「先清掉全部 `responses*` 標記再重設」，保持互斥）：
- `mark_tested_ok` → `{responses, responses:tested}`
- `mark_tested_failed` → 清空（回 unknown；測試失敗不標可用，符合 US2-3）
- `mark_manual_on` → `{responses, responses:manual}`
- `mark_manual_off` → `{responses:blocked, responses:manual}`

**Rationale**：
- 零 migration、零新欄（Constitution V / spec FR-007 / Assumptions）。`capabilities` 既是 JSON list，加標記不需 schema 變更。
- `responses` 既有值正是「可用」徽章與舊 proxy 閘門所讀，沿用不破壞既有資料/前端。
- 冒號子標記（`responses:*`）為**內部標記**，成員 facet 序列化時過濾掉（只露 `responses` 徽章），不污染畫面。
- 全部約定封裝在一個 helper，三軸解耦（responses 不再從 mode 推導）有單一真相來源，避免散落。

**Alternatives considered**：
- **新增 nullable 欄 `responses_support`（migration 0019）**：語意最乾淨，但違反 spec「零 migration」假設且增加 schema 變更面；標記約定已足夠表達三態 + 來源，YAGNI 下不值得。
- **存進 `litellm_sync` sidecar**：與 FR-006「LiteLLM 不碰 responses / 解耦」直接矛盾（responses 會被綁進 litellm 物件，且 manual 模型 `litellm_sync=null`）。否決。
- **用 `tags` 欄**：`tags` 是成員可見的描述性標籤，混入控制狀態語意不清。否決。

## D2 — runtime 軟化閘門（FR-001/002）

**Decision**：`src/ai_api/proxy/responses.py` 既有閘門（line ~277）
```py
if not await model_supports_responses(session, requested_model):
    return await reject("model_not_responses_capable", ...)
```
改為**只在手動 blocked 時事前擋**：
```py
support = await responses_support.lookup(session, requested_model)  # reads capabilities
if support.state == "unavailable":   # admin 手動 blocked → 唯一事前封鎖
    return await reject("model_responses_disabled",
        f"model '{requested_model}' has been manually disabled for the responses endpoint", 400)
# 其餘（available / unknown）一律先試，走既有上游 aresponses 呼叫；
# 打不通由既有 upstream_error 路徑回帶真實原因（FR-001 場景 2）
```

**Rationale**：實際能不能用由真實呼叫決定（spec 核心想法），解掉「誤擋」與「旗標過時」；手動 blocked 是 admin 明確意圖，保留為唯一事前封鎖（FR-002、US3）。既有上游錯誤已能 surface 為 `upstream_error`（Assumptions），不支援模型會自然回帶原因錯誤，無需新邏輯。

**Alternatives considered**：保留靜態旗標僅放寬 unknown→try——仍會被「同步洗掉旗標」害到（latent bug），且 admin 標 available 的實測結果無處落地。否決。

## D3 — admin「測試 responses」端點（FR-003）

**Decision**：在 `admin_catalog.py` 新增 `POST /admin/catalog/{slug}/test-responses`，**沿用 `admin_providers.py:test_provider_connection` 的「結果即回應」模式**：打一個極小 `aresponses` 呼叫（1-token、`input="ping"` 或等價最小體），成功回 `{ok: true, latency_ms}` 並 `responses_support.mark_tested_ok`；失敗回 `{ok: false, error_type, message}` 且**不**標可用（測試失敗→保持 unknown）。NEVER raise 5xx for upstream errors。寫 audit。

**Rationale**：複用既有成熟模式（1-token ping、結果即回應、不 5xx），最小新面積；admin 明確觸發、極小呼叫，不在熱路徑（Assumptions）。

**Alternatives considered**：自動在成員首次呼叫時實測並落地——違反「不在成員熱路徑反覆自動測」（Edge Cases）。否決。

## D4 — admin 手動覆寫端點（FR-004，手動優先）

**Decision**：`PATCH /admin/catalog/{slug}/responses-support`，body `{available: bool}` → `mark_manual_on` / `mark_manual_off`。手動標記用 `responses:manual`，其狀態（available 或 blocked）皆蓋過任何實測（讀取時 blocked 最先判、manual 來源覆蓋 tested）。寫 audit。

**Rationale**：給 admin 最終裁量；手動優先由 helper 讀取順序保證（blocked > available；manual source 覆蓋 tested）。

## D5 — LiteLLM 解耦 + merge-preserve（FR-006）

**Decision**：
1. `litellm_registry._capabilities`：**移除** `mode in (...)` 分支裡 `caps.append("responses")` 那行（連同把 responses 從 mode 衍生的註解），改為 `_capabilities` 永不產生任何 `responses*`。`chat` 仍從 mode 產生。
2. `admin_catalog.admin_litellm_apply`：採納 `capabilities` 欄時改 **merge-preserve**——`setattr(m, "capabilities", merged)`，其中 `merged = [litellm 非 responses 能力] + [保留 m.capabilities 既有的所有 responses* 標記]`。helper 提供 `preserve_into(new_caps, old_caps)`。
3. 既有測試 `test_litellm_registry.py` 中斷言 `responses in caps` 的兩處（`test_lookup_maps_metadata`、`test_chat_mode_yields_chat_and_responses`、`test_capabilities_expanded_decision_flags`）需改為斷言 responses **不**由 registry 產生。

**Rationale**：直接修掉 latent bug（同步洗掉 admin 設的 responses → Codex 突然不能用）；三軸解耦的硬性要求（FR-006、Edge Cases「同步不洗掉」、SC-004）。

## D6 — 目錄徽章 + 成員 facet（FR-005）+ i18n 併入

**Decision**：
- 成員目錄序列化（`catalog.py`）：輸出 `capabilities` 時**過濾掉 `responses:*` 內部標記**（只保留 bare `responses` → 既有 `FACET_LABELS["responses"]="Agent 相容（Responses）"` 徽章），並另外輸出 `responses_support: {state, source}` 供徽章顯示來源 + 「Agent 相容」篩選。
- 前端 `model-detail.tsx`：admin 區塊顯示目前 state/source + 「測試 responses」按鈕 + 手動可用/不可用切換。
- **i18n 併入**：上一輪 i18n 修正（`catalog-labels.ts` 的 hyphen 詞彙 + 缺漏標籤）現已在工作樹/檔內（見已讀檔），確認對齊後隨本階段一起上線，**不另外單獨 deploy 那個 commit**。

**Rationale**：把判斷結果變成成員看得懂的資訊（原則 6 可達性）；i18n 修正與本階段同屬 responses/能力顯示面，合併乾淨上線避免額外部署。

## D7 — 計費與零回歸（FR-007）

**Decision**：不動 `responses.py` 第 5 步之後的儲存/計費/attribution；billing model_key 仍用 `canonical_model`。軟化閘門只改第 4 步的判斷條件，不改其餘管線。

**Rationale**：SC-005 零回歸；本功能只動軸③判斷，不碰計費。
