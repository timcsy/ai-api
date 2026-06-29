# Data Model: 配額池設定移到前端

## 新增實體：`pool_config`（單例）
| 欄 | 型別 | 說明 |
|----|------|------|
| `id` | int PK, `CHECK (id = 1)` | 單例（同 `notification_config` 慣例） |
| `total_tokens_per_month` | int, ≥0 | 配額池總額 T；0 = 停用 |
| `floor_per_allocation` | int, ≥0 | 每分配保底 |
| `updated_at` | datetime tz-aware | 最後更新時間 |
| `updated_by` | str nullable | 最後更新的 admin（subject/email） |

- **migration 0021**：純加表（head 0020 → 0021）。無既有資料遷移。
- **驗證規則**（service/API 層）：`T ≥ 0`、`floor ≥ 0`、**`T ≥ floor × N`**（N = 池內 active 非服務型非鎖定型分配數）；`T < 近月用量` → soft warning（不擋）。
- **lazy-seed**：`get_pool_config(db)` 首次（無列）用 `settings.pool_total_tokens_per_month`/`pool_floor_per_allocation` 建列 → 首次零行為變更；env 自此僅 bootstrap。

## 唯讀 DTO：建議（Suggestion）
| 欄 | 來源 |
|----|------|
| `recent_month_tokens` | `aggregate_usage` 近月 total_tokens |
| `pool_members` N | active ∧ 非服務型 ∧ 非鎖定型 分配數 |
| `suggested_total` | `round(recent × 2)` |
| `suggested_floor` | informed default（可用基本額量級） |
| （約束） | `T ≥ suggested_floor × N` |

非持久化，GET 時即算。

## 涉及既有（改讀取來源，非改 schema）
- `services/quota_pool.py::apply_rebalance` — 改讀 `get_pool_config(db)`（原讀 `settings.pool_*`）。
- `api/quota_pool.py::get_pool_status` — 同上 + 回 config/suggestion/N/warning。
- `config.py` `pool_*` — 保留為 bootstrap 預設來源。
