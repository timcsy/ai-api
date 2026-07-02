# Data Model: 異常偵測 v2

## 新增：`anomaly_config`（單例，migration 0022）

比照 `pool_config` / `notification_config` 單例慣例（`CHECK id=1`）。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | int PK | 恆為 1（`CHECK id = 1`） |
| `auto_quarantine_enabled` | bool NOT NULL default true | 自動隔離總開關 |
| `pause_until` | timestamptz NULL | 非空且未到＝暫停中；過期或空＝依 enabled |
| `threshold_multiplier` | float NOT NULL default 10 | 比例規則倍數（近1h ≥ baseline/hr × 此值） |
| `min_calls` | int NOT NULL default 100 | 低於此近1h呼叫數不評估 |
| `absolute_cold_start` | int NOT NULL default 10000 | 絕對門檻（稀疏baseline/冷啟動用） |
| `baseline_min_calls` | int NOT NULL default 200 | **NEW**：baseline 樣本數低於此 → 不套比例、走絕對門檻 |
| `updated_at` | timestamptz NOT NULL | |
| `updated_by` | varchar(64) NULL | |

**CHECK**：`id=1`、`threshold_multiplier >= 1`、`min_calls >= 0`、`absolute_cold_start >= 0`、`baseline_min_calls >= 0`。

**Lazy-seed**：`get_anomaly_config(db)` 無列時用 `settings.anomaly_threshold_multiplier / anomaly_min_calls / anomaly_absolute_cold_start`（既有）+ `baseline_min_calls` 預設 200 建列。`auto_quarantine_enabled=true`、`pause_until=null`（首次＝現況）。

## 衍生狀態（讀時計算，不落庫）

- `effective_enforcing(now)` = `auto_quarantine_enabled AND (pause_until is null OR pause_until <= now)`。
- `status` 顯示：`enabled` / `disabled` / `paused_until <ts>`。

## 既有（不改 schema）

- `allocations.status`：沿用 `quarantined`（enum VARCHAR）。
- `call_records`：近1h/baseline 計算來源不變。
- `AuditEventType`：+ `anomaly_config_updated`（`native_enum=False`，無 migration）；`allocation_quarantined`/`allocation_unquarantined`/`anomaly_detector_run` 既有。
