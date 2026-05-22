# Feature Specification: 階段 2.5 — 安全加固 (Hardening)

**Feature Branch**: `003-hardening`
**Created**: 2026-05-22
**Status**: Draft
**Input**: User description: "階段 2.5 hardening — 雙層 provider allowlist + K8s NetworkPolicy + Trivy + per-allocation quota/警報，加 securityContext / per-IP rate limit / distroless"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 管理員可限定哪些 AI 供應商可被使用 (Priority: P1)

擁有者開放本平台給組織成員之前，要能明確說「我們只允許呼叫 Azure OpenAI；
其他供應商即使 LiteLLM 支援，也禁止」。這保護「成本可預期」與「資料留在
合規供應商」兩個關鍵承諾。

**Why this priority**：vision 預期未來會接更多供應商（Anthropic、Gemini…），
但「未明示允許」必須等於「拒絕」。第一道應用層 allowlist 是雙層防禦的
最強約束，CP 值最高。

**Independent Test**：在設定中允許 `azure`，呼叫 `azure/<model>` 成功；
呼叫 `anthropic/claude-3` 即使 LiteLLM 可路由也回 403 + `provider_not_allowed`。

**Acceptance Scenarios**:

1. **Given** `allowed_providers = ["azure"]`，**When** 持分配憑證對
   `/v1/chat/completions` 呼叫已綁定模型，**Then** 成功代理；CallRecord
   標記 provider=`azure`。
2. **Given** 同一設定，**When** 呼叫指定 `model="anthropic/claude-3"`（即使
   LiteLLM 能 route），**Then** 回 403、`error.code = provider_not_allowed`、
   CallRecord outcome 為新增的 `rejected_provider`。
3. **Given** 管理員把設定改為 `allowed_providers = ["azure", "anthropic"]`，
   **When** 重啟（或熱重載），**Then** 上述兩個呼叫都成功。

---

### User Story 2 - 攻擊者突破 RCE 仍打不出去 (Priority: P1)

即使應用層被 RCE，pod 也不該能對外發起任意連線（防 SSRF、防偷渡資料、防
向雲端 metadata service 偷取角色 token）。

**Why this priority**：縱深防禦的關鍵層。即使所有應用層保護被繞過，K8s
NetworkPolicy 也能切斷攻擊者的後續路徑。

**Independent Test**：部署後從 pod 內試圖：(a) 連 `8.8.8.8:80` HTTP — 阻擋；
(b) `curl http://169.254.169.254/latest/meta-data/` — 阻擋；(c) `curl
https://api.openai.com` HTTPS — 允許（443/TCP 開放）；(d) Postgres 5432 連
DB host — 允許。

**Acceptance Scenarios**:

1. **Given** NetworkPolicy 已套用，**When** pod 內 `curl http://8.8.8.8` (port 80)，
   **Then** 連線逾時 / refused。
2. **Given** 同上，**When** `curl http://169.254.169.254/` (cloud metadata)，
   **Then** 連線拒絕。
3. **Given** 同上，**When** 應用呼叫 LiteLLM → Azure OpenAI (443)，**Then**
   成功（DNS 與 443/TCP 通）。
4. **Given** 同上，**When** Pre-install migration Job 連 Postgres，**Then**
   成功。

---

### User Story 3 - 已知 CVE 的 image 不會進入 main (Priority: P1)

依賴鏈很長（LiteLLM + 其下游），定期會冒出 CVE。CI 必須在 PR 階段就擋住
含 HIGH/CRITICAL CVE 的 image，不讓它們進 main / 不會被 deploy。

**Why this priority**：純被動防禦，CP 值極高 — 一次設定持續受益。

**Independent Test**：故意把 `pyproject.toml` 釘到一個已知有 HIGH CVE 的
舊版套件 → 開 PR → CI Trivy job 失敗。

**Acceptance Scenarios**:

1. **Given** 一個 PR 引入含 HIGH/CRITICAL 漏洞的 base image 或套件，
   **When** CI 跑到 Trivy 步驟，**Then** job 失敗、PR 自動阻擋合併。
2. **Given** 同 PR 修正後（升級到無已知 CVE 的版本），**When** 重跑 CI，
   **Then** Trivy 通過、PR 可合併。
3. **Given** 有合理原因要 ignore 某個 CVE（例：實際不受影響），**When**
   把 CVE id 加到 `.trivyignore` 並在 PR 描述記錄理由，**Then** Trivy 允許
   通過。

---

### User Story 4 - 分配被竊用會被及時發現並止血 (Priority: P1)

如果某分配憑證外洩，攻擊者可能會大量呼叫直到耗盡組織預算。系統必須能偵
測「某分配 1 小時內用量遠超過自身基線」並自動降級該分配 + 通知擁有者。

**Why this priority**：這是「被攻破後」的關鍵止血機制。沒有它，攻擊者可
在發現前燒掉大量 token。

**Independent Test**：建分配 → 模擬正常使用 N 次取得 baseline → 突然 1 小
時內呼叫 N×10 次 → 觀察該分配自動降為 quota=0 並寫入 `auth_audit_log`
事件。

**Acceptance Scenarios**:

1. **Given** 分配 A 過去 24 小時平均 1 小時 100 calls，**When** 最近 1 小時
   突發 1000 calls，**Then** 系統自動把 A 標為 `quarantined` 並通知擁有者
   （管理員可看到一筆 `allocation_quarantined` 審計事件）。
2. **Given** 分配被 quarantine，**When** 持原 token 再呼叫，**Then** 立即
   回 403 + `error.code = allocation_quarantined`。
3. **Given** 擁有者人工 review 後解除，**When** 對該分配呼叫 unquarantine
   API，**Then** 恢復可用；事件同樣寫入審計。

---

### User Story 5 - Pod 與 image 更難被 RCE / 利用 (Priority: P2)

容器層次的最小權限：唯讀根檔系統、無 capabilities、distroless（無 shell）。
這些不擋住「應用層 RCE」的初次發生，但會讓攻擊者**拿到 RCE 後幾乎沒事
能做**。

**Why this priority**：增量防禦，CP 值高但不阻擋 P1；可與其他 story 並
行。

**Independent Test**：用 `docker run --rm -it image sh` 應該失敗（無 shell）；
pod 在 K8s 上以 non-root 跑（已實作）+ readOnlyRootFilesystem（待加）；
任何試圖寫 `/`、`/tmp/foo` 應該失敗。

**Acceptance Scenarios**:

1. **Given** distroless image，**When** 嘗試 `docker exec ... sh`，**Then**
   執行檔不存在，無法進入互動 shell。
2. **Given** Pod 啟用 `readOnlyRootFilesystem: true`，**When** 嘗試寫入
   `/etc/some-file`，**Then** 失敗（只有 `emptyDir` 掛載的目錄可寫）。
3. **Given** Pod 啟用 `capabilities.drop: [ALL]`，**When** 任何需要 cap 的
   操作（例：bind <1024 port），**Then** 失敗。

---

### User Story 6 - 多 email 失敗也擋得住 (Priority: P2)

現有 rate limit 只看 per-email，攻擊者可換 email 一直試。補上 per-IP 維度，
擋掉 password spraying。

**Why this priority**：補強現有 rate limit；如果 P1 全部完成這個就是錦上添
花，因此 P2。

**Independent Test**：從同一 IP 對 10 個不同 email 各嘗試 1 次錯密碼（共
10 次），第 11 次應該被擋。

**Acceptance Scenarios**:

1. **Given** 同一 IP 在 60 秒內對任意 email 累計 ≥ 10 次失敗，**When** 第
   11 次嘗試（任何 email），**Then** 回 429，鎖該 IP 15 分鐘。
2. **Given** 該 IP 在鎖定期內，**When** 嘗試合法登入（正確密碼），**Then**
   仍被拒（信任先暫停）。

### Edge Cases

- Allowlist 設為空 `[]`：等同關閉代理 — fail-fast，service 啟動時即拒絕，
  避免「忘了設」導致全部失敗變沉默。
- per-allocation 異常檢測 cold-start：分配建立後 24 小時內無 baseline 可比
  — 採「絕對門檻」(例：1 小時 ≥ 10000 calls 也觸發) 作為保險，且不觸發
  Quarantine 而是發 warning（避免新使用者一上線就被誤鎖）。
- NetworkPolicy 與 in-cluster 服務名稱：如果 Postgres 在同 namespace，pod-
  to-pod 走 ClusterIP；NetworkPolicy 必須以 podSelector 或 namespaceSelector
  描述，而非寫死 IP。
- Trivy 在新 CVE 公佈時可能讓所有 PR 都失敗：必須允許 `.trivyignore`，並
  要求 PR 描述記錄忽略原因（避免無聲忽略）。

## Requirements *(mandatory)*

### Functional Requirements

#### Provider Allowlist
- **FR-001**: `Settings` MUST 提供 `allowed_providers` 清單欄位（預設
  `["azure"]`）。
- **FR-002**: Proxy 路徑 MUST 在 routing 前解析請求 model 字串的 provider
  前綴（例 `azure/...`、`anthropic/...`）；若 provider 不在 allowlist 中，
  立即 403 + `error.code = provider_not_allowed`，不轉發給 LiteLLM。
- **FR-003**: Allowlist 為空 `[]` MUST 觸發 service 啟動失敗（fail-fast），
  避免「沉默全拒」。

#### Network egress
- **FR-004**: Helm chart MUST 內建一份 NetworkPolicy template（可選開關，
  預設 enabled），策略為：
  - Egress: allow DNS (UDP/53), TCP 443 to 0.0.0.0/0, TCP 5432 to Postgres
    pod/namespace
  - Egress: **explicit deny** 169.254.0.0/16（cloud metadata + link-local）
  - Egress: 其餘 deny
  - Ingress: 允許 cluster 內 ClusterIP / Ingress controller 連 8000/TCP
- **FR-005**: NetworkPolicy MUST 不阻礙 Pre-install migration Job 連 Postgres。

#### CVE scanning
- **FR-006**: CI MUST 在 PR build image 後跑 Trivy scan：HIGH + CRITICAL
  severity 觸發 job 失敗。
- **FR-007**: 系統 MUST 支援 `.trivyignore` 機制，可顯式忽略特定 CVE id；
  PR 模板要求被忽略的 CVE 必須附理由。

#### Per-allocation quota & anomaly
- **FR-008**: 新增背景 job `anomaly_detector`：每 N 分鐘掃描 CallRecord，
  對 active allocations 計算「最近 1 小時用量 vs 過去 24 小時 baseline」。
- **FR-009**: 觸發條件（可設定，預設）：
  - 最近 1 小時 calls ≥ baseline × 10 **且** ≥ 100 calls，OR
  - cold-start 期間最近 1 小時 calls ≥ 10000（絕對門檻）
  → 寫入 audit + 把 allocation status 改為新增的 `quarantined`
- **FR-010**: Allocation 表 MUST 加 `status` enum 擴充值 `quarantined`；
  proxy 對 `quarantined` 分配回 403 + `error.code = allocation_quarantined`。
- **FR-011**: 管理員 API MUST 提供 `POST /admin/allocations/{id}/unquarantine`
  端點解除隔離。
- **FR-012**: 系統 MUST 在 Quarantine 觸發時呼叫通知 hook（首階段：寫 audit
  event；email/Slack 整合留後階段）。

#### Per-IP rate limit
- **FR-013**: `PasswordAttempt` 表 MUST 支援以 `source_ip` 為維度的查詢；
  rate limit 服務 MUST 同時檢查 (a) per-email、(b) per-IP（同 IP 60s 內 ≥
  10 次失敗即鎖 15 分鐘）。

#### Container hardening
- **FR-014**: Helm Deployment template MUST 預設 `readOnlyRootFilesystem: true`、
  `allowPrivilegeEscalation: false`、`capabilities.drop: ["ALL"]`。
- **FR-015**: Dockerfile MUST 改用 **distroless** base image（如
  `gcr.io/distroless/python3-debian12`）；healthcheck 若依賴 shell 需重寫
  為內建 Python script。
- **FR-016**: 應用必須能在 `readOnlyRootFilesystem=true` 下啟動（必要的
  暫存目錄如 `/tmp` 改掛 `emptyDir`）。

### Key Entities

無新主領域實體。延伸：
- **Allocation**：`status` enum 多加一值 `quarantined`。
- **PasswordAttempt**：欄位不變；新查詢「per-IP 60s 內失敗計數」。
- **AuthAuditLog**：新增 event_type 列舉值 `allocation_quarantined` 與
  `allocation_unquarantined`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 對非 allowlist provider 的 100 次呼叫 → 100 次回 403
  `provider_not_allowed`；不觸及上游。
- **SC-002**: 從 pod 內測試 4 種網路情境：metadata IP / 任意 HTTP / 上游
  HTTPS / Postgres，分別 deny/deny/allow/allow，4/4 符合預期。
- **SC-003**: 故意引入含 HIGH CVE 的 image → CI Trivy job 失敗、PR 阻擋；
  修正後通過。
- **SC-004**: 用 synthetic load 模擬「正常 baseline 100 calls/hr + 突發
  1000 calls/hr」→ ≤ 5 分鐘內 allocation 進入 `quarantined`、後續呼叫即拒、
  audit 留紀錄。
- **SC-005**: per-IP rate limit：同 IP 10 個 email 各 1 次失敗 + 第 11 次 →
  HTTP 429；該 IP 15 分鐘內所有登入嘗試皆拒。
- **SC-006**: 對部署後的 pod 執行 `kubectl exec ... -- sh` → 失敗（無 shell）；
  嘗試 `touch /tmp/x` → 失敗（readOnlyRootFilesystem，除非有 emptyDir 掛載）。
- **SC-007**: 所有 Phase 1+2 既有 tests 持續綠（不能因 hardening 引入回歸）。
- **SC-008**: 所有 FR 在 git 歷史中可見「測試 commit 早於對應實作 commit」
  （延續 SC-008 of 階段 1 的 TDD 紀律）。

## Assumptions

- **NetworkPolicy 在 k3s 上需先啟用 CNI 支援**：k3s 預設 Flannel 不支援
  NetworkPolicy；本階段假設叢集已切換到 Flannel + kube-router 或 Calico/
  Cilium（k3s 啟動參數 `--flannel-backend=...`）。若叢集不支援，本階段
  仍交付 manifest，但實際生效要靠叢集端配置。
- **Trivy 整合用 GitHub-hosted runner 的 `aquasecurity/trivy-action`**：免費、
  社群維護；DB 自動 sync。
- **Quarantine 通知首階段只寫 audit**：email/Slack hook 留後續；管理員需
  定期查看 audit dashboard 或在階段 3 UI 加 banner 提示。
- **異常偵測背景 job 用簡單 Python `asyncio` task**：不引入 Celery / RQ，
  跑在主 process 內或獨立 K8s CronJob（plan 階段二選一）。
- **provider 字串解析規則**：以第一個 `/` 之前的字串為 provider；無 `/`
  視為預設 provider（按 vision 為 `azure`）。
- **distroless image 內部仍可跑 alembic / uvicorn**：兩者皆純 Python，可
  在 distroless 上跑。
