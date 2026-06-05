# Quickstart：憑證 UI 收斂 驗收

後端「改名」由 pytest 自動化；UI 收斂以 vitest + 手動。

## 後端 contract（先 Red 後 Green）

- [ ] **改名**：`PATCH /me/credentials/{id}`（`{name}`）→ 名稱改變；該 token 仍可呼叫、可用 model **不變**。
- [ ] **改名 + scope 同送**：`{name, add, remove}` → 兩者皆生效。
- [ ] **owner / admin**：成員改他人金鑰 → 404/403；admin `PATCH /admin/credentials/{id}`（`{name}`）→ 200 + 留稽核 `credential_renamed`。
- [ ] **驗證**：空 / 超長名 → 422/400。
- [ ] 全套 `uv run pytest tests/` 零回歸；`ruff` + `mypy` 清。

## 前端（vitest + 手動）

- [ ] dashboard「我的應用金鑰」每把可**就地改名**（含「預設」）；改名後 token 前綴 / 可用 model 不變。
- [ ] 分配（model）詳情頁金鑰區為**唯讀**：列「能用此 model 的應用金鑰」、每筆顯示其**全部**可用 model、有「前往管理」連 dashboard、**無**撤回 / 新增 / 重新產生。
- [ ] 撤回金鑰確認框**明示**「此金鑰涵蓋的 N 個 model 會一起失效」。
- [ ] device 授權頁 / 安裝 Codex 卡用「**應用金鑰**」字眼；安裝卡說明「會在你的應用金鑰新增一把」。
- [ ] admin 成員詳情頁：唯讀應用金鑰清單 + 撤回 + 改名（走 `/admin/members/{id}/credentials`）。
- [ ] 全站「裝置 / 憑證」對此物件的稱呼掃為「應用金鑰」（grep 收尾）。
- [ ] 桌機 + 360px 手機不溢出；lint/typecheck/build 綠。

## 對應成功標準

| 清單 | SC |
|------|----|
| 只用「應用金鑰」一詞 | SC-001 |
| 管理單一入口 | SC-002 |
| 可改名、不影響 token/model | SC-003 |
| 分配詳情唯讀 + 顯示全部 model + 連本尊 | SC-004 |
| 撤回明示連坐 | SC-005 |
| 零回歸 + RWD | SC-006 |
