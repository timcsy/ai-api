# Implementation Plan: 階段 3a — 用量觀測與費用計算

**Branch**: `004-usage-billing` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-usage-billing/spec.md`

## Summary

延續既有 Python 3.11 + FastAPI + SQLAlchemy + Postgres：

- **資料模型**：新表 `PriceList`；`Allocation` +2 欄；`CallRecord` +1 欄
- **計費**：proxy 在 `record_call(success)` 寫入前查最新適用 PriceList，
  算出 `cost_usd` 一併存（point-in-time，FR-011）
- **配額**：proxy 在送上游前查 `SELECT SUM(total_tokens) FROM call_records
  WHERE allocation_id=? AND started_at >= utc_month_start` 與 quota 比對；
  ≥ quota 即拒
- **查詢**：`UsageService` 用 SQL `GROUP BY` 聚合，依 group_by 切換鍵
- **CLI**：`python -m ai_api.cli.load_prices <yaml>` 解析 yaml 並 INSERT；
  違反 UNIQUE (provider, model, effective_from) 則錯
- **CSV 匯出**：FastAPI streaming response 用 stdlib `csv` module
- **CORS**：FastAPI `CORSMiddleware`；session cookie 設定依 `cors_origins`
  是否非空動態切 SameSite

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**：無新增 — 用 SQLAlchemy `func.sum/group_by`、stdlib `csv`、
  stdlib `yaml` 已透過 schemathesis 拖入 (`pyyaml`)；FastAPI `CORSMiddleware` 內建
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）
  - 新表 `price_list`
  - 既有表 `allocations`、`call_records` 加欄位（Alembic 0004）
**Testing**: pytest 既有；新增 contract/integration/unit
**Target Platform**: 同既有（Linux container + K8s）
**Project Type**: web-service（不變）
**Performance Goals**：
  - SC-001 「10k CallRecord by-member 查詢 ≤ 2s」 → DB 端做 GROUP BY，
    應用層只 stream rows
  - SC-002 配額檢查每次 proxy 呼叫 < 50ms → index on (allocation_id, started_at)
**Constraints**：
  - point-in-time billing 不可回溯（FR-013）
  - 配額計算採「樂觀」（FR-007）：可能輕微超額（±1 請求），與 anomaly_detector
    互補
**Scale/Scope**：≤ 1M CallRecord、≤ 1000 active allocations、≤ 100 模型

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | FR + SC-008 都要求 TDD；contract 測試先於 endpoint | ✅ |
| II. Contract-First | OpenAPI 新增 5 個端點 + 擴充 PATCH /admin/allocations；先於實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | DB 行為以 testcontainers Postgres 驗證（含 GROUP BY 與配額查詢）；YAML 載入用真實 yaml 檔 | ✅ |
| IV. 可觀測性 | quota 拒絕走既有 record_and_respond → CallRecord（已有結構化 outcome）；新增 outcome `rejected_quota_exceeded` | ✅ |
| V. YAGNI | 不接 Azure Retail Prices API、不加 Team、不做 UI、不接 Redis 快取 | ✅ |

**符合 experience.md 教訓**：
- 「async lazy-load 禁止」：UsageService 全部直接寫 SQL（`select(func.sum(...))`），
  不依賴 ORM 關聯
- 「datetime 一律 tz-aware」：from/to 一律 tz-aware；UTC 月初由
  `datetime(now.year, now.month, 1, tzinfo=UTC)` 算
- 「拒絕路徑先 bind context」：quota_exceeded 拒絕仍寫 CallRecord 並帶 allocation_id

**初次評估通過**，無 Complexity Tracking。

## Project Structure

### Documentation

```text
specs/004-usage-billing/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md  (by /speckit.tasks)
```

### Source Code

```text
src/ai_api/
├── api/
│   ├── usage.py                  # 新：/admin/usage, /admin/usage.csv, /admin/usage.json,
│   │                             #     /admin/allocations/{id}/usage-timeseries
│   ├── allocations.py            # 既有；PATCH /admin/allocations/{id} 加 quota 欄位支援
│   └── deps.py                   # 既有；加 cors-aware cookie setting helper
├── services/
│   ├── usage.py                  # 新：aggregate queries
│   ├── pricing.py                # 新：lookup_price_for_call(model, ts) + load_prices_from_yaml
│   ├── quota.py                  # 新：current_month_usage + check_quota
│   └── records.py                # 既有；record_call() 加 cost_usd 計算
├── models/
│   ├── price_list.py             # 新
│   ├── allocation.py             # 既有；加 quota_tokens_per_month, is_service_allocation
│   ├── call_record.py            # 既有；加 cost_usd + outcome enum 加 rejected_quota_exceeded
├── proxy/
│   └── router.py                 # 既有；在 allowlist 之後、record_call 之前插入 quota 檢查
├── cli/
│   └── load_prices.py            # 新：YAML loader CLI
├── config.py                     # 既有；加 cors_origins
└── main.py                       # 既有；加 CORSMiddleware

alembic/versions/
└── 0004_usage_billing.py         # 新

deploy/
├── helm/ai-api/templates/
│   ├── secret.yaml               # 加 CORS_ORIGINS
│   ├── deployment.yaml           # 不變
│   └── cronjob-loadprices.yaml   # 新：optional，可選用 CronJob 自動 reload yaml from S3 等
└── prices/                       # 新：sample YAML 檔
    └── azure-2026-05.yaml

tests/
├── contract/
│   ├── test_usage_endpoint.py
│   ├── test_usage_timeseries.py
│   ├── test_usage_export.py
│   ├── test_cors.py
│   └── test_quota_patch.py
├── integration/
│   ├── test_us3_quota_enforcement.py
│   ├── test_us5_pricelist_pit.py
│   └── test_aggregation_perf.py
└── unit/
    ├── test_price_lookup.py
    ├── test_quota_check.py
    └── test_csv_writer.py
```

**Structure Decision**: 新增 `api/usage.py`、`services/usage.py`、`services/pricing.py`、
`services/quota.py` 四個檔案；CLI 沿用既有 `cli/` 模組（同階段 2.5 anomaly_detector
的形式）。`prices/` 目錄收 YAML 範例，部署時透過 ConfigMap mount 或 CLI 載入即可。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | contract / integration / unit 三層測試先於實作 → ✅ |
| Contract-First | `contracts/openapi.yaml` 新端點皆有定義 → ✅ |
| 整合測試覆蓋外部依賴 | testcontainers Postgres 跑 GROUP BY + UNIQUE 衝突 + 月初邊界 → ✅ |
| 可觀測性 | quota_exceeded 寫 CallRecord；CLI 載入價目寫 stdout + 結構化 log → ✅ |
| YAGNI | 無 cache、無 BI、無 Team、無 UI、無自動爬蟲 → ✅ |

通過，可進入 `/speckit.tasks`。
