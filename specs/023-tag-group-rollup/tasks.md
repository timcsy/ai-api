---
description: "Tasks for Phase 15 — tag-based group cost rollup"
---

# 任務清單：Tag-based 群組成本 rollup

**輸入文件**：`/specs/023-tag-group-rollup/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/](./contracts/) / [quickstart.md](./quickstart.md)

**測試**：憲章 TDD 不可妥協 → **每個 US 階段先寫失敗測試（Red）才實作（Green）**。

**組織原則**：依使用者故事分組，可獨立實作與測試。

## 格式

`- [ ] TaskID [P?] [Story?] 描述 (含絕對檔案路徑)`
- **[P]**：可並行（不同檔案、無未完成依賴）
- **[Story]**：US1/US2/US3；Setup / Foundational / Polish 不加 Story 標

## 路徑慣例

- 後端：`src/ai_api/`；前端：`frontend/src/`；測試：`tests/`

---

## Phase 1：Setup（共享基礎）

**目的**：本功能無新依賴、無新表——Setup 極小。

- [X] T001 確認本功能不需新增任何依賴 / migration（核對 `pyproject.toml` 與 `alembic/versions/` 無新增）；本任務僅為對齊「純查詢層擴充」前提，無實際檔案變更

---

## Phase 2：Foundational（阻斷性前置）

**⚠️ 沒做完任何 US 都不能開始。**

- [X] T002 在 `src/ai_api/services/usage.py` 將 `GroupBy = Literal["member", "allocation", "model"]` 擴充為加入 `"tag"`（僅型別擴充，分支實作於 US1）

**Checkpoint**：型別就緒，可平行進入 US1-US3。

---

## Phase 3：US1 — 按班級／群組檢視當月支出（P1）🎯 MVP

**目標**：`GET /admin/usage?group_by=tag` 回每 tag 的 token/cost/call 聚合。

**獨立驗收**：quickstart 情境 1、3、5。

### Tests First (Red)

- [X] T003 [US1] 新增 `tests/integration/test_usage_tag_agg.py::test_tag_aggregation_equals_member_sum`：seed 成員 A、B 皆掛 `class-101`、各自呼叫，驗證 `aggregate_usage(group_by="tag")` 的 `class-101` 列 = A+B 之和（token / call_count 逐項）
- [X] T004 [P] [US1] 同檔加 `test_tag_respects_time_range`：A 在區間內/外各有呼叫，驗證只計區間內
- [X] T005 [P] [US1] 同檔加 `test_tag_service_only_filter`：掛 tag 的成員有 service + 非 service 呼叫，`service_only=True` 只計 service
- [~] T006 [P] [US1] ~~`test_tag_member_scope_not_accepted`~~ — **不需要**：tag 維度與 member_id scope 的組合在任何端點都不可達（`/admin/usage` 不傳 member_id；`/me` 不提供 tag 維度）。隔離由 T029（admin-only）覆蓋。設計上排除，無需測試。
- [X] T007 [P] [US1] 新增 `tests/contract/test_usage_tag.py::test_usage_group_by_tag_endpoint`：`GET /admin/usage?group_by=tag&from=&to=` 回 200 + `group_by=tag` + `items` 形狀符合 `contracts/admin-usage-tag.openapi.yaml`
- [X] T008 [P] [US1] 同檔加 `test_existing_group_by_unchanged`：`group_by=member/allocation/model` 仍各自回正確（非破壞性驗證）
- [X] T009 [US1] 跑 T003–T008 確認 **全 Red**

### Implementation (Green)

- [X] T010 [US1] 在 `src/ai_api/services/usage.py` 加 `group_by == "tag"` 分支：`select(MemberTag.tag, sum_*...).join(Allocation, ...).join(MemberTag, MemberTag.member_id == Allocation.member_id).where(*base_filters).group_by(MemberTag.tag).order_by(sum_total.desc())`；用獨立變數名 `tag_stmt`/`tag_rows`（避免多分支型別衝突）；回 `UsageItem`（`group_key=tag`、`display_name=tag`）；`service_only` 套用、`member_id` scope 不套
- [X] T011 [US1] 在 `src/ai_api/api/usage.py` 確認 `group_by` 參數型別已含 `tag`（隨 `GroupBy` 自動）；`GET /usage`、`/usage.json`、`/usage.csv` 無需改動即支援 tag（驗證走既有路徑）
- [X] T012 [US1] 跑 T003–T008 確認 **全 Green**

---

## Phase 4：US2 — 點開某 tag 看成員明細 + 重疊提示（P2）

**目標**：`GET /admin/usage/tag/{tag}/members` 下鑽；前端 Tag 視圖 + 重疊提示。

**獨立驗收**：quickstart 情境 2、4。

### Tests First (Red)

- [X] T013 [US2] 在 `tests/integration/test_usage_tag_agg.py` 加 `test_multi_tag_member_counts_in_each`：成員 C 同掛 `class-101` + `資訊社`、呼叫 300，驗證兩個 tag 聚合都含 C 的 300（重疊正確）
- [X] T014 [P] [US2] 新增 `tests/contract/test_usage_tag.py::test_tag_members_drilldown`：`GET /admin/usage/tag/class-101/members?from=&to=` 回該 tag 成員各自 `UsageItem`，形狀同 member 維度、數字與個別用量一致
- [X] T015 [P] [US2] 同檔加 `test_tag_members_drilldown_empty_tag`：不存在 / 無成員的 tag → 回空 members list（不報錯）
- [X] T016 [US2] 跑 T013–T015 確認 **全 Red**

### Implementation (Green)

- [X] T017 [US2] 在 `src/ai_api/services/usage.py` 新增 `aggregate_usage_for_tag_members(db, *, tag, from_, to, service_only=False) -> list[UsageItem]`：重用 member 分支邏輯 + `WHERE Allocation.member_id IN (SELECT member_id FROM member_tags WHERE tag=:tag)`（subquery 或 JOIN）；回成員 `UsageItem`
- [X] T018 [US2] 在 `src/ai_api/api/usage.py` 新增 `GET /usage/tag/{tag}/members`：`require_admin`（router 既有）、`_validate_range`、呼叫 T017、回 `{"tag":..., "from":..., "to":..., "members":[...]}`，schema 對齊 contract
- [X] T019 [US2] 跑 T013–T015 確認 **全 Green**
- [X] T020 [P] [US2] 在 `frontend/src/routes/admin/usage.tsx` group-by `Select` 加 `<SelectItem value="tag">依 Tag</SelectItem>`；`groupBy` 型別加 `"tag"`
- [X] T021 [US2] 在 `frontend/src/routes/admin/usage.tsx` 當 `groupBy === "tag"`：列表每列一個 tag，列可點擊 → 呼叫 `/admin/usage/tag/{tag}/members` 展開成員明細（可用 expandable row 或 dialog）
- [X] T022 [P] [US2] 在 `frontend/src/routes/admin/usage.tsx` Tag 視圖加常駐重疊提示文字：「成員可掛多個 tag，各 tag 加總可能重複計算、不等於平台總用量」
- [X] T023 [US2] 跑 `npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build` 確認前端零警告

---

## Phase 5：US3 — tag 維度匯出（P3）

**目標**：CSV / JSON 以 tag 維度匯出。

**獨立驗收**：quickstart 情境 6。

### Tests First (Red)

- [X] T024 [US3] 在 `tests/contract/test_usage_tag.py` 加 `test_tag_csv_export`：`GET /admin/usage.csv?group_by=tag` 回 CSV、每列一 tag、數字與 `/usage` 一致
- [X] T025 [P] [US3] 同檔加 `test_tag_json_export`：`GET /admin/usage.json?group_by=tag` 回 `UsageItem` array，結構同既有維度
- [X] T026 [US3] 跑 T024–T025 確認 **Red**（若既有 CSV/JSON 已自動支援 tag 則可能直接 Green——確認 `_serialize_items` 與 csv 產生器對 tag 維度無特例需求）

### Implementation (Green)

- [X] T027 [US3] 確認 `src/ai_api/api/usage.py` 的 `/usage.csv`、`/usage.json` 對 `group_by=tag` 正確運作（多半無需改動——tag 回傳形狀同既有 `UsageItem`）；若 CSV 產生器對某維度有特例（如 allocation 的 service 欄），確認 tag 維度欄位合理
- [X] T028 [US3] 跑 T024–T025 確認 **Green**

---

## Phase 6：Polish 與跨領域

- [X] T029 [P] [US2/US3 隔離] 新增 `tests/contract/test_usage_tag.py::test_tag_endpoints_admin_only`：以非 admin session 呼叫 `group_by=tag` 與 `/usage/tag/{tag}/members`，皆回 401/403（FR-012/013、SC-005）
- [X] T030 跑 `uv run pytest tests/` 全套件確認既有 usage 測試零退化（SC-004）；`pytest --co -q` 確認新增測試 ≥ 10 筆
- [X] T031 跑 `uv run ruff check . && uv run mypy src/` 零警告（**注意：跑 `ruff check .` 全 repo，非單檔**）
- [X] T032 [P] 新增 `knowledge/design/tag-rollup.md`：摘要 research 7 條決策 + 重疊語意自證 + JOIN 拓撲圖；連結回 spec/plan
- [X] T033 [P] 更新 `knowledge/vision.md` 階段 15 條目：完成日期填入後改 ✅、列實際交付、連結 history
- [X] T034 [P] 在 `knowledge/history/completed-phases-detail.md` 追加「## 階段 15：Tag 群組 rollup」詳情（依 Phase 11–13 格式）
- [X] T035 端到端煙霧（本機）：`/admin/usage` 切「依 Tag」→ 點 tag 展開 → 確認重疊提示 → 匯出 CSV 數字一致
- [X] T036 commit + push + 等 CI（**push 前先 `ruff check .` + 前端 lint/build**）；CI 綠後 helm upgrade 至 ai-ccsh；live 跑 quickstart 情境 1 + 4 真機驗證
- [X] T037 收尾：vision 階段 15 改 ✅、history 補上、確認 roadmap 狀態一致

---

## 依賴與順序

```text
Phase 1 (Setup, 極小)
   ↓
Phase 2 (Foundational：GroupBy 加 tag 型別)
   ↓
Phase 3 (US1：tag 聚合) ─── MVP，獨立可上線
   ↓
Phase 4 (US2：下鑽 + 前端) ─── 依賴 US1 的聚合分支
   │
Phase 5 (US3：匯出) ─── 依賴 US1（多半零改動，驗證為主）；可與 US2 平行
   ↓
Phase 6 (Polish：隔離測試 + 文件 + 部署)
```

**MVP 建議**：US1（tag 聚合 + 既有端點/匯出自動支援）即可上線首個價值——admin 能用 API/CSV 看各 tag 用量。US2（下鑽 + 前端 UI）、US3（驗證匯出）為陸續增益。

**[P] 並行機會**：
- Phase 3：T004/T005/T006/T007/T008 [P]
- Phase 4：T014/T015 + T020/T022 [P]
- Phase 5：T025 [P]
- Phase 6：T032/T033/T034 [P]

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 1 | 0 |
| 2 Foundational | 1 | 0 |
| 3 US1（P1，MVP） | 10 | 6 |
| 4 US2（P2） | 11 | 3 |
| 5 US3（P3） | 5 | 2 |
| 6 Polish | 9 | 1 |
| **總計** | **37** | **12** |

---

## 格式檢核

- ✅ 所有任務 `- [ ] T###` 開頭、含 ID、描述、絕對檔案路徑
- ✅ Setup / Foundational / Polish 無 Story 標；US1–US3 任務含 `[US#]` 標
- ✅ 可並行任務標 `[P]`
- ✅ 每 US 階段：Tests First → 跑 Red → Implementation → 跑 Green（TDD）

---

## 下一步

跑 `/speckit.implement` 開始實作；每完成一筆把 `- [ ]` 改 `- [X]`。
