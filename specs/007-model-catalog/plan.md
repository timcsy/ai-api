# Implementation Plan: 階段 4 — Model Catalog + Multi-facet Filter

**Branch**: `007-model-catalog` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-model-catalog/spec.md`

## Summary

延續既有 Python 3.11 + FastAPI + SQLAlchemy + Postgres，無新外部依賴：

- **資料模型**：新表 `model_catalog`，list-valued 欄位用 `JSON` column（Postgres JSONB / SQLite JSON 自動對應）
- **CLI**：`cli/load_models.py` upsert by slug；schema 用 Pydantic 驗證
- **服務**：`services/model_catalog.py` 純函式 filter（list 欄位用 Python set 交集，由 DB JSON 取出後處理 — 首版 8 模型不必走 JSONB containment）
- **API**：`api/catalog.py` 3 個端點，require active member
- **YAML 內容**：`deploy/catalog/azure-2026-05.yaml` 含 9 個 Azure OpenAI 模型

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**：無新增（SQLAlchemy 2、FastAPI、PyYAML 既有；Pydantic 既有）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）— `model_catalog` 表用 JSON columns
**Testing**: pytest 既有；新增 unit + contract + integration
**Target Platform**: 同既有
**Project Type**: web-service（不變）
**Performance Goals**：
  - filter API p95 ≤ 100ms（model 數量 < 100 時純 Python filter 足夠；不必索引）
  - facet API p95 ≤ 50ms（同上）
**Constraints**：
  - 多選 capability AND 語意（FR-007）— 必須 list 全部包含
  - upsert 不刪除未列出的 model（FR-005）防事故
  - facet 結構穩定（FR-016）
**Scale/Scope**：≤ 100 active models、≤ 6 filter dimensions

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | spec SC-007；filter 邏輯 unit test 先寫；contract 測試 API 三端點 | ✅ |
| II. Contract-First | OpenAPI 新增 3 端點；先於實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | CLI 載入 YAML + DB upsert 走 testcontainers Postgres；facet 結構穩定性測試 | ✅ |
| IV. 可觀測性 | 載入失敗寫 stderr + exit code；無需 audit（catalog 是描述性，非安全敏感） | ✅ |
| V. YAGNI | 無 EWMA、無自動同步、無智慧推薦；spec 6 條 NON-GOAL 明列 | ✅ |

**符合 experience.md 教訓**：
- 「async lazy-load 禁止」：filter 由 DB 取整批 → Python 處理；無 ORM lazy
- 「datetime tz-aware」：created_at / updated_at 一律 tz-aware
- 「YAML CLI 載入模式」：同 PriceList 結構（CLI → Pydantic 驗 → upsert）
- 「SQLAlchemy 多分支 select 型別衝突」：本階段查詢結構單一（全 model + Python filter），不會踩

**初次評估通過**，無 Complexity Tracking。

## Project Structure

### Documentation

```text
specs/007-model-catalog/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md            # /speckit.tasks 產出
```

### Source Code

```text
src/ai_api/
├── api/
│   └── catalog.py                # 新：3 個 endpoints
├── services/
│   └── model_catalog.py          # 新：filter 純函式 + facet 計算
├── models/
│   └── model_catalog.py          # 新 ORM model
├── cli/
│   └── load_models.py            # 新：YAML upsert CLI
├── api/deps.py                   # 既有；新增 require_active_member 依賴
└── main.py                       # 既有；註冊新 router

alembic/versions/
└── 0006_model_catalog.py         # 新

deploy/catalog/
└── azure-2026-05.yaml            # 新：9 個 Azure OpenAI 模型

tests/
├── contract/
│   ├── test_catalog_list.py
│   ├── test_catalog_detail.py
│   └── test_catalog_filters.py
├── integration/
│   ├── test_catalog_yaml_upsert.py
│   └── test_catalog_deprecation.py
└── unit/
    └── test_model_filter.py      # 純函式 filter 邏輯
```

**Structure Decision**: 沿用 web-service 模式。filter 邏輯切純函式 + DB I/O 兩
層（同 Phase 3c 演算法分層）— pure function 用 unit test 完整覆蓋多選 AND
等 boundary；DB layer 整合測試。

## Complexity Tracking

無待說明偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | unit + contract + integration 三層測試先於實作 → ✅ |
| Contract-First | `contracts/openapi.yaml` 3 端點完整 → ✅ |
| 整合測試覆蓋外部依賴 | YAML 載入 + DB upsert + idempotent 重跑、deprecation 隔離 → ✅ |
| 可觀測性 | 無新 audit 需求；CLI 走 stderr + exit code | ✅ |
| YAGNI | 無新元件、無新 deps、Helm 不改 → ✅ |

通過，可進入 `/speckit.tasks`。
