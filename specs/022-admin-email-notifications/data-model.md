# Phase 1：資料模型

本檔定義本功能新增的三張資料表結構、關聯與狀態轉換。所有時間欄位採 `DateTime(timezone=True)`、
Python 端一律 `datetime.now(UTC)`（沿用既有專案規範）。

---

## 概覽

```text
notification_config (1 row max)
    │
    │ (configures channel/recipients for events)
    │
    ↓ (decoupled — config 不引用 record)

notification_dedup_bucket ─── (event_type unique within active window)
    │
    │ (one bucket per (event_type, 5-min window))
    │
    ↓

notification_record (many)
    └─ (each event triggers one record; outcome 包含 sent/suppressed/skipped_disabled/send_failed_*)
```

---

## 1. `notification_config`

通知設定（singleton，整個部署一列）。

| 欄位 | 型別 | Null | 預設 | 說明 |
|------|------|------|------|------|
| `id` | `INTEGER` | NO | `1` | 永遠 = 1（CHECK constraint enforce singleton） |
| `smtp_host` | `VARCHAR(255)` | NO | — | SMTP server hostname（e.g. `smtp.gmail.com`） |
| `smtp_port` | `INTEGER` | NO | `587` | SMTP server port |
| `smtp_username` | `VARCHAR(255)` | NO | — | SMTP 認證帳號 |
| `smtp_password_encrypted` | `TEXT` | NO | — | Fernet 加密後的密碼（沿用 `PROVIDER_KEY_ENC_KEY`） |
| `sender_email` | `VARCHAR(320)` | NO | — | `From` 標頭中的 email address |
| `sender_name` | `VARCHAR(128)` | NO | `'AI API Manager'` | `From` 標頭中的 display name |
| `recipients` | `JSON` | NO | `'[]'` | 收件人 email list；e.g. `["admin@school.edu.tw", "ops@school.edu.tw"]` |
| `enabled` | `BOOLEAN` | NO | `true` | admin 可在 UI 切換而不刪設定 |
| `status` | `VARCHAR(32)` | NO | `'pending_test'` | `pending_test` / `verified` / `credentials_invalid` |
| `last_test_at` | `TIMESTAMP TZ` | YES | NULL | 最近一次測試寄送時間 |
| `last_test_outcome` | `VARCHAR(32)` | YES | NULL | 最近測試結果（`success` / `auth_failed` / `connect_failed` / etc.） |
| `last_test_error` | `TEXT` | YES | NULL | 最近測試失敗訊息（成功時為 NULL） |
| `created_at` | `TIMESTAMP TZ` | NO | `now()` | |
| `updated_at` | `TIMESTAMP TZ` | NO | `now()` | |
| `created_by` | `VARCHAR(64)` | NO | — | 建立者 admin email |

**Constraints**:
- `CHECK (id = 1)`（singleton enforce）
- `smtp_port BETWEEN 1 AND 65535`
- `status IN ('pending_test', 'verified', 'credentials_invalid')`

**狀態轉換**：

```
（無設定）
    │
    │ admin POST/PUT /admin/notifications/config
    ↓
pending_test ─── admin 按「發測試信」成功 ───► verified
    │                                              │
    │                                              │ Fernet decrypt failed at runtime
    │                                              ↓
    └────── decrypt 失敗 ───────────────────► credentials_invalid
                                                   │
                                                   │ admin 重新存設定
                                                   ↓
                                              pending_test
```

**驗證規則**（service 層）：
- `smtp_host` 非空、不含 whitespace
- `smtp_port` ∈ [1, 65535]
- `recipients` 每一元素為合法 email format（regex 或 stdlib `email.utils.parseaddr`）
- `recipients` 至少 1 個（empty list = 通知停用，UI 警示但允許）
- `sender_email` 為合法 email format

---

## 2. `notification_dedup_bucket`

去重時間窗。每個 `event_type` 在「事件爆發起算 5 分鐘」內共享一個 bucket。

| 欄位 | 型別 | Null | 預設 | 說明 |
|------|------|------|------|------|
| `id` | `VARCHAR(26)` | NO | — | ULID |
| `event_type` | `VARCHAR(64)` | NO | — | 對應 audit `AuditEventType` 值 |
| `window_start` | `TIMESTAMP TZ` | NO | `now()` | 第一筆事件時間（窗開始） |
| `window_end` | `TIMESTAMP TZ` | NO | `window_start + 5min` | 窗結束時間（不含） |
| `event_count` | `INTEGER` | NO | `1` | 累計事件數（含已 send + suppressed） |
| `primary_record_id` | `VARCHAR(26)` | NO | — | 觸發此 bucket 的「第一筆 record」FK（即發出 email 那一筆） |
| `last_event_at` | `TIMESTAMP TZ` | NO | `now()` | 最近一次同型別事件時間 |

**Constraints**:
- PK `id`
- INDEX `idx_dedup_event_window` ON `(event_type, window_end)` — 用於「查當前是否有 active window」
- FK `primary_record_id → notification_record(id)`（CASCADE on delete = SET NULL，避免歷史
  GC 連動異常）

**生命週期**：
- 新建：第一筆事件 → 建 bucket、寄信、建立關聯 record
- 同型別後續事件 → `event_count += 1`、`last_event_at = now()`、新增 record（`outcome=suppressed`）
- 窗結束（`window_end < now()`）：bucket 不再被「同型別新事件」匹配（→ 下一筆觸發建立新 bucket）
- 清理：與 `notification_record` 同 cronjob，30 天後刪 bucket（保留歷史可溯）

---

## 3. `notification_record`

每筆事件的「曾嘗試通知」紀錄；admin UI 歷史列表的資料來源。

| 欄位 | 型別 | Null | 預設 | 說明 |
|------|------|------|------|------|
| `id` | `VARCHAR(26)` | NO | — | ULID |
| `event_type` | `VARCHAR(64)` | NO | — | 對應 `AuditEventType` 值 |
| `audit_event_id` | `VARCHAR(26)` | YES | NULL | 對應 `audit_events.id`（若為事件觸發；測試寄送則為 NULL） |
| `dedup_bucket_id` | `VARCHAR(26)` | YES | NULL | 所屬 bucket（測試寄送無 bucket） |
| `outcome` | `VARCHAR(32)` | NO | — | 詳見下方 enum |
| `recipients` | `JSON` | NO | `'[]'` | 寄送對象 list（snapshot；config 改動不影響歷史） |
| `per_recipient_status` | `JSON` | NO | `'{}'` | `{"alice@example.com": "ok", "bob@example.com": "rejected: mailbox unavailable"}` |
| `subject` | `VARCHAR(256)` | NO | — | 寄出的 subject |
| `body_preview` | `VARCHAR(500)` | NO | — | body 前 500 字（不存全文，省空間） |
| `smtp_response_code` | `INTEGER` | YES | NULL | 全 batch 結束時最終 SMTP 回應碼（多 recipient 時取最差） |
| `error_message` | `TEXT` | YES | NULL | 整體失敗訊息（個別 recipient 錯誤在 `per_recipient_status`） |
| `latency_ms` | `INTEGER` | YES | NULL | 「事件記錄 → SMTP server 回應」全程毫秒（FR-017 SLO 驗證） |
| `created_at` | `TIMESTAMP TZ` | NO | `now()` | |

**`outcome` enum**：
- `sent` — 至少一位 recipient 成功
- `suppressed` — 在現有 dedup window 內，未寄出
- `skipped_disabled` — `notification_config` 不存在或 `enabled=false`
- `skipped_no_recipients` — `recipients` 為空
- `send_failed_auth` — SMTP 認證失敗
- `send_failed_connect` — 無法連線 SMTP server
- `send_failed_sender` — 寄件者被 SMTP server 拒絕
- `send_failed_all_recipients` — 所有 recipients 都被拒
- `send_failed_unknown` — 其他未知失敗
- `test_sent` — 測試寄送成功（recipients 為 admin 即時輸入的一次性 email）
- `test_failed_*` — 測試寄送失敗（對應於上述 `send_failed_*`）

**Constraints**:
- PK `id`
- INDEX `idx_record_created` ON `created_at DESC` — UI 歷史按時間 desc 排序
- INDEX `idx_record_event_type` ON `(event_type, created_at DESC)` — 篩選查詢
- FK `audit_event_id → audit_events.id`（CASCADE on delete = SET NULL）
- FK `dedup_bucket_id → notification_dedup_bucket.id`（CASCADE on delete = SET NULL）

**保留**：30 天，每日 cronjob `DELETE WHERE created_at < now() - interval '30 days'`。

---

## 驗證規則總覽（service 層）

| 規則 | 對應 FR | 實作位置 |
|------|---------|----------|
| singleton config | spec key entity | `NotificationConfigService.save()` |
| password Fernet 加密 | FR-003 | `NotificationConfigService.save()` |
| recipients 為合法 email list | FR-002 | `NotificationConfigService.save()` |
| 寄信失敗不阻斷 audit | FR-025 | `audit.record()` hook 使用 `asyncio.create_task` + 內部 try/except |
| 解密失敗 → status=credentials_invalid | FR-026 | `NotificationConfigService.get()` |
| 同型別 5 min 內 ≤ 1 寄送 | FR-018 | `Notifier.notify()` 查 dedup bucket |
| 30 天歷史保留 | FR-024 | cronjob `notification-cleanup-cronjob.yaml` |

---

## Migration 0014（草稿；最終 alembic 由實作階段產生）

```python
"""admin notifications schema (0014)

Revision ID: 0014_admin_notifications
Revises: 0013_responses_api
Create Date: 2026-06-02
"""
# 新增三張表如上述 schema；index、constraints、FK 一併建立
# 既有表無變更
```

不需要既有表 schema 變更（純新增）。
