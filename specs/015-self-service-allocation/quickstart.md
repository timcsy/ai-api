# Quickstart：自助領取憑證 驗收場景

## 前置
- Phase 5 / 5.1 / 5.2 已部署（catalog / access policy / tag / allocation 內嵌 / 跨成員總覽已存在）
- admin 已登入；至少一個 provider 有 key、catalog 有一個 model

## 場景 1：admin 開放某 model 自助領取（US1 / SC-006 / SC-003）

1. admin 進某 model 設定 → 開「允許自助領取」、填預設月配額（如 50000）→ 儲存
2. 查該 model：`self_service_enabled=true`、`self_service_default_quota=50000`
3. 對另一個 model 維持關閉
4. 嘗試只開 enabled 不填配額 → **被拒** `quota_required`

**通過判準**：1 分鐘內完成開放；未開放 model 仍關閉；開放必帶配額。

## 場景 2：成員自助領取並呼叫（US2 / SC-001 / SC-002 / SC-005）

1. 用一個被該 model access policy 允許的成員登入 dashboard
2. 「可自助領取」區看到該 model → 按「領取憑證」→ 一次性顯示 token
3. 查 `GET /me/allocations`：多一張 `origin=self_service`、`quota=50000`、active
4. 用該 token 呼叫 `/v1/chat/completions`（在配額內）→ 200，且可溯源到該 allocation
5. 用**不被 access policy 允許**的成員 → 看不到領取入口；直接 `POST /me/allocations` → 403 `model_forbidden`
6. 對**未開放自助**的 model 領取 → 403 `model_not_self_service`
7. 同成員同 model 再領 → 409 `already_claimed`（不重發）

**通過判準**：被允許者 3 點擊 / 30 秒內領到可用憑證、不需 admin；不被允許 / 未開放 100% 領不到；領到的與手動建立行為一致。

## 場景 3：撤回後鎖定、admin 解鎖（US3 / SC-004）

1. admin 在「觀測 → 分配」或成員詳情撤回該自助 allocation → 立即 revoked
2. 該成員再按「領取憑證」→ 403 `reclaim_locked`（提示需 admin 解鎖）
3. admin「觀測 → 分配」看到鎖定列表有此（成員, model）→ 按「解鎖」
4. 成員再領 → 成功（前提 access policy 仍允許、model 仍開放）
5. 查稽核：`self_service_claimed` / `self_service_reclaim_locked` / `self_service_unlocked` 三事件齊備

**通過判準**：撤回後重領成功率 0%；解鎖後可再領；三類事件可稽核。

## 場景 4：相容性回歸（SC-005）

```bash
uv run pytest -q          # 既有 311 + 新測試全綠
cd frontend && npm test -- --run   # 既有 69 + 新測試全綠
```

**通過判準**：既有 allocation / quota pool / 撤回 / catalog / access policy 測試零回歸；`origin` 預設 `admin`、既有 allocation 行為不變。
