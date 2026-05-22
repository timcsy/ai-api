# Implementation Plan: 階段 2.5 — 安全加固 (Hardening)

**Branch**: `003-hardening` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-hardening/spec.md`

## Summary

純安全強化，無新功能。延續 Phase 1+2 的 FastAPI + SQLAlchemy + Helm 線：

- **應用層**：新增 `Settings.allowed_providers`；proxy router 在 LiteLLM 之前
  拒掉非清單上的 provider。Allocation `status` enum 加 `quarantined`，
  proxy 對其立即拒。背景 anomaly_detector（K8s CronJob）每 5 分鐘掃描，把
  突發用量飆高的分配標為 `quarantined`。
- **網路層**：Helm chart 加 NetworkPolicy template（預設 enabled）；deny-all
  egress + allow {DNS, Postgres pod, 443/TCP} + explicit deny 169.254.0.0/16。
- **CI**：`.github/workflows/ci.yml` 加 Trivy 步驟，HIGH+CRITICAL 失敗即擋；
  支援 `.trivyignore`。
- **容器**：Dockerfile 換 `gcr.io/distroless/python3-debian12`；healthcheck
  改用純 Python script；Deployment securityContext 加
  `readOnlyRootFilesystem` + emptyDir 給 `/tmp`。
- **rate limit**：擴充現有 `ratelimit.py`，多查 per-IP 維度。

## Technical Context

**Language/Version**: Python 3.11+（不變）
**Primary Dependencies**：沒新 Python 依賴。CI 加 `aquasecurity/trivy-action@v0.24`。
**Storage**: PostgreSQL（不變）；無新表，只修 Allocation enum
**Testing**: pytest 既有；新加 `tests/integration/test_us4_anomaly_detector.py`、
  `tests/integration/test_us2_network_policy.py`（前者跑 service，後者用
  `helm template` + 純斷言 manifest 結構）
**Target Platform**: K8s（NetworkPolicy 需 CNI 支援）
**Project Type**: web-service（不變）
**Performance Goals**：anomaly detector 一輪掃描 ≤ 5 秒（即使 1000 分配）
**Constraints**：
- distroless image 不能有 shell，所以 docker HEALTHCHECK 必須用 Python
- NetworkPolicy 在 k3s 預設 Flannel 上不生效；plan 階段 1 任務即把這個
  限制寫進 quickstart 提示
**Scale/Scope**：≤ 500 active allocations、≤ 10 quarantine events/天

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | spec FR-008、SC-008；anomaly_detector、provider allowlist、NetworkPolicy 都先寫測試 | ✅ |
| II. Contract-First | 新增端點僅 `POST /admin/allocations/{id}/unquarantine`；OpenAPI 更新先於實作 | ✅ |
| III. 整合測試覆蓋外部依賴 | NetworkPolicy 以 `helm template` 驗 manifest；anomaly_detector 以 testcontainers Postgres 驗實際 quarantine 行為；Trivy 在 CI 上「真的跑一次」 | ✅ |
| IV. 可觀測性 | `allocation_quarantined`、`allocation_unquarantined`、`anomaly_detected` 寫 AuthAuditLog；anomaly_detector 自身結構化 JSON log | ✅ |
| V. YAGNI | 不引入 Celery / Redis / Vault / cosign / Slack 通知（皆排除於 spec FR-024 等） | ✅ |

**符合 experience.md 的教訓**：
- 「拒絕路徑先 bind context」：provider_not_allowed 與 quarantine reject 都會
  寫 CallRecord 並帶 allocation_id（如可解析）
- 「Helm pre-install hook 順序」：anomaly_detector 用 K8s CronJob，獨立於
  app pod，無 hook 順序問題
- 「快速迭代不要用 mutable tag」：Trivy 用 pinned action version，distroless
  image tag 用 digest 鎖死（Dockerfile 內）

**初次評估通過**，無 Complexity Tracking 需要填寫。

## Project Structure

### Documentation (this feature)

```text
specs/003-hardening/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml        # 主要是 unquarantine 端點 + ErrorResponse 新 code
├── checklists/
│   └── requirements.md
└── tasks.md                # /speckit.tasks 產出
```

### Source Code（修改 / 新增）

```text
src/ai_api/
├── config.py                     # +allowed_providers + anomaly thresholds
├── proxy/
│   ├── router.py                 # 加 provider allowlist 檢查
│   └── allowlist.py              # 新：parse_provider + check_allowed
├── services/
│   └── anomaly.py                # 新：detect_and_quarantine()
├── auth/
│   ├── ratelimit.py              # 擴充加 per-IP check
│   └── audit.py                  # 加新 event_type
├── api/
│   └── allocations.py            # 加 unquarantine 端點
├── models/
│   ├── allocation.py             # status enum 加 quarantined
│   └── auth_audit.py             # event_type enum 加 3 個值
└── cli/
    └── run_anomaly_detector.py   # 新：CronJob 入口；單次掃描即退出

alembic/versions/
└── 0003_hardening.py             # 加 quarantined enum 值

deploy/
├── docker/
│   └── Dockerfile                # distroless + Python healthcheck
├── helm/ai-api/
│   ├── values.yaml               # +networkPolicy.enabled, +cronJob 設定
│   └── templates/
│       ├── networkpolicy.yaml    # 新
│       ├── cronjob-anomaly.yaml  # 新
│       └── deployment.yaml       # +readOnlyRootFilesystem +emptyDir tmp

.github/workflows/
└── ci.yml                        # +Trivy step

.trivyignore                      # 新：空檔起步；docs PR 模板要求記錄理由

tests/
├── contract/
│   ├── test_proxy_provider_allowlist.py
│   ├── test_unquarantine.py
│   └── test_perip_ratelimit.py
├── integration/
│   ├── test_us2_network_policy.py        # helm template 結構驗證
│   ├── test_us4_anomaly_detector.py      # 真跑 anomaly_detector + Postgres
│   └── test_us5_container_security.py   # docker image inspect + run
└── unit/
    └── test_provider_parsing.py
```

**Structure Decision**: 沿用 Phase 1/2 single-project layout；新增 `src/ai_api/cli/`
模組裝 CronJob 入口（單檔即可），與 services 平行。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | contract 與 integration 測試先於實作 → ✅ |
| Contract-First | `unquarantine` + 新錯誤碼於 OpenAPI 定義 → ✅ |
| 整合測試覆蓋外部依賴 | helm template 驗 NetworkPolicy；testcontainers Postgres 驗 anomaly_detector；CI 跑真 Trivy → ✅ |
| 可觀測性 | 三個新 audit event_type 寫入 AuthAuditLog；anomaly_detector 結構化 log → ✅ |
| YAGNI | 不引入 message queue、不引入 KMS、不引入 sidecar → ✅ |

通過。可進入 `/speckit.tasks`。
