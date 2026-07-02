---
description: "Task list for 異常偵測 v2（管理員可暫停自動隔離 + 稀疏 baseline 聰明放寬 + 門檻可調 + 解除更好找）"
---

# Tasks: 異常偵測 v2

**Prerequisites**: spec.md、plan.md、data-model.md、contracts/anomaly-config.md
**Tests**: TDD——測試先於實作。後端契約 `tests/contract/test_anomaly_config.py` + 單元 `tests/unit/test_anomaly_evaluate.py`；前端 `anomaly-config.test.tsx`。

## Phase 1: Setup
- [X] T001 基線：`pytest tests/ -q -k anomaly` + 現有 anomaly 測試綠（比對零回歸起點）。

## Phase 2: Foundational（阻斷全部——DB 單例 + 單一讀取入口 + lazy-seed）
- [X] T002 [test] `tests/contract/test_anomaly_config.py` 寫失敗測試：全新 DB → `GET /admin/anomaly/config` lazy-seed 自 settings（enabled=true、門檻＝現值）、建列。先紅。
- [X] T003 新建 `src/ai_api/models/anomaly_config.py`：`AnomalyConfig` 單例（`CHECK id=1` + 各門檻 CHECK），`models/__init__.py` 匯出。
- [X] T004 新建 `alembic/versions/0022_anomaly_config.py`：create table（down_revision=0021）；up/down 對稱。
- [X] T005 `services/anomaly.py` 加 `get_anomaly_config(db)`：get-or-create + lazy-seed（`baseline_min_calls` 預設 200）。
- [X] T006 [單一真理] `evaluate_allocation` + `detect_and_quarantine` 改讀 `get_anomaly_config`，不再直接讀 `settings.anomaly_*`（config.py 保留為 seed 來源）。
- [X] T007 跑 T002 綠 + `alembic upgrade/downgrade` 驗 0022 對稱 + 既有 anomaly 測試零回歸。

## Phase 3: US2 稀疏 baseline 聰明放寬（P1，常態品質）
- [X] T008 [test][US2] `tests/unit/test_anomaly_evaluate.py`：baseline_total < baseline_min_calls 且比例超標但未達絕對 → 不隔離；達絕對 → 隔離；baseline 充足 → 比例照常。先紅。
- [X] T009 [US2] `evaluate_allocation`：加「`baseline_total < cfg.baseline_min_calls` → 走絕對門檻分支」；比例/絕對/min_calls 皆用 cfg 值。
- [X] T010 [US2] 跑 T008 綠。

## Phase 4: US1 管理員暫停/關閉自動隔離（P1，核心訴求）
- [X] T011 [test][US1] contract：`PUT {auto_quarantine_enabled:false}` → GET 反映、status=disabled、稽核 `anomaly_config_updated`；`PUT {pause_until:未來}` → status=paused。integration：enabled=false 時 `detect_and_quarantine` 掃描但不隔離（造一個平常會隔離的用量）。先紅。
- [X] T012 [US1] `AuditEventType.anomaly_config_updated`（無 migration）。
- [X] T013 [US1] `detect_and_quarantine` 開頭：`effective_enforcing(now)=enabled AND (pause_until is null or <= now)`；不執法時照掃描、寫 `anomaly_detector_run`（`enforced=false`）、跳過 `status=quarantined`。
- [X] T014 [US1] 新建 `src/ai_api/api/anomaly.py`：GET + PUT `/admin/anomaly/config`（部分更新、驗證 422 `invalid_anomaly_config`、稽核）；掛 router（`require_admin_token`）。
- [X] T015 [US1] 跑 T011 綠。

## Phase 5: US4 門檻可調（P3）
- [X] T016 [test][US4] contract：PUT 各門檻持久化 + 生效於 `get_anomaly_config`；非法值（multiplier<1、負數）→ 422。先紅。
- [X] T017 [US4] PUT handler 門檻驗證 + 寫入（與 US1 同 handler，補欄位）。
- [X] T018 [US4] 跑 T016 綠。

## Phase 6: 前端（US1 設定頁 + US3 一鍵解除）
- [X] T019 [US1/US4] `frontend/src/routes/admin/anomaly.tsx`（或整併進既有 admin 頁）：顯示狀態（啟用/停用/暫停到期）+ 開關 + 暫停到期選擇 + 門檻輸入 + 儲存（PUT）；`anomaly-config.test.tsx` 測渲染/切換/儲存。
- [X] T020 [US3] 首頁隔離提示（`home.tsx`/dashboard 的 `quarantinedCount`）加「解除」直達（呼叫既有 `unquarantine` 端點）+ 導向已隔離清單；測試斷言一鍵解除。
- [X] T021 前端全套 `vitest run` + `tsc --noEmit; echo $?` + `npm run build` 綠。

## Phase 7: Polish & 上線
- [X] T022 全套零回歸：`pytest tests/ -q` + `ruff check .` + `uv run mypy src/ai_api`；前端全套 vitest + tsc(退出碼) + build。
- [X] T023 PR + squash-merge（CI 綠）。前後端兩 image bump；**有 migration → `--set migrationJob.enabled=true`**；部署 **ccsh + tew**（`--reuse-values` + 顯式 `--set` 新 chart 值若有）。驗 `alembic current=0022`、`GET /admin/anomaly/config`。
- [ ] T024 真機驗收（明天研習前）：admin 介面「暫停自動隔離到 <研習結束>」→ 確認研習期間不隔離；到期自動恢復；首頁一鍵解除可用。
- [X] T025 知識同步：vision 階段標「異常偵測 v2 ✅」；experience 蒸餾「異常偵測要可被 admin 自助暫停 + 稀疏 baseline 走絕對門檻（比例規則需足量樣本才可信）」。

## Dependencies
- Foundational（T002–T007）阻斷全部。US2（T008–10）、US1（T011–15）皆依賴它；US4（T016–18）疊在 US1 的 PUT handler。前端（T019–21）依賴後端端點。Polish 最後。
- **MVP＝Foundational + US1 + US2**（管理員可暫停 + 常態不誤判）——明天研習的核心。US3/US4 加分。
