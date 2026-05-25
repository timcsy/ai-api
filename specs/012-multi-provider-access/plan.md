# Implementation Plan: 多 Provider 支援 + Admin 管理憑證 + Tag-based 存取規則

**Branch**: `012-multi-provider-access` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-multi-provider-access/spec.md`

## Summary

把目前單一 Azure OpenAI 寫死的 upstream 改為**多 provider 動態路由**：admin 透過 web UI 管理各家 LLM provider 的 API key（Fernet 加密 at rest，K8s Secret 持金鑰），catalog 的 model 標明 `provider` 與 `default_access` + `allowed_tags`/`denied_tags`，成員看到的 model 受**「credential gate ∩ access policy」**兩道過濾。提供 zero-downtime 升級路徑把既有 `AZURE_OPENAI_API_KEY` env 灌入 DB。技術上重新引入 `litellm`（library form only，不啟用 proxy server）作為多 provider 抽象層。

## Technical Context

**Language/Version**: Python 3.11+（後端不變）+ TypeScript strict / React 19 / Vite 6（前端不變）
**Primary Dependencies**: FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`litellm`（library only，預計 `>=1.55,<2`）、`cryptography`（Fernet）、既有前端 stack（shadcn/ui + TanStack Query）
**Storage**: PostgreSQL（生產）/ SQLite（dev、CI）；新表 `provider_credentials`、`member_tags`；既有 `model_catalog` 加欄
**Testing**: pytest（後端，既有 213 tests baseline）；Vitest + Testing Library（前端，既有 50 tests baseline）；schemathesis（contract）
**Target Platform**: Linux server（K8s）；本機 dev 走 uvicorn + Vite
**Project Type**: web-service（後端 + SPA）
**Performance Goals**: tag 變更 < 5 秒生效（SC-004）；credential disable 10 秒 SLO（SC-003，沿用既有 revocation SLO）
**Constraints**: zero downtime 升級（SC-007）；明文 key 不入日誌（SC-005）；K8s Secret 缺則 pod 拒啟動（SC-006）
**Scale/Scope**: 百人量級 member、~20 tag、~50 model catalog、~10 provider credential

## Constitution Check

### I. Test-First (NON-NEGOTIABLE) ✅
- 每一個 user story 先寫 contract / integration test（紅）再實作（綠）
- Migration 必有 contract test（schema 驗證）
- 加密邏輯有 unit test（roundtrip + 金鑰錯誤路徑）

### II. API 契約優先 ✅
- 新 endpoint 全部先寫 OpenAPI（contracts/）再實作
- 沿用既有錯誤格式 `{"error": {"code": ..., "message": ...}}`
- 破壞性變更：env-only → DB 為兩個 release，N+1 加 fallback、N+2 拔 fallback（spec FR-019）

### III. 整合測試覆蓋外部依賴 ✅
- 各 provider 至少 1 個 happy-path integration test，real network 由 marker 控制（可在 CI 用 fixture mock）
- DB migration 整合測試（沿用 testcontainers）
- K8s Secret 缺漏整合測試（透過 env 不設來模擬）

### IV. 可觀測性 ✅
- 新稽核事件型別：`provider_credential_{created,rotated,disabled,used_first_time}`、`member_tag_{added,removed,bulk_added}`、`model_access_policy_updated`
- 結構化日誌仍走既有 redact_string；新增「對 plaintext key 100% redact」測試
- Proxy 呼叫日誌加 `credential_id`（不加 key）

### V. 簡潔優先 (YAGNI) ✅
- 不做 rule matcher（複合條件），只支援 tag 集合 AND/NOT
- 不做 provider failover、不做按 provider 切配額池、不做 Tag entity（直接用 distinct，未來再升）
- credential 挑選 round-robin 即可（spec FR-009），不做 weighted / least-used

**Pass**：所有原則均符合，無 deviation。

## Project Structure

### Documentation (this feature)

```text
specs/012-multi-provider-access/
├── plan.md              # 本檔
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── providers.yaml         # Admin: provider credential CRUD + rotate
│   ├── tags.yaml              # Admin: tag CRUD + member tag mgmt + bulk
│   └── model-access.yaml      # Admin: model access policy + catalog 既有 endpoint 擴充
├── checklists/
│   └── requirements.md  # 已完成
└── tasks.md             # Phase 2（由 /speckit.tasks 產生）
```

### Source Code (repository root)

```text
src/ai_api/
├── models/
│   ├── provider_credential.py   # NEW: ProviderCredential ORM model
│   ├── member_tag.py            # NEW: MemberTag ORM model
│   ├── model_catalog.py         # MODIFY: 加 provider / default_access / allowed_tags / denied_tags
│   ├── auth_audit.py            # MODIFY: 擴 AuditEventType enum
│   └── ...
├── services/
│   ├── provider_credentials.py  # NEW: CRUD + Fernet 加密 + rotation + round-robin
│   ├── member_tags.py           # NEW: tag CRUD + member 加/移除/批次
│   ├── model_access.py          # NEW: 兩段過濾邏輯（credential gate ∩ access policy）
│   ├── crypto.py                # NEW: Fernet key load（K8s Secret / env fallback for dev）
│   └── ...
├── proxy/
│   ├── upstream.py              # REWRITE: 從 openai SDK 改回 litellm（library form），加 provider 路由
│   └── router.py                # MODIFY: 呼叫前套用 access policy 防禦性二次檢查
├── api/
│   ├── admin_providers.py       # NEW: providers CRUD endpoints
│   ├── admin_tags.py            # NEW: tag CRUD + member tag mgmt
│   ├── admin_model_access.py    # NEW: model access policy
│   ├── catalog.py               # MODIFY: list/detail 套用兩段過濾
│   └── deps.py                  # 不動
├── cli/
│   └── migrate_azure_env.py     # NEW: env → DB credential migration command
└── config.py                    # MODIFY: 加 PROVIDER_KEY_ENC_KEY (env fallback 路徑)

alembic/versions/
├── 0009_provider_credentials_member_tags.py   # NEW: 新表 + model_catalog 擴欄
└── 0010_audit_events_phase5.py                # NEW: enum 擴值

deploy/helm/ai-api/templates/
├── secret.yaml                  # MODIFY: 加 PROVIDER_KEY_ENC_KEY 必要 Secret entry
└── deployment.yaml              # MODIFY: env 區段引用上述 Secret

frontend/src/
├── routes/admin/
│   ├── providers.tsx            # NEW: provider credential CRUD UI
│   ├── tags.tsx                 # NEW: tag CRUD + bulk apply
│   └── model-access.tsx         # NEW: per-model access policy editor
└── lib/api-client.ts            # 不動

tests/
├── contract/
│   ├── test_admin_providers.py  # NEW
│   ├── test_admin_tags.py       # NEW
│   ├── test_admin_model_access.py  # NEW
│   ├── test_catalog_filtering.py   # NEW: 兩段過濾
│   ├── test_proxy_multiprovider.py # NEW: 4 家 happy path
│   └── test_no_key_leak_global.py  # MODIFY: 加 provider key redaction scenario
├── integration/
│   ├── test_us1_multiprovider.py     # NEW: P1 user story
│   ├── test_us2_credential_ui.py     # NEW: P2 user story
│   ├── test_us3_tag_access.py        # NEW: P3 user story
│   ├── test_us4_azure_env_migration.py  # NEW: P4 user story
│   └── test_credential_rotation_immediacy.py  # NEW: 10s SLO
└── unit/
    ├── test_crypto_fernet.py    # NEW: roundtrip + tampered key
    ├── test_member_tags.py      # NEW
    └── test_provider_rr.py      # NEW: round-robin selection
```

**Structure Decision**: 沿用既有 web-service 結構（`src/ai_api/` 後端 + `frontend/` SPA），不引入新頂層目錄。新增的 services / models / api modules 都放在既有目錄下；前端新增 3 個 admin 視圖檔在 `frontend/src/routes/admin/`。

## Complexity Tracking

無偏離 constitution，本節留空。
