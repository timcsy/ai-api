# Implementation Plan: 管理員 Bootstrap 與部署強化

**Branch**: `017-admin-bootstrap` | **Date**: 2026-05-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-admin-bootstrap/spec.md`

## Summary

補上「首位管理員自動佈建」與「不安全預設 bootstrap token 防呆」，並寫部署文件。技術路徑：新增 idempotent 的 CLI 指令 `ai_api.cli.create_admin`（複用既有 `MemberService.create` + `set_is_admin`），以 Helm pre-install/pre-upgrade hook Job 在遷移後、app 上線前執行；在 `create_app()` 既有 fail-fast 區塊加一道啟動防呆（`COOKIE_SECURE` 為真且 token 為空／預設值即拒啟動）；新增 Helm `bootstrap-admin-job.yaml` 與 `bootstrapAdmin` values；撰寫 `docs/deployment.md` 並自 README 連結。不新增資料表、不改既有授權邏輯。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Pydantic v2（既有，不新增套件）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；本功能不新增表、不新增 migration
**Testing**: pytest（unit / integration），既有 `helm template` 渲染測試
**Target Platform**: Linux server / Kubernetes（Helm chart 已存在於 `deploy/helm/ai-api`）
**Project Type**: web-service（backend）+ CLI + 部署編排
**Performance Goals**: N/A（一次性佈建與啟動驗證，非熱路徑）
**Constraints**: 佈建必須 idempotent；啟動防呆不得誤擋本地開發；不削弱既有授權
**Scale/Scope**: 單一 CLI 指令 + 一處啟動驗證 + 一個 Helm Job + 一份文件

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First (NON-NEGOTIABLE)**: ✅ 先寫失敗測試。涵蓋 CLI 佈建（建立／idempotent／provider 衝突／local_password 邀請）、啟動防呆（預設／空／自訂 × cookie_secure 真假）、Helm 渲染（bootstrap-admin Job 存在且排序在 migrate 之後、envFrom secret）。
- **II. Contract-First**: ✅ 本功能不新增 HTTP 端點。「契約」為 CLI 介面契約（參數、退出碼、idempotent 行為）與啟動驗證契約，記於 `contracts/`。
- **III. 整合測試覆蓋外部依賴**: ✅ CLI 直接操作 DB，以真實 SQLite session 做整合測試（非 mock 邊界）；Helm 以真實 `helm template` 渲染（CLI 不存在時 skip，比照既有）。
- **IV. 可觀測性**: ✅ CLI 以結構化、不洩漏密鑰的訊息回報結果；啟動防呆錯誤帶明確訊息與原因，不印出 token 值。
- **V. 簡潔優先 (YAGNI)**: ✅ 複用既有 service，不新增抽象層、不新增資料表、不新增環境變數（重用 `COOKIE_SECURE` 作 production 訊號）。

**結論**：無違反，無需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/017-admin-bootstrap/
├── plan.md              # 本檔
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1（CLI 契約 + 啟動防呆契約）
└── tasks.md             # Phase 2（/speckit.tasks 產生）
```

### Source Code (repository root)

```text
src/ai_api/
├── cli/
│   └── create_admin.py          # 新增：首位 admin 佈建 CLI（idempotent）
├── config.py                    # 既有：DEFAULT token 常數可抽出供防呆與測試共用
├── main.py                      # 修改：create_app() 既有 fail-fast 區塊加啟動防呆
└── services/
    └── members.py               # 既有：複用 create / set_is_admin（不改邏輯）

deploy/helm/ai-api/
├── templates/
│   └── bootstrap-admin-job.yaml # 新增：pre-install,pre-upgrade hook（weight 1，排在 migrate 後）
└── values.yaml                  # 修改：新增 bootstrapAdmin.{enabled,email,provider,displayName}

docs/
└── deployment.md                # 新增：必填機密、首位 admin、防呆、救援

README.md                        # 修改：連結到 docs/deployment.md

tests/
├── integration/
│   ├── test_create_admin_cli.py # 新增：CLI 佈建整合測試
│   └── test_us4_helm_template.py# 修改：新增 bootstrap-admin Job 渲染斷言
└── unit/
    └── test_startup_admin_token_guard.py  # 新增：啟動防呆單元/整合測試
```

**Structure Decision**: 沿用既有單體 backend + CLI + Helm 佈局。新增檔案落在既有 `cli/`、`deploy/helm/.../templates/`、`docs/`、`tests/`，與現行慣例一致（比照 `cli/load_models.py`、`migration-job.yaml`、`test_startup_crypto.py`）。

## Complexity Tracking

> 無 Constitution 違反，本節留空。
