# Quickstart：scoped application credentials（M:N）驗收

後端由 pytest 自動化；前端清單升層以 vitest + 手動。

## 後端 contract（先 Red 後 Green）

- [ ] **建立多 model key**：`POST /me/credentials`（name + allocation_ids=[A,B]）→ 回明文一次 + scope；list 不含明文。
- [ ] **多 model 各自歸戶**：用該 token 打 model A → 用量/額度記到分配 A；打 model B → 記到 B（互不影響）。
- [ ] **scope 外被拒**：打不在 scope 的 model C → 403 `model_mismatch`、**0 計費**。
- [ ] **歸戶無歧義**：建立/patch 時 scope 內 model 重複 → 409。
- [ ] **擁有者邊界**：scope 加**他人**分配 → 403；移除至 0 → 409。
- [ ] **scope 編輯即時**：patch 加 B → 同 token 立刻能打 B；移除 A → 立刻不能打 A、仍能打 B。
- [ ] **撤回不連坐**：revoke 一把 key → 其所有 model 失效、**其他 key 仍可用**。
- [ ] **admin 治理**：`GET /admin/members/{id}/credentials` 列出；`DELETE/PATCH /admin/credentials/{id}` 改/撤 → 留稽核；成員不可碰他人 key。
- [ ] **device-flow 多選**：`approve {allocation_ids:[A,B]}` → mint 一把涵蓋 A+B 的 key；token 打 A、B 皆通。

## 後端 integration（Postgres）

- [ ] **migration 0017（零回歸）**：seed 舊式單分配憑證 → `alembic upgrade head` → 該舊 token **仍解析/呼叫/歸戶到原分配**；該憑證現等同「scope 含一筆分配」。`device_authorizations` 對 credentials 的 FK 並存無損。
- [ ] **唯一鍵**：`credential_allocations` 的 `UNIQUE(credential_id, resource_model)` 在 Postgres 生效。
- [ ] 全套 `uv run pytest tests/` 零回歸；`ruff` + `mypy` 零警告。

## 前端（vitest + 手動）

- [ ] dashboard 出現**成員層**「我的應用/金鑰」清單（名稱、可用 model、狀態、最後使用）。
- [ ] 建立：命名 + **多選分配** → 遮罩 + 一鍵複製顯示一次。
- [ ] 編輯 scope（加/刪 model）、撤回、rotate 即時更新。
- [ ] 分配詳情頁：唯讀顯示「哪些 app key 含此分配」+「用此分配建 app key」捷徑。
- [ ] device-flow 授權頁分配選單為**多選**。
- [ ] **收尾 A**：舊「如何呼叫」的 Codex 分頁已移除；全站只剩一處 Codex 安裝（一行指令卡）。
- [ ] 桌機 + 360px 手機不溢出（沿用階段 16 RWD）。

## 對應成功標準

| 清單 | SC |
|------|----|
| 一 key 多 model、各自歸戶 | SC-001 |
| scope 外 → 拒絕 + 0 計費 | SC-002 |
| 撤一把、其他不受影響 | SC-003 |
| 既有單分配 token 零回歸 | SC-004 |
| scope 增刪即時生效 + 稽核 | SC-005 |
| 成員不可碰他人；admin 可治理 | SC-006 |
| Codex 一裝多 model `/model` 不 403；單一說明 | SC-007 |
