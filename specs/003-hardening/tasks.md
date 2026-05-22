# Tasks: 階段 2.5 — 安全加固 (Hardening)

**Input**: Design documents from `/specs/003-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: TDD enforced（constitution Principle I + spec SC-008）。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

- [ ] T001 在 `src/ai_api/config.py` 加入新 Settings 欄位：`allowed_providers`、`anomaly_check_interval_min`、`anomaly_threshold_multiplier`、`anomaly_absolute_cold_start`、`anomaly_min_calls`、`perip_lockout_threshold`（依 data-model.md）
- [ ] T002 [P] 建立 `.trivyignore`（空檔 + 註解模板說明「忽略 CVE 必須附理由於 PR 描述」）
- [ ] T003 [P] 更新 `.env.example` 對新 Settings 加 commented 範例

---

## Phase 2: Foundational

- [ ] T004 修改 `src/ai_api/models/allocation.py`：`AllocationStatus` enum 加 `quarantined` 值
- [ ] T005 [P] 修改 `src/ai_api/models/auth_audit.py`：`AuditEventType` enum 加 `allocation_quarantined`、`allocation_unquarantined`、`anomaly_detector_run`
- [ ] T006 建立 Alembic migration `alembic/versions/0003_hardening.py`：
   - 擴充 enum 值（SQLite 用 batch_alter；Postgres 用直接 ALTER）
   - 加 `idx_attempt_source_ip_time` index on `password_attempts(source_ip, attempted_at)`

**Checkpoint**：DB schema 更新完成，後續所有 story 可在共同基礎上展開。

---

## Phase 3: US1 — Provider allowlist (P1)

**Goal**：限定哪些 provider 可被代理。
**Independent Test**：allowed=`["azure"]` → `azure/*` 成功；`anthropic/*` 即使
LiteLLM 支援也 403 `provider_not_allowed`。

### Tests for US1 (TDD red)
- [ ] T007 [P] [US1] 單元測試 `tests/unit/test_provider_parsing.py`：`parse_provider("azure/gpt-4o-mini")` → `("azure", "gpt-4o-mini")`；`parse_provider("anthropic/claude-3")` → `("anthropic", "claude-3")`；無 `/` 走預設
- [ ] T008 [P] [US1] 契約測試 `tests/contract/test_proxy_provider_allowlist.py`：
   - 允許清單內 → 200
   - 不在清單 → 403 `provider_not_allowed`；CallRecord outcome 為 `rejected_provider`
   - 啟動時 `allowed_providers=[]` → service 啟動失敗 (fail-fast)

### Implementation for US1
- [ ] T009 [P] [US1] 實作 `src/ai_api/proxy/allowlist.py`：`parse_provider()` + `check_allowed()`
- [ ] T010 [US1] 在 `src/ai_api/models/call_record.py` 的 `CallOutcome` enum 加 `rejected_provider` 值（依需要可放 0003 migration）
- [ ] T011 [US1] 修改 `src/ai_api/proxy/router.py`：在解析請求 model 後、呼叫 LiteLLM 前插入 allowlist check
- [ ] T012 [US1] 修改 `src/ai_api/main.py` lifespan：啟動時若 `allowed_providers=[]` 即 raise，service 拒絕啟動

**Checkpoint**：provider allowlist 上線；不在清單的供應商即刻被擋。

---

## Phase 4: US2 — NetworkPolicy (P1)

**Goal**：K8s pod egress 限制到 {DNS, Postgres, 443/internet}，封 metadata IP。
**Independent Test**：見 quickstart §2 — 4 種網路情境（metadata / 任意 HTTP / 上游 HTTPS / Postgres）。

### Tests for US2 (TDD red)
- [ ] T013 [P] [US2] 整合測試 `tests/integration/test_us2_network_policy.py`：用 `helm template` 渲染 chart，斷言 NetworkPolicy 結構含 egress allow 443/53/5432 + deny 169.254.0.0/16

### Implementation for US2
- [ ] T014 [P] [US2] 建立 Helm template `deploy/helm/ai-api/templates/networkpolicy.yaml`（依 research.md §2 規則）
- [ ] T015 [P] [US2] 修改 `deploy/helm/ai-api/values.yaml` 加 `networkPolicy.enabled: true` toggle + postgresPodSelector / postgresNamespace 設定鍵
- [ ] T016 [US2] 更新 `deploy/dev-postgres.yaml`：Pod 加 label `app: ai-api-pg`（NetworkPolicy podSelector 對應）

**Checkpoint**：Helm chart 可在叢集套用 NetworkPolicy（叢集 CNI 支援 NP 才生效）。

---

## Phase 5: US3 — Trivy CVE 掃描 (P1)

**Goal**：CI 在 PR 階段擋住 HIGH/CRITICAL CVE 的 image。
**Independent Test**：故意引入含 HIGH CVE 的舊版依賴 → CI Trivy job 失敗。

### Tests for US3
- [ ] T017 [P] [US3] 撰寫文件 `.github/PULL_REQUEST_TEMPLATE.md`：要求若加入 `.trivyignore` 條目時須說明理由

### Implementation for US3
- [ ] T018 [US3] 修改 `.github/workflows/image.yml`（或 `ci.yml`，依現有結構）加 Trivy step：
   ```yaml
   - uses: aquasecurity/trivy-action@v0.24.0
     with:
       image-ref: ghcr.io/timcsy/ai-api:${{ github.sha }}
       severity: HIGH,CRITICAL
       exit-code: '1'
       ignore-unfixed: true
       trivyignores: .trivyignore
   ```
   step 必須在 build 之後、若 build 失敗整個 job 失敗

**Checkpoint**：開 PR 即會跑 Trivy；故意失敗測試可手動執行驗證。

---

## Phase 6: US4 — Anomaly detector + Quarantine (P1)

**Goal**：突發用量自動隔離分配；管理員可解除。
**Independent Test**：見 quickstart §4 — 模擬突發 → detector 隔離 → 呼叫被拒 → unquarantine 恢復。

### Tests for US4 (TDD red)
- [ ] T019 [P] [US4] 契約測試 `tests/contract/test_unquarantine.py`：`POST /admin/allocations/{id}/unquarantine` 200 / 404 / 409（非 quarantined 狀態時）
- [ ] T020 [P] [US4] 契約測試 `tests/contract/test_quarantine_proxy_reject.py`：對 quarantined 分配呼叫 `/v1/chat/completions` 回 403 `allocation_quarantined`
- [ ] T021 [P] [US4] 整合測試 `tests/integration/test_us4_anomaly_detector.py`：
   - 種入 24h baseline + 突發 1 小時 → 跑 detector → 該 allocation status=quarantined
   - cold-start 場景（無 baseline + < 10000 calls）→ 不觸發
   - cold-start + ≥ 10000 calls → 觸發

### Implementation for US4
- [ ] T022 [P] [US4] 實作 `src/ai_api/services/anomaly.py`：`detect_and_quarantine()` 函式，依 research.md §5 演算法
- [ ] T023 [P] [US4] 修改 `src/ai_api/proxy/router.py`：在 allocation lookup 後加 `status == quarantined` 檢查（與 revoked 同層）
- [ ] T024 [P] [US4] 修改 `src/ai_api/auth/audit.py`：新 event_type helper 函式（如 `record_quarantine`）
- [ ] T025 [US4] 實作 `src/ai_api/cli/run_anomaly_detector.py`：CLI 入口，呼叫 `anomaly.detect_and_quarantine()` 一輪即退出（適合 K8s CronJob）
- [ ] T026 [US4] 實作 `POST /admin/allocations/{id}/unquarantine` 端點於 `src/ai_api/api/allocations.py`
- [ ] T027 [P] [US4] 建立 Helm template `deploy/helm/ai-api/templates/cronjob-anomaly.yaml`（每 5 分鐘 schedule，可由 values 控制 enable/interval）
- [ ] T028 [P] [US4] 修改 `deploy/helm/ai-api/values.yaml`：加 `anomalyDetector.enabled` + `schedule`（預設 `*/5 * * * *`）

**Checkpoint**：突發用量自動止血；管理員有 unquarantine 工具。

---

## Phase 7: US5 — Container hardening (P2)

**Goal**：distroless image + readOnlyRootFilesystem + capabilities drop。
**Independent Test**：見 quickstart §5（docker 嘗試 `sh` 失敗、嘗試寫 `/etc` 失敗）。

### Tests for US5
- [ ] T029 [P] [US5] 整合測試 `tests/integration/test_us5_container_security.py`：
   - 用 `docker image inspect` 解析 entrypoint 含 python3
   - 嘗試 `docker run --rm image sh` → 失敗
   - 嘗試 `docker run --rm image ls` → 失敗（distroless 無 ls）
   - （標記 skipif Docker 不可用）

### Implementation for US5
- [ ] T030 [US5] 改寫 `deploy/docker/Dockerfile`：
   - builder 階段不變
   - runtime 改為 `FROM gcr.io/distroless/python3-debian12:nonroot@sha256:<digest>`（pinned by digest）
   - 加 `/app/healthcheck.py` 純 Python script，HEALTHCHECK 用之
   - entrypoint 改 `["python3", "-m", "uvicorn", "ai_api.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- [ ] T031 [US5] 建立 `deploy/docker/healthcheck.py`：urllib.request 打 `/healthz`，非 200 即 sys.exit(1)
- [ ] T032 [US5] 修改 `deploy/helm/ai-api/templates/deployment.yaml`：
   - container `securityContext`: `readOnlyRootFilesystem: true`、`allowPrivilegeEscalation: false`、`capabilities.drop: ["ALL"]`
   - 加 `volumeMounts` + `volumes` 兩個 emptyDir：`/tmp` 與 `/home/nonroot/.cache`

**Checkpoint**：容器層次最小權限就緒。

---

## Phase 8: US6 — Per-IP rate limit (P2)

**Goal**：補強現有 per-email rate limit，加 per-IP 維度。
**Independent Test**：見 quickstart §6（同 IP 10 不同 email 各失敗 1 次 + 第 11 → 429）。

### Tests for US6 (TDD red)
- [ ] T033 [P] [US6] 契約測試 `tests/contract/test_perip_ratelimit.py`：
   - 同 IP 10 個 email 各失敗 1 次 → 第 11 次回 429
   - 鎖定期內合法登入仍拒

### Implementation for US6
- [ ] T034 [P] [US6] 擴充 `src/ai_api/auth/ratelimit.py`：新增 `is_ip_locked(ip)`；service 在 login 流程中先檢查 per-email、再檢查 per-IP
- [ ] T035 [US6] 修改 `src/ai_api/api/auth.py` 的 `local_login`：呼叫 `is_ip_locked(client_ip)` 並回 429 + `rate_limited` 若鎖
- [ ] T036 [US6] 為 `AttemptOutcome` 加 `locked_ip` 值（或重用 `locked`）— 取決於是否需要區分 per-email-lock vs per-IP-lock

---

## Phase 9: Polish & Cross-Cutting

- [ ] T037 跑全套測試 `uv run pytest -q`，確認既有 Phase 1+2 tests 全綠 + 新增測試全綠
- [ ] T038 [P] 更新 `.github/workflows/ci.yml` 對新增的測試類別（若需 Docker）加判斷或單獨 job
- [ ] T039 [P] 在 `tests/contract/test_no_key_leak_global.py` 增補新錯誤碼情境（`provider_not_allowed`、`allocation_quarantined`）
- [ ] T040 [P] 更新 `README.md`：加「Phase 2.5 Hardening 已上線」段落
- [ ] T041 跑 `quickstart.md` §1~§6 逐項驗證，把結果寫入 `specs/003-hardening/quickstart-run-notes.md`
- [ ] T042 對 `quickstart-run-notes.md` 標 SC-001~SC-008 通過情形
- [ ] T043 在 `knowledge/vision.md` 把階段 2.5 各 checkbox 由 `[ ]` → `[x]`

---

## Dependencies

```
Phase 1 Setup
   │
   ▼
Phase 2 Foundational (Alembic 0003 + enum 擴充)
   │
   ├─→ Phase 3 (US1 provider allowlist)        ←─ 應用層，獨立可推進
   ├─→ Phase 5 (US3 Trivy CI)                  ←─ CI-only，完全獨立
   ├─→ Phase 8 (US6 per-IP rate limit)         ←─ 應用層，獨立
   │
   ├─→ Phase 6 (US4 anomaly + quarantine)      ←─ 依 Phase 2 的 enum
   │       │
   │       ▼
   │  Phase 4 (US2 NetworkPolicy) + Phase 7 (US5 container hardening)
   │  ↑ 這兩個彼此獨立，且只動 deploy/ 不動 app 程式
   │
   ▼
Phase 9 Polish
```

**Story dependencies**：
- **US1 / US3 / US5 / US6** 全部相互獨立 — 可四線並行
- **US4** 依 Phase 2 的 enum 擴充
- **US2** 完全是 Helm template — 不阻擋其他 story

---

## Parallel Execution Opportunities

- **Phase 1**：T002 / T003 並行
- **Phase 2**：T005 與 T004 並行；T006 收尾
- **Phase 3 (US1)**：T007 / T008 測試並行；T009 / T010 並行；T011 / T012 循序（同檔）
- **Phase 4 (US2)**：T013 測試先；T014 / T015 / T016 並行（不同檔案）
- **Phase 5 (US3)**：T017 / T018 並行（不同檔案）
- **Phase 6 (US4)**：T019 / T020 / T021 測試並行；T022 / T023 / T024 並行；T025 / T026 / T027 / T028 並行（不同檔案）
- **Phase 7 (US5)**：T029 測試先；T030 / T031 / T032 順序（健康檢查腳本要在 Dockerfile 加 COPY 之前）
- **Phase 8 (US6)**：T033 測試先；T034 / T035 / T036 順序（共用檔案修改）
- **Phase 9**：T038 / T039 / T040 並行；T041~T043 循序

---

## Implementation Strategy

### MVP 建議優先序

1. **Phase 1 + 2**（基底）
2. **US3 Trivy**（純 CI 設定，最快上線；無需測試環境）
3. **US1 provider allowlist**（應用層強約束，馬上提升安全等級）
4. **US6 per-IP rate limit**（小範圍補強）
5. **US4 anomaly + quarantine**（最大投入；提供事後止血）
6. **US2 NetworkPolicy + US5 container hardening**（叢集層，最後驗證）

### TDD 紀律

每個 story 內測試任務先完成並 commit（失敗 commit），再 commit 實作（綠 commit）。
SC-008 要求 git 歷史可驗證此順序。

### Risk Hot Spots

1. **Trivy 首次跑可能爆出既有 CVE** — 預期會看到一些；若無法立刻修，把 id 加進 `.trivyignore` 並在 PR 寫理由（FR-007 設計即考慮此）。
2. **NetworkPolicy 在 k3s 上若 CNI 不支援** — manifest 套用會成功但無效果。Phase 4 完成後需手動在叢集驗證一次 `kubectl exec` 測網路。
3. **distroless 切換** — 第一次 build 後若應用啟動失敗，可能是某 dependency 需要 `libffi.so` 等系統檔；distroless `python3-debian12` 已內含 Python 標準庫所需，但 LiteLLM 的某些可選依賴可能不行；plan T030 完成後立即跑 `docker run` 驗證健康。
4. **anomaly threshold 太敏感** — 預設值（10x + 100 min calls）對小規模專案可能太寬，對大規模可能太緊。第一週上線後人工觀察 audit log，可能需調 Settings。

---

## Format Validation

✅ 全部 43 個任務符合 checklist 格式
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3–8 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
