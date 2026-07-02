# Contract: Anomaly Config admin API

所有端點 `require_admin_token`。

## GET /admin/anomaly/config

回目前設定 + 衍生狀態。
```json
{
  "auto_quarantine_enabled": true,
  "pause_until": null,
  "effective_enforcing": true,
  "status": "enabled",              // enabled | disabled | paused
  "thresholds": {
    "threshold_multiplier": 10.0,
    "min_calls": 100,
    "absolute_cold_start": 10000,
    "baseline_min_calls": 200
  },
  "updated_at": "...", "updated_by": "admin"
}
```

## PUT /admin/anomaly/config

部分更新（欄位皆選填）；驗證後持久化 + 稽核 `anomaly_config_updated`。
```json
{
  "auto_quarantine_enabled": false,        // 開/關
  "pause_until": "2026-07-03T10:00:00Z",   // 暫停到期（可 null 清除）
  "threshold_multiplier": 20.0,
  "min_calls": 300,
  "absolute_cold_start": 10000,
  "baseline_min_calls": 200
}
```
**驗證**：`threshold_multiplier >= 1`、其餘 `>= 0`；違反 → 422 `invalid_anomaly_config`。回更新後完整設定（同 GET）。

## 既有（沿用）

- `POST /admin/allocations/{id}/unquarantine` — 解除隔離（US3 前端直達，不改後端）。
- `GET /admin/allocations/{id}/quarantine-reason` — 隔離原因（已存在）。

## 行為契約（偵測器）

- `effective_enforcing == false`（關閉或暫停中）→ 掃描照跑、`anomaly_detector_run` 稽核帶 `enforced=false`、**不隔離任何分配**。
- `baseline_total < baseline_min_calls` → 只用絕對門檻（不套比例）。
- 服務型分配豁免不變。
