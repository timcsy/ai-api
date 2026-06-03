---
description: "Tasks for Phase 13 — admin email notifications"
---

# 任務清單：管理員 Email 通知

**輸入文件**：`/specs/022-admin-email-notifications/` 下的
[plan.md](./plan.md) / [spec.md](./spec.md) / [research.md](./research.md) /
[data-model.md](./data-model.md) / [contracts/](./contracts/) / [quickstart.md](./quickstart.md)

**測試**：本專案憲章規定 TDD 為不可妥協原則 → **所有任務中的測試必須先寫且先失敗（Red）才能寫實作（Green）**

**組織原則**：依使用者故事分組，使每個故事可獨立實作與測試。

## 格式說明

每筆任務格式：`- [ ] TaskID [P?] [Story?] 描述 (含絕對檔案路徑)`

- **[P]**：可並行（不同檔案、無未完成依賴）
- **[Story]**：屬於哪個 user story（US1/US2/US3/US4/US5）；Setup / Foundational / Polish 階段不加 Story 標
- 所有路徑為 repo 根的相對路徑

## 路徑慣例

- 後端：`src/ai_api/`
- 前端：`frontend/src/`
- 測試：`tests/`（依層分 `contract/` `integration/` `unit/`）

---

## Phase 1：Setup（共享基礎）

**目的**：依賴安裝與設定變數

- [X] T001 在 `pyproject.toml` 新增依賴 `aiosmtplib>=3.0,<4` 與 dev 依賴 `aiosmtpd>=1.4,<2`，跑 `uv lock` 確認 lockfile 更新且 CI 可解析
- [X] T002 [P] 在 `src/ai_api/config.py` `Settings` 加 `notify_event_types_override: list[str] = Field(default=[], alias="NOTIFY_EVENT_TYPES_OVERRIDE")`，允許 operator 以 env 覆寫訂閱清單
- [X] T003 [P] 在 `CLAUDE.md` Active Technologies 段加 `aiosmtplib`、`aiosmtpd`（已由 update-agent-context.sh 處理；若 commit diff 顯示缺漏則手動補）

---

## Phase 2：Foundational（阻斷性前置）

**⚠️ 沒做完任何 US 都不能開始。**

- [X] T004 在 `src/ai_api/models/audit.py` `AuditEventType` enum 加入三個新值：`responses_upstream_error_burst`、`provider_credential_auth_failed`、`allocation_daily_cap_exceeded`（既有 enum 為 `native_enum=False` 存 VARCHAR，無需 migration）
- [X] T005 [P] 新增 `src/ai_api/models/notification.py`：`NotificationConfig` / `NotificationDedupBucket` / `NotificationRecord` ORM models，依 data-model.md 定義欄位、constraints、index、FK（CASCADE SET NULL 策略）
- [X] T006 在 `src/ai_api/models/__init__.py` 註冊上述三個 model 並 re-export
- [X] T007 在 `src/ai_api/alembic/versions/` 新增 `0014_admin_notifications.py` migration：建立三張新表（含 `CHECK (id = 1)` enforce singleton、index、FK），revises 上一版 `0013_responses_api`；於 `tests/integration/` 下執行 `pytest -k alembic` 確認 upgrade/downgrade 通過
- [X] T008 [P] 新增 `src/ai_api/services/notifier.py`：`Notifier` ABC + `NotificationEvent` + `NotificationResult` dataclass 骨架（**僅介面，無實作**）；依 `contracts/notifier-interface.md`

**Checkpoint**：基礎就緒，可平行進入 US1-US5 phases。

---

## Phase 3：US1 — admin 設定通知管道並驗證可用（P1）🎯 MVP 第一塊

**目標**：admin 能在 `/admin/notifications` 頁完成 SMTP 設定 + 收件人 + 即時發測試信驗證。

**獨立驗收**：依 `quickstart.md` 情境 1 與 2 端到端可跑通。

### Tests First (Red)

- [X] T009 [US1] 新增 `tests/contract/test_admin_notifications.py::test_get_config_returns_204_when_unset`：未設定時 `GET /admin/notifications/config` 回 204
- [X] T010 [P] [US1] 同檔加 `test_put_config_persists_and_returns_masked`：`PUT` 完整 payload 回 200、回應含 `smtp_password_fingerprint`、不含明文、`status=pending_test`
- [X] T011 [P] [US1] 同檔加 `test_put_config_rejects_invalid_port`、`test_put_config_rejects_malformed_recipients`、`test_put_config_rejects_empty_smtp_host` 三條驗證錯誤情境（皆回 400 + 標準 error envelope）
- [X] T012 [P] [US1] 同檔加 `test_delete_config_clears_state`：DELETE 後 GET 回 204、且後續 `notification_record(outcome=skipped_disabled)` 仍可寫
- [X] T013 [P] [US1] 同檔加 `test_test_send_with_one_off_recipient`：FR-007 要求；POST `/admin/notifications/test-send` body 含 `test_recipient`，回 200 + `outcome=success`；驗證**儲存的 recipients 清單不被使用**（mock 真實 SMTP 端只看到 `test_recipient`）
- [X] T014 [P] [US1] 同檔加 `test_test_send_returns_actionable_error_on_auth_failure`：用錯誤密碼，回 200 + `outcome=send_failed_auth`、`smtp_response_code=535`、`message` 中文可讀
- [X] T015 [P] [US1] 新增 `tests/integration/test_notification_smtp.py::test_aiosmtpd_starttls_round_trip`：起 `aiosmtpd` 內部測試 server（port 1587，STARTTLS），執行真實 SMTP 握手 + 寄送、收到 message 驗 subject/body 正確
- [X] T016 [P] [US1] 同檔加 `test_aiosmtpd_tls_465_round_trip`：同上但 port 465 直接 TLS
- [X] T017 [P] [US1] 新增 `tests/unit/test_notifier_email.py::test_smtp_exception_classification`：對 `aiosmtplib.SMTPAuthenticationError`、`SMTPConnectError`、`SMTPSenderRefused`、`OSError` 分別驗證 mapping 到正確 `outcome` 值
- [X] T018 [US1] 跑 `uv run pytest tests/contract/test_admin_notifications.py tests/integration/test_notification_smtp.py tests/unit/test_notifier_email.py` 確認 **全 Red**（測試先失敗，符合 TDD）

### Implementation (Green)

- [X] T019 [US1] 在 `src/ai_api/services/notifier.py` 實作 `EmailNotifier.test_send()`：使用 `aiosmtplib` 純 async client、STARTTLS 587 / TLS 465 policy、connect 15s / command 30s timeout；依 `contracts/notifier-interface.md` 失敗分類；落 `notification_record(outcome=test_*)`；mask email log 欄位
- [X] T020 [US1] 新增 `src/ai_api/services/notifications.py::NotificationConfigService`：CRUD（get/save/delete）+ Fernet 加密 password（沿用 `PROVIDER_KEY_ENC_KEY`）+ status 狀態機（`pending_test` / `verified` / `credentials_invalid`）+ decrypt 失敗時 catch `InvalidToken` 回 `credentials_invalid`
- [X] T021 [US1] 新增 `src/ai_api/api/admin_notifications.py`：FastAPI router with 4 endpoints（GET/PUT/DELETE `/config`、POST `/test-send`）、Pydantic schemas 對齊 `contracts/admin-notifications.openapi.yaml`、`require_admin_token` dependency、標準 error envelope
- [X] T022 [US1] 在 `src/ai_api/main.py` import 新 router 並 `app.include_router(admin_notifications.router, prefix="/admin/notifications", tags=["admin-notifications"])`
- [X] T023 [US1] 跑 T009–T017 測試確認 **全 Green**；補修任何失敗
- [X] T024 [P] [US1] 新增 `frontend/src/routes/admin/notifications.tsx`：SMTP 設定表單（host/port/username/password/sender/recipients）+ status badge + 「發測試信」按鈕（彈出 input 一次性測試 email）+ 結果 toast；使用 TanStack Query + shadcn/ui Form 元件
- [X] T025 [P] [US1] 在 `frontend/src/components/app-shell.tsx` 的 `ADMIN_SUBNAV` 加入 `{ to: "/admin/notifications", label: "通知" }`，使用 lucide-react `Bell` icon（為未來 web push badge 預留位置）
- [X] T026 [P] [US1] 在 `frontend/src/App.tsx` 註冊 `/admin/notifications` route
- [X] T027 [US1] 跑 `npm --prefix frontend run lint` + `npm --prefix frontend run build` 確認前端編譯通過、無 lint 警告
- [X] T028 [US1] 跑 quickstart.md 情境 1 + 情境 2 端到端煙霧測試（可在本機 docker-compose + Mailpit 替代真 Gmail），確認 UI 操作流程符合驗收條件

---

## Phase 4：US2 — 分配自動隔離觸發 email（P1）

**目標**：anomaly detector 隔離分配時，30 秒內 admin recipients 都收到含完整資訊的 email。

**獨立驗收**：依 `quickstart.md` 情境 3。

### Tests First (Red)

- [X] T029 [US2] 新增 `tests/integration/test_notification_hooks.py::test_allocation_quarantined_event_sends_email`：seed config + recipients、觸發 `audit.record(event_type=allocation_quarantined, target_id=..., details={"reason":"ratio","last_hour_calls":1100,"baseline_per_hour":100,...})`，驗證：a) 30 秒內 `aiosmtpd` 收到 message；b) 每 recipient 都收一封；c) subject 含 `[AI API] 分配自動隔離`；d) body 含完整 FR-014 欄位（分配 ID、display_name、reason 含具體數字、時間 UTC+8、admin 頁連結）
- [X] T030 [P] [US2] 同檔加 `test_quarantine_event_when_smtp_unset_skips_silently`：config 不存在時，audit event 仍正常落 DB、`notification_record(outcome=skipped_disabled)` 被建立、無 ERROR log（FR-005、SC-004）
- [X] T031 [P] [US2] 同檔加 `test_one_recipient_failure_does_not_block_others`：一位 recipient 故意被 SMTP server reject、另一位成功；驗證 `notification_record.per_recipient_status` 兩位 status 都記、`outcome=sent`（至少一位成功）（FR-021）
- [X] T032 [P] [US2] 同檔加 `test_credentials_invalid_status_blocks_send`：config.status=credentials_invalid 時，event 觸發後 record 落 `outcome=skipped_disabled`、無 SMTP 連線嘗試
- [X] T033 [P] [US2] 同檔加 `test_email_send_failure_does_not_break_audit`：故意讓 SMTP 連線超時，驗證 audit_events 仍正常寫入、`notification_record(outcome=send_failed_connect)`、`error_message` 含 actionable detail（FR-025）
- [X] T034 [US2] 跑 T029–T033 確認 **全 Red**

### Implementation (Green)

- [X] T035 [US2] 在 `src/ai_api/services/notifier.py` 實作 `EmailNotifier.notify()` 核心：讀 config（無/disabled/invalid 即落 skipped 並 return）、組 subject/body、寄信、落 record；**此版尚不含 dedup（US4 加）** — 但保留 hook 位置（pass-through）；TLS / timeout / error classification 沿用 T019 內部 helper
- [X] T036 [US2] 在 `src/ai_api/services/notifier.py` 加 `_render_quarantine_email(event: NotificationEvent) -> tuple[str, str]`：subject + body template；body 中文範本依 research.md R6
- [X] T037 [US2] 在 `src/ai_api/auth/audit.py`（或 `services/audit.py` 視既有結構）`record()` 完成後加 hook：若 `event_type ∈ NOTIFY_EVENT_TYPES`（讀 `settings.notify_event_types_override` 或預設清單），使用 `asyncio.create_task(notifier.notify(...))`；hook 整段包 try/except 不向上 raise（FR-025）
- [X] T038 [P] [US2] 在 `src/ai_api/services/notifier.py` 落結構化 JSON log 每筆寄送（含 `event_type`、`audit_event_id`、`recipients_count`、`outcome`、`smtp_response_code`、`latency_ms`、email partial mask）；對應 `contracts/notifier-interface.md` logging 契約
- [X] T039 [US2] 跑 T029–T033 確認 **全 Green**

---

## Phase 5：US3 — 其他 3 種事件型別觸發 email（P1）

**目標**：upstream burst、provider credential 失效、daily cap 三類事件同樣觸發 email。

**獨立驗收**：依 `quickstart.md` 情境 5（依此類推 US3.b、US3.c）。

### Tests First (Red)

- [X] T040 [US3] 在 `tests/integration/test_notification_hooks.py` 加 `test_upstream_error_burst_triggers_notification`：模擬 5 分鐘內 10 筆 `outcome=upstream_error` 的 `call_records`、確認 detector 觸發 `responses_upstream_error_burst` audit event、確認對應 email 寄出含 provider 名稱 + 失敗筆數 + 最近 model
- [X] T041 [P] [US3] 同檔加 `test_provider_credential_auth_failed_triggers_notification`：mock proxy 對 upstream 收到 401/403、發 `provider_credential_auth_failed` audit event、驗證對應 email
- [X] T042 [P] [US3] 同檔加 `test_daily_cap_exceeded_event_template_renders`：直接觸發 `allocation_daily_cap_exceeded` audit event（即使 Phase 16 尚未上線此事件來源），驗證 email 內容正確 — 確保模板就位以待 Phase 16 整合
- [X] T043 [US3] 跑 T040–T042 確認 **全 Red**

### Implementation (Green)

- [X] T044 [US3] 新增 `src/ai_api/services/upstream_burst_detector.py`：sliding 5-min window 計數 `outcome=upstream_error` `call_records`，跨過門檻（預設 10，env `UPSTREAM_BURST_THRESHOLD` 可調）即觸發 `audit.record(responses_upstream_error_burst)`；以 helm cronjob（每分鐘）執行類似 anomaly detector pattern
- [X] T045 [P] [US3] 在 `src/ai_api/proxy/responses.py` 與 `src/ai_api/proxy/router.py` 上游回 401/403 的 catch 點加 `audit.record(provider_credential_auth_failed, target_type="provider_credential", target_id=<credential_id>, ...)`
- [X] T046 [P] [US3] 在 `src/ai_api/services/notifier.py` 加 3 個 template renderer：`_render_upstream_burst_email`、`_render_credential_invalid_email`、`_render_daily_cap_email`；各依 FR-014 含 subject ≤50 字、body 中文白話 + admin 頁連結
- [X] T047 [P] [US3] 新增 `deploy/helm/ai-api/templates/upstream-burst-cronjob.yaml`（mirror anomaly-cronjob.yaml；schedule `* * * * *`）
- [X] T048 [US3] 跑 T040–T042 確認 **全 Green**

---

## Phase 6：US4 — 5 分鐘窗去重避免事件爆量灌爆信箱（P2）

**目標**：同事件型別在 5 分鐘窗內，無論底層觸發多少次都僅寄出 1 封 email；其餘事件落 `outcome=suppressed`。

**獨立驗收**：依 `quickstart.md` 情境 4。

### Tests First (Red)

- [ ] T049 [US4] 新增 `tests/integration/test_notification_dedup.py::test_burst_within_5min_window_sends_once`：50 筆同型別事件在 4 分鐘內依序觸發，驗證：a) `aiosmtpd` 只收到 1 封 message；b) `notification_dedup_bucket` 一筆，`event_count=50`；c) 49 筆 `notification_record(outcome=suppressed)` 皆指向同一 `dedup_bucket_id`；d) 1 筆 `notification_record(outcome=sent)` 為 bucket `primary_record_id`
- [ ] T050 [P] [US4] 同檔加 `test_different_event_types_send_separately`：5 分鐘內 quarantine + upstream burst 兩種型別各 1 筆，驗證寄出 2 封 message（FR-020）
- [ ] T051 [P] [US4] 同檔加 `test_window_expires_starts_new_bucket`：第 6 分鐘再觸發同型別 1 筆，驗證寄出第 2 封 + `notification_dedup_bucket` 新增第 2 筆
- [ ] T052 [P] [US4] 同檔加 `test_concurrent_same_type_events_only_send_once`：用 asyncio.gather 並行觸發 5 筆同型別事件（模擬 multi-replica scenario）；驗證 DB row lock 正確、僅 1 封 message 寄出（其餘 4 筆 suppressed）
- [ ] T053 [US4] 跑 T049–T052 確認 **全 Red**

### Implementation (Green)

- [ ] T054 [US4] 在 `src/ai_api/services/notifier.py::EmailNotifier.notify()` 加 dedup gate：在寄信前先 query `notification_dedup_bucket WHERE event_type=:t AND window_end > :now FOR UPDATE`；命中即 `event_count += 1`、落 `notification_record(outcome=suppressed, dedup_bucket_id=...)`、return；未命中即 insert bucket（`window_end=now+5min`）、寄信、落 record（`primary_record_id` 反向 update bucket）
- [ ] T055 [US4] 跑 T049–T052 確認 **全 Green**

---

## Phase 7：US5 — admin 檢視通知歷史（P3）

**目標**：admin 在 `/admin/notifications` 同頁看得到最近 N 筆通知紀錄 + 被去重合併的摺疊群組。

**獨立驗收**：依 `quickstart.md` 情境 8。

### Tests First (Red)

- [ ] T056 [US5] 在 `tests/contract/test_admin_notifications.py` 加 `test_list_history_returns_paginated_records`：seed 60 筆 records、`GET /admin/notifications/history?limit=20` 回 20 筆 + `next_cursor`，第二次帶 cursor 回下 20 筆
- [ ] T057 [P] [US5] 同檔加 `test_history_filters_by_event_type`：`?event_type=allocation_quarantined` 只回對應紀錄
- [ ] T058 [P] [US5] 同檔加 `test_history_filters_by_outcome`：`?outcome=send_failed_auth` 只回失敗紀錄
- [ ] T059 [P] [US5] 同檔加 `test_primary_record_surfaces_bucket_count`：被 49 筆 suppressed 合併的 primary record 回應含 `bucket_event_count=50`
- [ ] T060 [US5] 跑 T056–T059 確認 **全 Red**

### Implementation (Green)

- [ ] T061 [US5] 在 `src/ai_api/services/notifications.py` 加 `list_history(limit, cursor, event_type, outcome) -> tuple[list[NotificationRecord], next_cursor]`：cursor 用 `(created_at, id)` 組合 opaque base64；`bucket_event_count` 透過 LEFT JOIN `notification_dedup_bucket` 取得（僅 primary record 上）
- [ ] T062 [US5] 在 `src/ai_api/api/admin_notifications.py` 加 `GET /history` endpoint，schema 對齊 `contracts/admin-notifications.openapi.yaml::NotificationHistoryResponse`
- [ ] T063 [P] [US5] 在 `frontend/src/routes/admin/notifications.tsx` 增加歷史區塊：列出最近 50 筆、`bucket_event_count > 1` 的 primary record 顯示「N 筆事件合併入此封」可展開列出 suppressed 子項；篩選器（event_type 下拉、outcome 下拉）；游標分頁
- [ ] T064 [P] [US5] 在 `frontend/src/routes/admin/notifications.tsx` 為失敗紀錄顯示 actionable 訊息（從 `error_message` + `per_recipient_status` 組合白話文）
- [ ] T065 [US5] 跑 T056–T059 + frontend lint/build 確認 **全 Green**

---

## Phase 8：Polish 與跨領域

- [ ] T066 新增 `deploy/helm/ai-api/templates/notification-cleanup-cronjob.yaml`：mirror `storedResponseCleanup` pattern；schedule `30 3 * * *` UTC；`DELETE FROM notification_record WHERE created_at < now() - interval '30 days'` 與 `DELETE FROM notification_dedup_bucket WHERE window_end < now() - interval '30 days'`
- [ ] T067 在 `deploy/helm/ai-api/values.yaml` 加 `notificationCleanup: {enabled: true, schedule: "30 3 * * *"}` 與 `upstreamBurstDetector: {enabled: true, schedule: "* * * * *", thresholdCalls: 10, windowMinutes: 5}`
- [ ] T068 [P] 新增 `knowledge/design/admin-notifications.md`：摘要 research.md 13 條決策 + plan.md 結構 + 主要圖示（migration 表關係 + audit hook 流程）；連結回本 spec / plan / research
- [ ] T069 [P] 在 `knowledge/experience.md` 預留位置（先不寫內容，留待實作中遇到值得 distill 的教訓再加）
- [ ] T070 [P] 更新 `knowledge/vision.md` 階段 13 條目（實作完成日期填入後改為 ✅；列出實際交付 + 連結 `history/completed-phases-detail.md`）
- [ ] T071 [P] 在 `knowledge/history/completed-phases-detail.md` 末追加「## 階段 13：管理員 Email 通知」完整詳情條目（依現有 Phase 11/12 格式）
- [ ] T072 在 `docs/deployment.md`（若存在；不存在則新增）加「通知 SMTP 設定章節」：Gmail App Password 申請步驟 + helm value `notifyEventTypesOverride` 用法 + 常見錯誤對照表
- [ ] T073 跑 `uv run pytest tests/` 全測試套件確認既有測試零退化；以 `pytest --co -q` 確認新增測試 ≥ 24 筆（T009–T017, T029–T033, T040–T042, T049–T052, T056–T059）
- [ ] T074 跑 `uv run ruff check . && uv run mypy src/` 確認 lint + 型別零警告
- [ ] T075 跑 `npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build` 確認前端零警告
- [ ] T076 端到端煙霧：在 staging（或本機 docker-compose + Mailpit）跑 `quickstart.md` 全 8 情境
- [ ] T077 [P] commit + push + 等 image build；helm upgrade 至 ai-ccsh ns；live cluster 跑 quickstart 情境 1 + 3 真實 SMTP 驗證（用 Gmail App Password + 真 admin 信箱）
- [ ] T078 收尾：將 spec / plan / tasks 中提到的「實作後待辦」（vision 條目改 ✅、history 補上等）逐項確認完成

---

## 依賴與順序

```text
Phase 1 (Setup)
   ↓
Phase 2 (Foundational)
   ↓
┌──────────────────────────────────────────────┐
│ Phase 3 (US1)                                │
│   ↓                                          │
│ Phase 4 (US2) ─── depends on US1 (config + EmailNotifier shell)
│   ↓                                          │
│ Phase 5 (US3) ─── depends on US2 (notify pipeline)
│   ↓                                          │
│ Phase 6 (US4) ─── modifies notify() to add dedup gate
│                                              │
│ Phase 7 (US5) ─── depends only on US1 (data model)
│                   可與 US2/US3/US4 平行
└──────────────────────────────────────────────┘
   ↓
Phase 8 (Polish & Cross-cutting)
```

**MVP 建議**：US1 + US2 完成即可上線首個有價值版本（admin 可設定通知 + 接收最重要的隔離事件通知）。US3/US4/US5 為陸續增益。

**[P] 並行機會**：
- Phase 3 內 T010/T011/T012/T013/T014/T015/T016/T017 全部 [P]（不同測試函式 / 不同檔案）
- Phase 4 內 T030/T031/T032/T033 全部 [P]
- Phase 5 內 T041/T042 + T045/T046/T047 [P]
- Phase 6 內 T050/T051/T052 [P]
- Phase 7 內 T057/T058/T059 + T063/T064 [P]
- Phase 8 大部分 [P]（不同檔案）

---

## 任務統計

| Phase | 任務數 | 含測試 |
|-------|------:|------:|
| 1 Setup | 3 | 0 |
| 2 Foundational | 5 | 0 |
| 3 US1（P1，MVP 第一塊） | 20 | 10 |
| 4 US2（P1） | 11 | 5 |
| 5 US3（P1） | 9 | 3 |
| 6 US4（P2） | 7 | 4 |
| 7 US5（P3） | 10 | 4 |
| 8 Polish | 13 | 0（驗證跑既有測試） |
| **總計** | **78** | **26** |

---

## 格式檢核

- ✅ 所有任務皆以 `- [ ] T###` 開頭、含 ID、含描述、含絕對檔案路徑
- ✅ Setup / Foundational / Polish 階段無 Story 標
- ✅ US1–US5 階段任務皆含 `[US#]` 標
- ✅ 可並行任務皆標 `[P]`
- ✅ 每一 user story 階段內：**Tests First → 跑測試 Red → Implementation → 跑測試 Green** 順序明確（符合憲章 TDD 不可妥協原則）

---

## 下一步

跑 `/speckit.implement` 開始實作（或手動按 phase 順序執行）。

> **重要**：實作期間每完成一筆即將該 `- [ ]` 改為 `- [X]`；跨 phase 邊界前確認該階段所有測試已 Green。
