# Quickstart 驗收：模型目錄 ↔ LiteLLM 登錄表對接

## 後端 contract / integration（先 Red 後 Green）

- [ ] **adapter mapping**：`litellm_registry.lookup("azure/gpt-4o")` 回 context_window=128000、modality 含 text/image、capabilities 含 vision/function_calling；`suggest_price` 回 input `0.0025`/output `0.01`/cached `0.00125`（per-token×1000）。
- [ ] **search**：`GET /admin/catalog/litellm/search?q=gpt-4o` 命中 `azure/gpt-4o`。
- [ ] **suggest**：`GET …/litellm/suggest/azure/gpt-4o` 回 metadata + 建議價 + slug_default；查無 key → 404。
- [ ] **建立帶入**：`POST /admin/catalog/models` 帶 litellm_sync → 模型落地、欄位來源 = litellm；附建議價 → 產生一筆 `PriceList` 帶 `source_note=litellm@<ver>`。
- [ ] **對照基礎模型**：自訂 slug `azure/gpt-5.4` + `base_model_key=azure/gpt-4o` → 借入 metadata（source=borrowed）、slug 維持自訂、價格自填。
- [ ] **手改轉 manual**：建立後 PATCH 某可同步欄 → 該欄 `field_sources` 轉 manual。
- [ ] **check（live mock）**：mock `get_model_cost_map` 回新值 → `litellm-check` 回 diffs 標 changed + source；mock 丟例外/逾時 → `source:"bundled-fallback"` 仍回 diffs。
- [ ] **apply 選擇性**：`litellm-apply {fields:[context_window]}` → 只更新該欄 + snapshot；含 manual 欄 → 不套用該欄。
- [ ] **apply 價格 append**：採納 `price.input_per_1k` → 新增一筆 `PriceList`、舊版本仍在、`current_price_map` 取最新版。
- [ ] **migration 0018**（Postgres）：`alembic upgrade head` 建出 `litellm_sync` 欄；既有目錄/價目/計費**零回歸**；既有列 `litellm_sync` 為 null。

## 前端（vitest + 手動）

- [ ] 新增模型頁：LiteLLM picker 搜尋 → 選 → 表單自動填（含 slug 預設 + 建議價）；可改任一欄。
- [ ] model 詳情/管理頁：「檢查 LiteLLM 更新」→ diff 對話框逐欄 old→new + 來源徽章 + 勾選採納；manual 欄不可勾或明示。
- [ ] 來源徽章：各欄顯示 litellm / 借用 / 手動。
- [ ] 360px 不溢出（沿用階段 16 RWD）。

## 部署 checklist（egress——experience 教訓）

- [ ] 確認 cluster egress 允許後端連 `raw.githubusercontent.com:443`（埠 443 已開；若以目的 IP/網段限制需放行）。
- [ ] live 驗：admin 按「檢查更新」回 `source:"live"`；若環境擋外連，應回 `source:"bundled-fallback"` 而非卡住/錯誤。

## 對應成功標準

| 清單 | SC |
|------|----|
| 登錄表內模型免手打建立 | SC-001 |
| 自訂 deployment 借對照基礎模型 | SC-002 |
| 欄位來源可見、手改轉 manual | SC-003 |
| 檢查更新逐欄 old→new + 選擇性採納 + 價格 append | SC-004 |
| 線上抓失敗逾時回退固定版 | SC-005 |
| 計費/目錄/proxy 零回歸 | SC-006 |
