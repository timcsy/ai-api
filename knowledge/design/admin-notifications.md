# 設計：管理員 Email 通知（階段 13）

> spec：[`specs/022-admin-email-notifications/`](../../specs/022-admin-email-notifications/)
> （spec.md / plan.md / research.md / data-model.md / contracts/ / quickstart.md / tasks.md）

## 一句話

admin 在 web UI 自助設定 SMTP，平台對 4 種重要 audit event 主動寄信通知；立即寄送 +
DB 去重，無排程器、無 retry，未設定時零影響。

## 元件圖

```
                            ┌─────────────────────────────┐
  任何業務流程              │  audit.record(event)         │
  （anomaly cronjob /       │   1. 寫 auth_audit_log       │
   proxy 401 / daily cap /  │   2. if event ∈ NOTIFY_TYPES │
   burst cronjob）          │      → fire(NotificationEvent)│ ── asyncio.create_task ──┐
                            └─────────────────────────────┘                          │
                                                                                     ▼
                                            ┌──────────────────────────────────────────┐
                                            │ notifier_hook._safe_notify (fresh session)│
                                            │   EmailNotifier.notify()                  │
                                            │     1. load NotificationConfig            │
                                            │        (absent/disabled/invalid → skip)   │
                                            │     2. decrypt password (Fernet)          │
                                            │     2b. dedup gate:                        │
                                            │        active bucket? → suppress (+count)  │
                                            │        else → open bucket, send            │
                                            │     3. render template (per event_type)    │
                                            │     4. aiosmtplib.send → all recipients     │
                                            │     5. persist NotificationRecord          │
                                            └──────────────────────────────────────────┘
```

## 三張表

- `notification_config`（singleton，CHECK id=1）：SMTP host/port/user、Fernet 密文、
  sender、recipients(JSON)、enabled、status（pending_test/verified/credentials_invalid）、
  last_test_*
- `notification_dedup_bucket`：每 `(event_type, 5-min window)` 一列；`event_count`、
  `primary_record_id`（指向實際寄出的 record）
- `notification_record`：每次嘗試一列；`outcome`（sent/suppressed/skipped_*/send_failed_*/
  test_*）、per_recipient_status、subject、body_preview、latency_ms

## 關鍵決策（research 摘要）

| 決策 | 選擇 | 為何 |
|------|------|------|
| SMTP client | `aiosmtplib`（async） | 與 FastAPI async 一致；無 native dep |
| 密碼加密 | 沿用 `PROVIDER_KEY_ENC_KEY` | 不新增加密基礎建設（YAGNI） |
| 去重模型 | 立即寄 + DB gate | 同時滿足 30s SLO 與 5-min ≤1 封 |
| 排程器 | 無 | 立即寄送無 deferred 需求 |
| 事件訂閱 | audit.record() 內 hook | 單一通過點、最低延遲、無漏網 |
| 重試 | v1 不重試 | YAGNI；下個事件會重觸發 |
| Email 範本 | f-string（無 Jinja2） | 4 種事件結構簡單 |

## 觸發來源對照

| 事件型別 | 來源 |
|----------|------|
| `allocation_quarantined` | anomaly detector cronjob（既有） |
| `responses_upstream_error_burst` | `upstream_burst_detector` cronjob（新，每分鐘） |
| `provider_credential_auth_failed` | proxy/responses.py 上游 401/403 catch（新） |
| `allocation_daily_cap_exceeded` | 階段 16 daily cap（模板就緒，事件源待接） |

## 已知限制

multi-replica 真同時事件可能各寄一封（上限 = replica 數）。SQLite/跨連線 row lock 無法
序列化；研究 R3 接受（真同時跨 replica 機率近 0）。單 process 內順序事件正確去重。

## 部署

- helm value：`upstreamBurstDetector.{enabled,schedule,thresholdCalls,windowMinutes}`、
  `notificationCleanup.{enabled,schedule}`
- 新 cronjob：`-upstream-burst`（每分鐘）、`-notification-cleanup`（每日 03:30，30 天 GC）
- SMTP 本身由 admin 在 UI 設定（非 Helm value）
