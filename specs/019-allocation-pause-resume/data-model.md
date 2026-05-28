# Phase 1 Data Model: 憑證暫停 / 恢復

**不新增資料表、不新增 migration**。僅為既有 enum 加列舉值（皆 `native_enum=False`，存 VARCHAR）。

## 既有實體改動

### Allocation（`models/allocation.py`）
- `AllocationStatus` 加列舉值 **`paused`**（`Enum(..., native_enum=False, length=16)`，免 migration）。
- 既有欄位（`token` 相關、`quota_tokens_per_month`、`origin`、`quota_locked`）語意不變；暫停**不**觸及。

**狀態機（本功能相關）：**

```text
              pause()                         resume()
  active ───────────────▶ paused ───────────────▶ active
  active ──revoke()──▶ revoked (終局，不可 pause/resume)
  active ──[偵測器]──▶ quarantined ──unquarantine()──▶ active

  非法（一律拒絕、不改動）：
    pause   僅允許 from active；對 paused/revoked/quarantined → 409
    resume  僅允許 from paused；對 active/revoked/quarantined → 409
```

### CallRecord（`models/call_record.py`）
- `CallOutcome` 加列舉值 **`rejected_paused`**（`Enum(..., native_enum=False, length=32)`，免 migration）。
- 暫停中被擋的呼叫以此結果記錄，供用量切分與稽核區分（FR-008）。

### AuditEvent（`models/auth_audit.py`）
- `AuditEventType` 加 **`allocation_paused`** / **`allocation_resumed`**（`Enum(..., native_enum=False, length=64)`，免 migration）。
- pause/resume 各寫一筆（actor=admin、target=allocation_id）。

## 不變式
- 暫停與恢復**只改 `status`**；token、配額、reclaim lock 皆不動。
- `paused` 與 `quarantined` 是不同來源、不同處理路徑：前者管理員手動（pause/resume），後者偵測器自動（quarantine/unquarantine）；resume 不處理 quarantined，unquarantine 不處理 paused。
- 拒絕的呼叫（含 rejected_paused）不計費（與既有 revoked / quota 拒絕一致）。
