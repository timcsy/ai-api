# Phase 1 Data Model: 階段 2.5 — Hardening

無新主領域實體。Schema 變更如下：

## Allocation（修改）

`status` enum 加值：

| 既有 | 新增 |
|---|---|
| active | `quarantined` |
| revoked |  |

**State transitions** (新增)：
```
active ──[anomaly_detector quarantines]──→ quarantined
quarantined ──[admin unquarantine]──→ active
quarantined ──[admin revoke]──→ revoked
```

撤回（revoked）為終態；quarantined 可由管理員解除回 active。

---

## AuthAuditLog（修改）

`event_type` enum 加值：

- `allocation_quarantined`（anomaly_detector 觸發或 admin 手動觸發）
- `allocation_unquarantined`
- `anomaly_detector_run`（每次 cron 跑完寫一筆 summary）

**details schema 範例**（quarantined）：
```json
{
  "trigger": "anomaly_detector",
  "last_hour_calls": 1052,
  "baseline_calls_per_hour": 87,
  "multiplier": 12.1
}
```

---

## PasswordAttempt（無 schema 變更，新查詢）

新增 service-level query：

```sql
SELECT COUNT(*) FROM password_attempts
WHERE source_ip = :ip
  AND attempted_at >= now() - interval '60 seconds'
  AND outcome IN ('bad_password', 'unknown_email')
```

新增 index（migration `0003`）：`(source_ip, attempted_at)`。

---

## Settings（修改）

新欄位（透過 `Pydantic Settings`）：

| 欄位 | 型別 | 預設 | 用途 |
|---|---|---|---|
| `allowed_providers` | `list[str]` | `["azure"]` | provider allowlist |
| `anomaly_check_interval_min` | `int` | `5` | CronJob 排程間隔 |
| `anomaly_threshold_multiplier` | `float` | `10.0` | 觸發倍數 |
| `anomaly_absolute_cold_start` | `int` | `10000` | 冷啟動絕對門檻 |
| `anomaly_min_calls` | `int` | `100` | 最低觸發呼叫數 |
| `perip_lockout_threshold` | `int` | `10` | per-IP rate limit 門檻 |

---

## Migration map

| Spec FR | Migration / Schema 動作 |
|---|---|
| FR-010 | Alembic `0003`：擴充 AllocationStatus enum + AuditEventType enum |
| FR-013 | Alembic `0003`：加 `idx_attempt_source_ip_time` index |

其他 FR（NetworkPolicy / Trivy / distroless）為部署層，無 DB schema 影響。
