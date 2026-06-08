# Quickstart 驗收：模型目錄 admin 體驗整合 + 充分利用 LiteLLM

## 後端（先 Red 後 Green）

- [ ] **能力映射擴充**（`tests/unit/test_litellm_registry.py`）：含 `supports_prompt_caching=true` 的 entry → capabilities 含 `prompt_caching`；`supports_reasoning=true` → 含 `reasoning`；皆無 → `["chat"]`。既有 vision/function_calling 不回歸。
- [ ] **raw 落地**（`tests/contract/test_admin_create_with_litellm.py`）：建立 `azure/gpt-4o` 對齊模型 → `litellm_sync.raw.max_output_tokens == 16384`、`raw.mode == "chat"`。
- [ ] **採納更新 raw**：`litellm-apply` 後 `litellm_sync.raw` 同步為最新 entry。
- [ ] 全套 `uv run pytest tests/` 零回歸（目錄/價目/計費/proxy/成員端 facet）；`ruff` + `mypy` 零警告。

## 前端（vitest + 手動）

- [ ] **詳情頁來源徽章**：LiteLLM 帶入的模型每個可同步欄有徽章（litellm/借用/手動）；手改欄顯示手動；純手動模型不誤導。
- [ ] **檢查更新前移**：詳情頁有「檢查 LiteLLM 更新」→ 點開 `LiteLLMUpdateDiff`，同時列 metadata + 價格差異、勾選採納、手動欄不可採。
- [ ] **唯讀面板**：詳情頁「LiteLLM 原始資訊」可折疊，顯示 `raw` 全欄（mode/max_output_tokens…）；無 litellm_sync 不顯示。
- [ ] **價格退役範本**：價格新增畫面無舊硬編範本（「Azure / OpenAI — gpt-4o」等不再出現）；有「從 LiteLLM 帶入建議價」；帶入填入建議價、手改後儲存仍 append 版本。
- [ ] 360px 不溢出（沿用階段 16 RWD）；`lint`/`typecheck`/`build` 綠。

## 對應成功標準

| 清單 | SC |
|------|----|
| 詳情頁一處：徽章 + 檢查更新 + 唯讀面板 | SC-001 |
| 檢查更新詳情頁可完成、選擇性採納、手動欄不覆寫 | SC-002 |
| 價格帶入換成 LiteLLM 建議 | SC-003 |
| 能力 ~10 旗標 + max_output_tokens（raw）+ 唯讀面板 | SC-004 |
| 計費/目錄/proxy/成員端篩選零回歸 | SC-005 |
| 無 migration、無套件、未開可篩選 mode 欄 | SC-006 |
