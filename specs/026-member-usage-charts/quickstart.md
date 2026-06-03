# Quickstart：成員端圖表驗收

對應 spec 的 SC。後端隔離/一致性由 pytest 自動化；前端視覺以 360px 手動清單。

## 後端（自動化，先 Red 後 Green）

- [ ] **時序正確**：seed 成員 A 跨多憑證多天的呼叫，`GET /me/usage/timeseries`（以 A 登入）回每日 point =
      A **所有憑證**當日和（SC-003）。
- [ ] **隔離（鐵律，SC-002）**：seed A 與 B 的呼叫；以 A 登入打 `/me/usage/timeseries` → 結果**不含** B 的任何
      呼叫；端點**無參數**可指定 B（integration, Postgres）。
- [ ] **未認證** → 401/403；**from ≥ to** → 400。
- [ ] **一致性**：同區間下，趨勢總和 與 `/me/usage` 的總用量、donut（`/me/usage?group_by=model`）各 model 和
      彼此一致（SC-003）。
- [ ] 全套 `uv run pytest tests/` 零回歸；`ruff check .` + `mypy src/` 零警告。

## 前端（vitest）

- [ ] MemberUsageCharts：給定 `/me/usage/timeseries` + `/me/usage?group_by=model` mock，趨勢 bar 與 donut
      正確映射；token/花費可切。
- [ ] 空資料（新成員）→ 兩圖皆顯示空狀態、不報錯。
- [ ] 既有 dashboard 測試零回歸。

## 360px 手機手動驗收（純視覺，SC-005）

以**一般成員**登入 `ai-ccsh.tew.tw`，DevTools 設 360 寬：
- [ ] dashboard 用量區出現「每日趨勢」+「各 model 占比」兩張圖，**不溢出畫面**（base `grid-cols-1`）
- [ ] 切換時段（本週/本月/本季）兩圖一起更新、有載入指示（SC-004）
- [ ] 桌機（≥768px）目視正常；admin 既有圖表行為不變（SC-006）

## 對應成功標準

| 清單 | SC |
|------|----|
| 成員自助看到兩圖 | SC-001 |
| 隔離（A 拿不到 B） | SC-002 |
| 趨勢/donut 與數字一致 | SC-003 |
| 切時段 3 秒內更新 | SC-004 |
| 360px + 桌機不溢出 | SC-005 |
| admin 既有圖零回歸 | SC-006 |
