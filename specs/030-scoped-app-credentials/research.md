# Research：scoped application credentials（M:N）

## 1. M:N 關聯與「歸戶無歧義」的 DB 級保證

- **Decision**：新增關聯表 `credential_allocations(credential_id, allocation_id, resource_model)`，**把 `resource_model` denormalize 進關聯列**，加 `UNIQUE(credential_id, resource_model)`（+ `UNIQUE(credential_id, allocation_id)`）。解析時 `WHERE credential_id=? AND resource_model=?` → 命中 ≤1 筆 → 唯一決定計費分配。
- **Rationale**：FR-003「一把 key 內 model 不重複」用 DB 唯一鍵硬保證，勝過應用層檢查（免競態）；denormalize 安全，因為 `allocation.resource_model` 是**不可變**（分配建立後 model 固定）。同時讓熱路徑「依 model 挑分配」變成單一 indexed 查詢。
- **Alternatives**：① 純 secondary 無額外欄 + 應用層查 model → 無 DB 級唯一、且要 JOIN allocations 才知 model；② 在 allocations 上做 → 跨 credential 無法表達；③ 不 denormalize、用 partial unique on JOIN → SQLite 不支援。

## 2. proxy 熱路徑：token → credential → 依 model 挑分配

- **Decision**：拆成兩步，對應既有 `preflight.py` 流程（`requested_model` 在 lookup 之前已備妥）：
  1. `lookup_credential_by_token(token) -> Credential | None`（fingerprint 命中 + `revoked_at IS NULL`；節流更新 `last_used_at`）。`None` → **401**。
  2. `resolve_scope_allocation(credential, requested_model) -> Allocation | None`（查 `credential_allocations` by `(credential_id, resource_model)` → allocation）。`None` → **403 `model_mismatch`**（model 不在此 key 範圍）。
  之後沿用既有：該 allocation 的 status（revoked/quarantined/paused）、月配額、access policy、計費——**全部仍 per-allocation、行為不變**。`guard.enforce_model_binding` 退為防禦性 assert（解析已保證 model∈scope）。
- **Rationale**：改動侷限在「解析出哪一筆分配」這一步；status/quota/billing 下游零改。單分配 key → 挑分配等同舊行為 → 零回歸。
- **Alternatives**：① 一個查詢同時 token+model（少一次往返，但 token 無效 vs model 不在 scope 無法區分 401/403）→ 故拆兩步；② 把 model 帶進 `lookup_by_token` 單函式 → 同樣難區分錯誤碼。
- **相容**：保留舊 `lookup_by_token(token) -> Allocation | None` 給非 proxy 呼叫端（顯示用）回「scope 第一筆」或標記 deprecated；proxy 改用新兩步。

## 3. Migration 0017（1:N → M:N，且 credentials 被 FK 參照）

- **Decision**：`credentials` **in-place ALTER**（**不可** drop+rename 整表——`device_authorizations.credential_id`（階段 19）參照它）：
  1. 建 `credential_allocations`（FK→credentials/allocations，唯一鍵）。
  2. `credentials` 加 `member_id`（先 nullable）。
  3. **backfill（raw SQL，跨 DB）**：每列 `member_id ← allocations.member_id`（經舊 `allocation_id`）；`INSERT credential_allocations SELECT id, allocation_id, (SELECT resource_model ...) FROM credentials`。
  4. `member_id` 設 NOT NULL；drop `credentials.allocation_id` 的 FK/index/欄。
  - SQLite 用 `batch_alter_table` 處理加/丟欄（Alembic 重建表時保留 `id` PK → device_authorizations 的 FK 仍指向同名表）；Postgres 走原生 ALTER。
- **Rationale**：保住既有 token（fingerprint 不變）、保住 device_authorizations FK；既有每把單分配 token 變成「scope 一筆」→ 零回歸。
- **Alternatives**：build-new-table+swap（階段 18 招式）→ **這裡不行**，會破壞 device_authorizations 對 credentials 的 FK。
- **Risk/經驗**：「改/加 schema 的 migration 必在 Postgres 整合測試驗」「本機 SQLite 寬鬆、prod Postgres 嚴格」→ migration 與唯一鍵**在 Postgres 跑整合測試**；測試結束 `DROP SCHEMA public CASCADE` 還原（避免污染 metadata-based 測試，階段 18 經驗）。

## 4. 治理邊界（admin vs 成員自助）

- **Decision**：member 端點（`/me/credentials*`，session + 擁有者）只能把 **`allocation.member_id == current_member` 的分配**放進 scope；admin 端點（`/admin/.../credentials`，admin token）可管理任一成員。建立/增刪 scope 時逐筆驗擁有權（attenuation）。
- **Rationale**：原則 5 集中管理 + capability attenuation（不提權）；沿用既有 `current_member` / `require_admin` / `require_csrf`。
- **Alternatives**：只 admin 能建 → 破壞 device-flow 自助；只成員能建 → admin 無治理。兩者皆要。

## 5. device-flow 多選 + 收尾 A

- **Decision**：`POST /me/device/{user_code}/approve` body 從 `allocation_id` 改 `allocation_ids: [..]`（≥1，皆需擁有者）；mint 一把 scope 涵蓋這些分配的 key。授權頁分配選單改**多選 checkbox**（不為 Codex 過濾 model 能力）。安裝腳本：`/device/token` 成功回應**附 scope 的 model 清單**，腳本把預設 `model` 寫進 config.toml（首選一個），其餘靠同把 token 切換。**移除** `api-usage-example.tsx` 的 Codex 分頁。
- **Rationale**：一裝涵蓋多 model、Codex `/model` 不再 403；單一 Codex 安裝來源（收尾 A）。
- **Alternatives**：device-flow 維持單選 → 又回到一裝一 model。

## 6. 前端清單升成員層

- **Decision**：`device-credentials-card.tsx`（階段 18，per-allocation）演進為 `app-credentials-card.tsx`（成員層）：列出成員所有 app key（名稱 / 可用 model / 狀態 / 最後使用），建立（命名 + 多選分配）、撤回、rotate、編輯 scope。掛 dashboard。分配詳情頁改唯讀顯示「哪些 app key 含此分配」+「用此分配建 app key」捷徑。
- **Rationale**：一把 key 跨多分配 → 自然屬成員層，不再掛單一分配底下。
- **Alternatives**：留在分配層 → 與 M:N 矛盾。

## 未解項

- 無 `NEEDS CLARIFICATION`。空 scope：建立至少 1 筆；scope 移除到 0 → 視為錯誤（要保留 ≥1，或顯式改為撤回整把）——採「拒絕移到 0，撤回走撤回端點」。
