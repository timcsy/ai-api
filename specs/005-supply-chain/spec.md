# Feature Specification: 階段 2.6 — Supply Chain / Scanner Hardening

**Feature Branch**: `005-supply-chain`
**Created**: 2026-05-22
**Status**: Draft
**Input**: User description: "階段 2.6 supply chain hardening — pin trivy-action SHA + Trivy CLI 版本 + 排程重掃 + SBOM"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 維運者信任 CI 跑的是「我們指定的那個 Trivy」 (Priority: P1)

維運者打開 `.github/workflows/image.yml` 想知道：「這個跑的 Trivy 到底是
哪個版本？來自哪個 commit？」目前 `aquasecurity/trivy-action@master` 給不
出任何承諾 — 上游隨時可換內容。本階段把所有 action ref 與 Trivy CLI 版本
都 pin 成不可變值。

**Why this priority**：直接對應 experience.md「mutable tag」教訓。供應鏈
攻擊的第一道門。

**Independent Test**：`grep -r '@master\|@main' .github/workflows/` 必須無
匹配；`grep version: .github/workflows/image.yml` 顯示明確的 Trivy CLI 版
本。

**Acceptance Scenarios**:

1. **Given** `.github/workflows/image.yml` 中所有 `uses:` 行，**When**
   regex 檢查，**Then** 每一個 ref 都是 40 字 commit SHA（或具體 semver
   tag），**沒有** `@master` / `@main`。
2. **Given** Trivy scan step，**When** 檢查 `with.version` 欄位，**Then**
   非空且為具體 semver（例 `v0.58.1`）。
3. **Given** 既有 Trivy gate 行為（HIGH/CRITICAL 失敗 + `.trivyignore`），
   **When** PR 觸發 CI，**Then** 與 Phase 2.5 行為一致（不能因 pin 而破壞
   既有功能）。

---

### User Story 2 - 沒有人改 code 也要能抓到新公布的 CVE (Priority: P1)

main 上的 image 即使一個月沒有 commit，公佈了新 CVE 就應該主動通知。
新增排程 workflow：每週重掃 `main` image，發現新的 HIGH/CRITICAL 自動開
GitHub issue 通知。

**Why this priority**：補 Phase 2.5 的盲區 — PR-only Trivy 只在合併路徑
上跑，已合進 main 的 image 對「未來公佈的 CVE」是無感的。

**Independent Test**：手動 `gh workflow run scheduled-scan.yml` → 跑完
後若有 HIGH CVE 即看到新 issue；無則不開。

**Acceptance Scenarios**:

1. **Given** `scheduled-scan.yml` 排程設定，**When** 每週一 06:00 UTC，
   **Then** 自動觸發；同樣可由 `workflow_dispatch` 手動觸發。
2. **Given** Trivy 找到 HIGH/CRITICAL（不在 `.trivyignore`），**When**
   workflow 結束，**Then** 自動開一個 GitHub issue，title 含日期與
   CVE 數，body 含 Trivy table report 截圖或文字。
3. **Given** 相同 CVE 已存在開啟中的 issue（同 CVE id），**When** 下次掃描
   再次發現，**Then** 不重複開 issue（去重），可選擇在原 issue 加註釋
   說明「該 CVE 仍存在於 main」。
4. **Given** Trivy 找不到 HIGH/CRITICAL，**When** workflow 結束，**Then**
   不開 issue；視需要在 workflow summary 輸出「clean」訊息。

---

### User Story 3 - 在 build image 前就知道 lockfile 有問題 (Priority: P2)

build image 後再掃需要 ~30 秒 build；如果直接掃 `pyproject.toml` /
`uv.lock`，5 秒內就能 fail。對開發迴圈友善。

**Why this priority**：節省迭代時間，但 image scan 已涵蓋；屬 P2 加分項。

**Independent Test**：對含已知 CVE 的 lockfile 跑 `trivy fs --severity
HIGH,CRITICAL .` → 即刻失敗。

**Acceptance Scenarios**:

1. **Given** image.yml 在 docker build 之前先跑 `scan-type: fs`，**When**
   lockfile 含 HIGH/CRITICAL，**Then** job 在 build 之前就失敗，省去
   build 時間。
2. **Given** fs scan 通過，**When** 流程繼續，**Then** image build → image
   scan 依次執行，行為與 Phase 2.5 一致。

---

### User Story 4 - 每個 image 有可追溯的 SBOM (Priority: P2)

每個 image build 同時產出 CycloneDX 格式的 SBOM，作為 workflow artifact。
未來追溯「某個 image 用了哪個版本的 X」時不必重 build。

**Why this priority**：合規與審計需求；但短期不是核心安全防線。

**Independent Test**：image build 完成後 `gh run download` 下載 artifact
應該有 `sbom.cdx.json`；用 `cyclonedx convert` 可解析。

**Acceptance Scenarios**:

1. **Given** image build job 完成，**When** 檢查 workflow artifacts，
   **Then** 存在 `sbom.cdx.json`（CycloneDX 1.5+ 格式）。
2. **Given** SBOM 內容，**When** 用 `jq` 查詢，**Then** 含至少 `components`
   陣列且每個 component 有 `name` + `version`。
3. **Given** SBOM 寫入後，**When** push 到 main，**Then** SBOM 上傳期間
   不洩漏任何 secret（一般 SBOM 不含 secret，但作為防呆驗一次）。

### Edge Cases

- **Trivy DB 下載失敗**（網路問題）：action 本身會 retry；連續失敗應讓
  job 失敗而非 silent skip — 否則 gate 失效。
- **GitHub Actions 跑 issue dedup 時 API rate limit**：使用內建 `gh` CLI
  搭配 retry；極端情況下不開 issue 比重複開 issue 好。
- **新 pinned Trivy 版本與舊 `.trivyignore` 格式不相容**：升級 Trivy 版本
  時須驗證 `.trivyignore` 仍被尊重。
- **scheduled-scan 在 main 有未發 image 時**：例如剛 push code 但 image
  build 還沒完成 — 用「最新成功 build 的 image」而非寫死 `:main` tag，
  避免拉到舊 image。

## Requirements *(mandatory)*

### Functional Requirements

#### Pinning（核心）
- **FR-001**: `.github/workflows/image.yml` 中所有 `uses:` action ref MUST
  為 40 字 commit SHA（並以註解標註對應 semver tag 便於人類理解）。
- **FR-002**: Trivy scan step MUST 透過 `with.version: 'v0.XX.X'` pin 具體
  CLI 版本，不依賴 action 的 latest 預設。
- **FR-003**: pinned 版本升級 MUST 走 PR review；PR 描述要求說明升級理由
  與最少測試驗證項目。

#### 排程重掃
- **FR-004**: 新增 `.github/workflows/scheduled-scan.yml`，排程
  `0 6 * * MON`，並支援 `workflow_dispatch` 手動觸發。
- **FR-005**: workflow MUST 拉「最新成功 build 的 image」掃描（不寫死 `:main`
  tag，避免比對到尚未更新的舊 image）。
- **FR-006**: 找到 HIGH/CRITICAL 且不在 `.trivyignore` 的 CVE 時 MUST
  自動開 GitHub issue；title 含日期；body 含 Trivy table report 文字。
- **FR-007**: 系統 MUST 對相同 CVE id 去重 — 若已有 open issue 標記同 CVE id，
  下次掃描不開新 issue。

#### fs scan
- **FR-008**: `image.yml` MUST 在 `docker build` 之前先跑 `scan-type: fs`
  針對 `pyproject.toml` + `uv.lock`，HIGH/CRITICAL 即 fail。

#### SBOM
- **FR-009**: image build job MUST 產出 `sbom.cdx.json`（CycloneDX 1.5+）。
- **FR-010**: SBOM MUST 以 `actions/upload-artifact` 上傳，retention 至少
  90 天。

#### 不在本階段範圍
- **FR-011** (NON-GOAL): 自架 Trivy server / vuln DB mirror。
- **FR-012** (NON-GOAL): 第二 scanner（OSV / Grype）整合到 CI；vision 列為
  「季度手動」即可。
- **FR-013** (NON-GOAL): cosign image 簽章與 admission control。
- **FR-014** (NON-GOAL): 通知到 Slack / email（issue 已足夠首版）。

### Key Entities

無新領域實體；本階段全為 CI / workflow 設定變更。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -rE '@(master|main)$' .github/workflows/` → 0 命中。
- **SC-002**: 對 `image.yml` 與 `scheduled-scan.yml` 解析 yaml，每一個
  `uses:` ref 通過正規 `^[a-z0-9-]+/[a-z0-9-]+@[0-9a-f]{40}$` 驗證。
- **SC-003**: 手動 `gh workflow run scheduled-scan.yml` 跑完 ≤ 5 分鐘；
  若無 CVE：summary 顯示 clean、不開 issue；若有：自動開 issue 一筆。
- **SC-004**: 對既有 lockfile 故意引入含 HIGH CVE 的舊版套件 → fs scan step
  在 build 前 fail（≤ 30 秒 fail-fast）。
- **SC-005**: image build artifact 包含 `sbom.cdx.json`，且 `jq '.components |
  length'` ≥ 50（合理規模）。
- **SC-006**: 既有 Phase 1+2+2.5+3a 全部 134 tests + image build 不受影響
  （無回歸）。
- **SC-007**: 所有 FR 在 git 歷史中可見「測試 commit 早於對應實作 commit」
  （延續 TDD 紀律）— 本階段測試多為 workflow yaml lint / structure 驗證。

## Assumptions

- **pinned 版本來源**：每次升級時手動到 `aquasecurity/trivy-action`
  GitHub releases 頁面查最新 release 對應的 commit SHA；操作流程寫入
  PR 描述模板。
- **issue 去重以 CVE id 為 key**：使用 GitHub issue label `cve:<id>`
  或在 title 含 `[CVE-xxxx-xxxxx]` 樣式，靠 `gh issue list --search` 比對。
- **scheduled-scan 失敗時不會自動 retry**（避免噪音）；連續兩次失敗，
  外部監控（人工觀察）即可。
- **第一次跑 scheduled-scan 可能會冒出未知 CVE**：屬正常，當作 baseline；
  通過合理理由加入 `.trivyignore` 或修。
- **SBOM 不含 secret**：sample 完後人工檢查一次，確認沒有 build-time
  injected 變數混進 component metadata。
