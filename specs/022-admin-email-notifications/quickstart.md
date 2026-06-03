# Phase 1：Quickstart — admin email 通知

本檔以**整合測試情境**形式定義 happy path 與關鍵 edge path 的端到端驗收。每條情境
對應 Phase 2（tasks）的一條整合測試。

---

## 前置：環境

- backend pod 已啟動，`PROVIDER_KEY_ENC_KEY` 有效（既有）
- 既有 admin 帳號可登入
- 至少一個現有的 allocation（用於觸發測試事件）

## 情境 1：admin 完成 SMTP 設定並通過測試寄送（US1）

**目標**：驗證 US1 端到端可用——admin 可在 UI 設定 SMTP + 即時發測試信驗證。

**步驟**：

1. admin 開 `https://<host>/admin/notifications`
   - 預期：頁面載入；首次進入時，「目前狀態」顯示「未設定（通知停用）」
2. admin 填表：
   - SMTP host: `smtp.gmail.com`
   - SMTP port: `587`
   - 帳號: `ai-api-bot@school.edu.tw`
   - 密碼: `<gmail-app-password>`（admin 預先在 Google 帳號中產的 App Password）
   - 寄件者 email / 顯示名稱
   - recipients：`[admin@school.edu.tw, ops@school.edu.tw]`
   - 按「儲存設定」
   - **預期**：API `PUT /admin/notifications/config` 回 200；密碼 Fernet 加密落 DB；狀態
     變 `pending_test`；UI 顯示「設定已儲存，請發測試信驗證」
3. admin 在「發測試信」區塊填 `test_recipient = tim@school.edu.tw`，按發送
   - **預期**：API `POST /admin/notifications/test-send` 回 200 with `outcome=success`；
     UI 顯示「測試信已寄出至 tim@school.edu.tw，30 秒內應該收到」
   - **預期**：tim 信箱於 30 秒內收到信，subject = `[AI API] 測試通知`、body 含本平台
     URL 與「這是測試信」標示
4. admin 重新整理頁面
   - **預期**：設定持久化；密碼欄位顯示 fingerprint 而非明文；狀態變 `verified`；
     `last_test_at` 與 `last_test_outcome=success` 顯示在 UI

**驗收**：
- ✅ `notification_config` row 存在（id=1）；`smtp_password_encrypted` 為密文
- ✅ `notification_record` 多一筆 `outcome=test_sent`，`recipients=[tim@school.edu.tw]`
- ✅ tim 收到信，內容符合範本

---

## 情境 2：admin 寄錯密碼，UI 顯示 actionable 錯誤（US1 邊界）

**步驟**：

1. admin 在表單填錯 SMTP password，存
2. admin 按「發測試信」
   - **預期**：API 回 200，body `outcome=send_failed_auth`，`message` 含「authentication
     failed: invalid username or password」；`smtp_response_code=535`
   - **預期**：UI 紅色提示框顯示該訊息；30 秒內可重試
   - **預期**：`notification_record` 多一筆 `outcome=test_failed_auth`
3. admin 改正密碼重新存、再測
   - **預期**：第二次測試成功；UI 反映成功

---

## 情境 3：分配被自動隔離，admin 收到 email 內含完整資訊（US2）

**前置**：情境 1 已完成（`notification_config.status=verified`、recipients 有 2 位）。

**步驟**：

1. 觸發 anomaly detector 對某分配 `alloc_abc` 做自動隔離（測試 fixture 或：用測試帳號
   實際送 1100 calls 在 1 小時內，baseline 100/hr）
2. 異常偵測器寫入 `audit_events(event_type='allocation_quarantined', target_id='alloc_abc', ...)`
3. **預期**（30 秒內，並行）：
   - admin@school.edu.tw 收到一封信
   - ops@school.edu.tw 收到一封信
   - 信件 subject：`[AI API] 分配自動隔離 — alloc abc12345`
   - 信件 body 含：
     - 分配 ID（前 8 碼縮寫）+ display_name（如「小明的 GPT-4o」）
     - 觸發原因（「過去 1 小時 1100 calls，baseline 100/hr，11× 突增」）
     - 時間（UTC+8 格式）
     - 連結到 `https://<host>/admin/observability/allocations`
   - `notification_record` 多一筆 `outcome=sent`，`recipients=[admin@..., ops@...]`，
     `per_recipient_status={"admin@school.edu.tw":"ok","ops@school.edu.tw":"ok"}`
   - `notification_dedup_bucket` 新增一筆，`event_type=allocation_quarantined`，
     `window_end=now+5min`，`event_count=1`，`primary_record_id` 指向上述 record

**驗收**：兩位 recipient 都收信；DB 紀錄正確；latency_ms ≤ 30000。

---

## 情境 4：incident 爆量，去重視窗只寄一封（US4）

**前置**：情境 3 已完成。

**步驟**：

1. 在情境 3 的隔離事件後 4 分鐘內，再觸發 49 次相同 `event_type=allocation_quarantined`
   事件（不同 allocation_id，但 event_type 相同）
2. **預期**：
   - 49 筆事件**不**寄出新 email；admin@/ops@ 共收到 1 封信（即情境 3 那封）
   - `notification_dedup_bucket.event_count` = 50（情境 3 那一筆 + 49 筆新）
   - 49 筆新 `notification_record` 落 `outcome=suppressed`，皆指向同一個 dedup_bucket_id
3. 經過第 6 分鐘（窗已過期），再觸發 1 次 `allocation_quarantined`
   - **預期**：寄出新一封 email；`notification_dedup_bucket` 新增第二筆 bucket
   - admin@/ops@ 收到第二封信

**驗收**：
- ✅ 整段 6 分鐘期間，admin@/ops@ 各收到正好 2 封信
- ✅ DB bucket 數 = 2、record 數 = 51（情境 3 的 1 筆 sent + 49 筆 suppressed + 1 筆 sent）
- ✅ UI 歷史頁顯示「49 筆事件合併入此封」對情境 3 的 primary record

---

## 情境 5：上游 provider 連續失敗觸發通知（US3.a）

**前置**：情境 1 已完成。

**步驟**：

1. 模擬上游 AI provider 持續回 5xx — 5 分鐘內累計 10 筆 `upstream_error` audit events
2. 第 10 筆觸發 detector emit `responses_upstream_error_burst` audit event
3. **預期**：30 秒內 admin@/ops@ 收信，subject 含「upstream 連續失敗」，body 列出影響的
   provider 名稱、5 分鐘內失敗筆數、最近一筆 model

**驗收**：record 表多一筆 `event_type=responses_upstream_error_burst, outcome=sent`。

---

## 情境 6：未設定 SMTP，事件發生時平台不噴錯（FR-005、SC-004）

**前置**：先呼叫 `DELETE /admin/notifications/config` 清除設定（或全新環境）。

**步驟**：

1. 觸發一次 `allocation_quarantined` audit event
2. **預期**：
   - audit event 正常落 DB
   - `notification_record` 多一筆 `outcome=skipped_disabled`
   - 無 ERROR log
   - 無 email 寄出
   - 所有 admin 與使用者 API 正常運作

**驗收**：`/admin/notifications` 頁顯示「通知未設定（停用中）」；其他平台功能不受影響。

---

## 情境 7：密碼解密失敗，UI 顯示「需要重新輸入」（FR-026）

**步驟**：

1. 故意輪替 `PROVIDER_KEY_ENC_KEY` 至錯誤值並重啟 backend
2. admin 開 `/admin/notifications`
   - **預期**：`status=credentials_invalid`；UI 顯示紅色提示「儲存的密碼無法解密，
     請重新輸入並儲存」；test-send 按鈕 disable
3. 觸發 audit event
   - **預期**：`notification_record` 落 `outcome=skipped_disabled`（視作未設定）；
     audit 寫入無異常；無 email 寄出
4. admin 重新填密碼按存
   - **預期**：`status` 回 `pending_test`；test-send 按鈕重新啟用

---

## 情境 8：歷史頁顯示去重 + per-recipient 失敗（US5）

**前置**：情境 4 已完成。

**步驟**：

1. admin 開 `/admin/notifications` 滑到歷史區
2. **預期**：
   - 列表前 3 列顯示：
     1. 第二窗 primary record（`outcome=sent`，event_count=1）
     2. 49 筆 suppressed records 摺疊在第一窗 primary record 下面，標籤「49 筆事件合併入此封」
     3. 第一窗 primary record（`outcome=sent`，event_count=50）
3. 點開合併群組
   - **預期**：展開列出 49 筆 suppressed record 的時間戳與 audit_event_id

---

## 整合測試命名建議

| 情境 | 測試檔案 | 測試函式 |
|------|----------|---------|
| 1 | `tests/contract/test_admin_notifications.py` | `test_save_config_and_test_send_happy_path` |
| 2 | `tests/contract/test_admin_notifications.py` | `test_test_send_with_wrong_password_returns_auth_error` |
| 3 | `tests/integration/test_notification_hooks.py` | `test_allocation_quarantined_event_sends_email` |
| 4 | `tests/integration/test_notification_dedup.py` | `test_burst_within_5min_window_sends_once` |
| 5 | `tests/integration/test_notification_hooks.py` | `test_upstream_error_burst_triggers_notification` |
| 6 | `tests/integration/test_notification_hooks.py` | `test_unconfigured_notification_does_not_break_audit` |
| 7 | `tests/integration/test_notification_smtp.py` | `test_credentials_invalid_state_blocks_send` |
| 8 | `tests/contract/test_admin_notifications.py` | `test_history_groups_suppressed_under_primary` |

---

## 部署後手動煙霧測試

1. 取得真實 Gmail App Password；在 `/admin/notifications` 完成設定 + test-send
2. 確認 admin 手機 Gmail app 推播在 30 秒內到達
3. 手動觸發一次低風險的 audit event（例如：admin UI 暫停一個自己的 allocation
   → `audit_events.allocation_paused` — 但這不在 v1 訂閱清單，故不會寄信。改用：
   切換某分配為 service allocation，邊際情境）
4. 確認歷史頁 list 出該事件 + outcome 正確

完成後在 vision Phase 13 條目從「⏳ 規劃中」改為「✅ 完成（YYYY-MM-DD）」並
寫進 history。
