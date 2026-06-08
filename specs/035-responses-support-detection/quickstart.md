# Quickstart: responses 支援判斷（手動驗收）

前置：本機起後端 + 前端、登入 admin、目錄至少一個 chat 模型（如 `azure/gpt-5.4`）。

## US1 — runtime 軟化閘門（先試，不誤擋）P1 🎯

1. 取一個**未標記** responses 的可橋接模型（state=unknown），對 `/v1/responses` 發極小請求。
   - ✅ 不再回 `model_not_responses_capable` 事前 400；正常完成。
2. 取一個**實際不支援** responses 的模型，發 `/v1/responses`。
   - ✅ 回帶上游原因的 `upstream_error`（非無資訊 400）。
3. admin 把某模型手動設「不可用」後，成員對其發 `/v1/responses`。
   - ✅ 事前擋，`model_responses_disabled`，訊息說明為手動停用。

## US2 — admin「測試 responses」P1

1. model-detail 頁對某可橋接模型按「測試 responses」。
   - ✅ 顯示「通過」+ latency；該模型 state→available、source→「實測」。
2. 對不支援模型按「測試 responses」。
   - ✅ 顯示「不通」+ 上游原因；模型**不**被標可用（維持 unknown）。

## US3 — admin 手動覆寫（手動優先）P2

1. 對某模型手動設「不可用」。
   - ✅ 即使「測試 responses」會通，runtime 仍事前擋；目錄不顯示「Agent 相容」。
2. 對某模型手動設「可用」。
   - ✅ 來源顯示「手動」（蓋過任何實測）。

## US4 — 目錄徽章 + 成員篩選 P2

1. 成員看目錄中一個 available 模型。
   - ✅ 顯示「Agent 相容（Responses）」徽章 + 來源（實測/手動）。
2. 成員用 facet 選「Agent 相容」。
   - ✅ 只列出 state=available 的模型。
3. 檢查任一模型的能力清單。
   - ✅ 不出現裸露的 `responses:tested`/`responses:manual`/`responses:blocked` 內部標記。

## 解耦 / 零回歸（SC-004 / SC-005）

1. 對一個 admin 已標 available 的模型，執行 LiteLLM「檢查更新 → 採納 capabilities」。
   - ✅ 採納後 responses 狀態**不**被洗掉（merge-preserve）。
2. 後端 unit：`reg.metadata_from_entry({"mode":"chat"})["capabilities"]` **不**含 `responses`。
3. 計費：對同一模型同樣請求，採納前後計費結果一致；proxy/目錄/成員端零回歸。
4. `alembic heads` 不變、無新 migration；`pip` 依賴無新增。
