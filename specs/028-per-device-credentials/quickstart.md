# Quickstart：每分配多 per-device 憑證 驗收

後端/migration 由 pytest 自動化；前端裝置清單以 vitest + 手動。

## 後端 contract（先 Red 後 Green）

- [ ] **新增憑證**：對一筆 active 分配 POST credentials（name="筆電"）→ 回明文一次 + prefix；該 token 可成功呼叫 proxy。
- [ ] **多把並存**：再加一把（name="桌機"）→ 兩把都能呼叫；兩次用量**都歸該分配**。
- [ ] **撤回不連坐**：DELETE 其中一把 → 該把呼叫被拒（鑑權失敗）、**另一把仍成功**。
- [ ] **owner-isolation**：成員對**他人**分配/憑證 GET/POST/DELETE → **403**。
- [ ] **list 不含明文**：GET credentials 只回 prefix/name/時間/狀態，無 token。
- [ ] **admin**：GET 列出某分配所有憑證；DELETE 撤一把 → 留**稽核紀錄**、其他不受影響。

## 後端 integration（Postgres）

- [ ] **migration 0015 + 既有 token 零回歸**：seed「舊式」單憑證（allocation_id 當 PK 的資料）→ 跑 migration →
      該舊 token **仍能解析/呼叫**；該分配現有一把名為「預設」的憑證。
- [ ] **多憑證 lookup 正確**：同分配多把 → 各自 fingerprint 解析到同一分配；撤一把後該 fingerprint 解析不到、其他仍可。
- [ ] 全套 `uv run pytest tests/` 零回歸；`ruff check .` + `mypy src/` 零警告。

## 前端（vitest + 手動）

- [ ] 分配詳情/dashboard 出現「我的裝置/憑證」清單（裝置名、prefix、建立/最後使用、狀態）。
- [ ] 新增裝置 → 遮罩 + 一鍵複製面板顯示一次（vitest 驗複製內容；手動驗遮罩）。
- [ ] 撤回某把 → 清單即時更新。
- [ ] admin 在分配詳情看得到某成員所有憑證、可逐把撤回。
- [ ] 桌機 + 360px 手機皆不溢出（沿用階段 16 RWD）。

## 對應成功標準

| 清單 | SC |
|------|----|
| 一分配 ≥2 把皆可呼叫、歸同分配 | SC-001 |
| 撤一把、其他 100% 仍可用 | SC-002 |
| migration 後既有 token 100% 可用 | SC-003 |
| 成員不能操作他人憑證 | SC-004 |
| admin 列出/撤回 + 稽核 | SC-005 |
| 既有 proxy/計費/配額/領取零回歸 | SC-006 |
