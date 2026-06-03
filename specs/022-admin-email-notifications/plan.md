# 實作計畫：管理員 Email 通知

**Branch**: `022-admin-email-notifications` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-admin-email-notifications/spec.md`

## 摘要

讓平台 admin 在 web UI 自助設定 SMTP 寄信憑證 + recipient 清單，平台在 4 種重要 audit
事件發生時自動寄 email 通知。包含「發測試信」即時驗證、5 分鐘窗內同型別去重、未設定
時通知停用不擋 boot。第一版採「事件→立即寄信」模型，藉資料庫紀錄作為去重 gate 取代
背景排程器；多 replica 環境每窗每型別仍至多寄出 N 封（N = replica 數量），實務上可接受。

架構抽象為 `Notifier` interface + `EmailNotifier` 單一實作；未來 LINE Bot / Web Push
作為平行 adapter 加入時不動現有結構。

## 技術脈絡

**Language/Version**: Python 3.11+（後端，既有不變）/ TypeScript strict + React 19 + Vite 6（前端，既有不變）
**Primary Dependencies**:
- 後端既有：FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`cryptography`（Fernet）
- 後端**新增**：`aiosmtplib`（async SMTP client，避免在 async 路徑用 `smtplib` + thread）
- 前端既有：TanStack Query、shadcn/ui

**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；本功能新增表 `notification_config`、
`notification_record`、`notification_dedup_bucket`；migration `0014_admin_notifications`

**Testing**: pytest（後端）+ vitest（前端）；SMTP 整合測試用 `aiosmtpd` 內建 test server
（與 `aiosmtplib` 同生態，無外部依賴）

**Target Platform**: K8s 叢集（既有 helm chart `deploy/helm/ai-api`，無新 deploy 元件——
所有 SMTP 流量從 backend pod egress）

**Project Type**: Web application（backend + frontend，既有）

**Performance Goals**:
- 事件 → SMTP server 收到回應 ≤ 30 秒（FR-017）
- 通知設定 CRUD ≤ 200 ms p95
- 去重檢查（DB 查詢）≤ 20 ms p95

**Constraints**:
- 未設定 SMTP 時 0 影響（FR-005 + SC-004）
- SMTP 密碼 Fernet 加密落 DB（FR-003，沿用 `PROVIDER_KEY_ENC_KEY`）
- 寄信失敗 MUST NOT 影響 audit event 寫入（FR-025）
- 多 replica 環境每窗每型別至多寄出 N 封（N = replica 數），accept 為 v1 限制

**Scale/Scope**:
- 每部署 1–5 個 admin、1 份 `NotificationConfig`
- 4 種事件型別（v1 固定）
- 通知歷史 30 天保留（每日清理 cronjob）
- 預期吞吐：尖峰 100 封/天/部署；典型 5 封/天/部署

## 憲章檢核（Constitution Check）

*GATE：必須在 Phase 0 research 前通過。Phase 1 design 後重核。*

### I. Test-First（不可妥協）
- ✅ Phase 2 tasks 將以「先寫失敗測試 → 實作」順序執行
- ✅ contract tests 為合併前必過 gate（4 條 endpoint，1 條 SMTP integration）
- ✅ 缺陷修復亦以可重現失敗測試為起點

### II. API 契約優先
- ✅ Phase 1 將以 OpenAPI 定義 `/admin/notifications/*` 四條端點 + 錯誤格式
- ✅ 契約測試 in `tests/contract/test_admin_notifications.py`
- ✅ 無破壞性 API 變更（純新增）

### III. 整合測試覆蓋外部依賴
- ✅ SMTP 為外部邊界 → 用 `aiosmtpd` 起內部 test server 驗證「真實 SMTP 握手」
- ✅ DB 互動以既有 pytest 整合測試 pattern（SQLite + 受控容器化 PG）

### IV. 可觀測性
- ✅ 結構化 JSON log（既有 pattern）；每筆寄信 log `event_type / recipients[*]@masked / latency_ms / status_code / error_code`
- ✅ SMTP server 回應碼必落 log（FR-025）
- ✅ 絕不 log 密碼明文（FR-003）；recipient email 採 partial mask（`tim***@school.edu.tw`）

### V. 簡潔優先（YAGNI）
- ✅ 採「立即寄送 + DB 去重 gate」單一模型；**不**做後台排程／aggregation engine
- ✅ 不做 retry queue；失敗即記錄、admin 可手動 re-test
- ✅ 不做 per-admin 偏好（v1 共用設定）
- ✅ 不做事件型別 UI 編輯（清單寫死於 code，Helm value override 即足夠）

### 語言與文件規範
- ✅ spec / plan / tasks / checklists 皆 **繁體中文**
- ✅ code 識別字（變數、函式、欄位、API 路徑）**英文**
- ✅ commit 訊息 **英文**祈使句
- ✅ 對使用者面向訊息（admin UI 文案、email subject/body）**繁體中文**

**Gate 結果（Phase 0 前）**：通過。無偏離項。

**重核（Phase 1 後）**：
- I. TDD：Phase 1 contracts 已產出 → `/speckit.tasks` 將生成「先寫 contract test + integration test → 才寫實作」順序。✅
- II. 契約優先：`contracts/admin-notifications.openapi.yaml` 與 `contracts/notifier-interface.md` 完整、含 error envelope；契約測試清單在 quickstart.md。✅
- III. 整合測試：SMTP 整合測試（aiosmtpd）、audit hook 整合測試、dedup 整合測試三項齊全。✅
- IV. 可觀測性：notifier 介面契約已明定 structured log 欄位（含 mask 規則）。✅
- V. YAGNI：仍維持「無 scheduler / 無 retry / 無 Jinja2 / 無新 KMS」單一立即寄送模型。✅

**Phase 1 後 Gate 結果**：通過。設計穩定，可進入 `/speckit.tasks`。

## 專案結構

### 文件（本 feature）

```text
specs/022-admin-email-notifications/
├── plan.md                  # 本檔
├── spec.md                  # /speckit.specify 輸出（已完成）
├── research.md              # Phase 0 輸出
├── data-model.md            # Phase 1 輸出
├── quickstart.md            # Phase 1 輸出
├── contracts/               # Phase 1 輸出
│   ├── admin-notifications.openapi.yaml
│   └── notifier-interface.md   # Python interface contract
├── checklists/
│   └── requirements.md      # /speckit.specify 輸出（已完成）
└── tasks.md                 # Phase 2 輸出（/speckit.tasks 階段產生）
```

### 原始碼（既有專案結構，新增與既有）

```text
backend (src/ai_api/)
├── models/
│   └── notification.py             # NEW: NotificationConfig / NotificationRecord / NotificationDedupBucket
├── services/
│   ├── notifications.py            # NEW: NotificationConfigService + history queries
│   ├── notifier.py                 # NEW: Notifier ABC + EmailNotifier
│   └── audit.py                    # 現有 audit emit 點注入 notifier 通知 hook
├── api/
│   └── admin_notifications.py      # NEW: /admin/notifications 端點群
├── alembic/versions/
│   └── 0014_admin_notifications.py # NEW: 三張表 + index
└── main.py                         # 註冊新 router

frontend (frontend/src/)
├── routes/admin/
│   └── notifications.tsx           # NEW: /admin/notifications 設定頁
└── components/app-shell.tsx        # 加 sub-nav 「通知」入口

tests/
├── contract/
│   └── test_admin_notifications.py # NEW: 端點契約測試
├── integration/
│   ├── test_notification_smtp.py   # NEW: aiosmtpd 整合測試
│   ├── test_notification_dedup.py  # NEW: 去重視窗驗證
│   └── test_notification_hooks.py  # NEW: audit event → notifier hook
└── unit/
    └── test_notifier_email.py      # NEW: EmailNotifier 單元測試

deploy/helm/ai-api/templates/
└── notification-cleanup-cronjob.yaml  # NEW: 每日 notification_record GC
```

**Structure Decision**: 沿用既有 web application 結構（`src/` 後端 + `frontend/` 前端 +
`tests/` 三層），無新增頂層目錄。新增三張資料表（migration 0014），三條 service 模組，
一個 admin API router，一個前端設定頁，一條 Helm cronjob（30 天 GC）。

## Complexity Tracking

> 無憲章違反項，本節空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| —         | —          | —                                   |

## 下一步

- Phase 0 / Phase 1 artifacts 由本 `/speckit.plan` 在後續自動產生
- Phase 1 完成後重核憲章
- `/speckit.tasks` 將以 plan + research + data-model + contracts 為輸入產出 tasks.md
