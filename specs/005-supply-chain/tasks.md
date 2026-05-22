# Tasks: 階段 2.6 — Supply Chain / Scanner Hardening

**Input**: Design documents from `/specs/005-supply-chain/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: TDD enforced（constitution + SC-007）— workflow yaml pinning 用 unit test 驗證。

## Format
`- [ ] T### [P?] [Story?] description with file path`

路徑相對 repo root：`/Users/timcsy/Documents/Projects/CCSH/AzureAI/ai-api`

---

## Phase 1: Setup

- [ ] T001 在本機跑 `gh api repos/aquasecurity/trivy-action/releases/latest --jq .tag_name` 取最新 trivy-action tag；用 `gh api "repos/aquasecurity/trivy-action/commits/<tag>" --jq .sha` 取對應 commit SHA；同樣方式取其他 5 個 action 的 SHA。輸出記錄於 PR 描述。
- [ ] T002 [P] 決定 Trivy CLI 版本（research.md §2：建議 `v0.58.1`）；在 PR 描述標註選擇理由

---

## Phase 2: Foundational

- [ ] T003 撰寫 `tests/unit/test_workflow_pinning.py`：
   - 載入 `.github/workflows/*.yml`，對每個 `uses:` 行斷言匹配
     `^[a-z0-9-_./]+@[0-9a-f]{40}$`
   - 對 `image.yml` 與 `scheduled-scan.yml` 內 Trivy action step 斷言
     `with.version` 欄位存在且為 `^v\d+\.\d+\.\d+$`

**Checkpoint**：測試先寫好且全部 fail（既有 yaml 有 `@master` + `@v0.24.0` 等
非 SHA ref）。

---

## Phase 3: US1 — Pinning (P1)

**Goal**：所有 action ref 變 commit SHA + Trivy CLI 版本 pin。
**Independent Test**：`tests/unit/test_workflow_pinning.py` 全綠。

- [ ] T004 [US1] 修改 `.github/workflows/image.yml`：把所有 `uses:` 從 tag/branch ref 改為 commit SHA（依 T001 結果），每行末尾加 `# v<tag>` 註解標 semver
- [ ] T005 [US1] 修改 `.github/workflows/image.yml`：trivy-action step 加 `with.version: 'v0.58.1'`（依 T002）
- [ ] T006 [US1] 確認 `uv run pytest tests/unit/test_workflow_pinning.py` 全綠

**Checkpoint**：US1 完成。`grep -rE '@(master|main)$' .github/workflows/` 為空。

---

## Phase 4: US2 — Scheduled rescan (P1)

**Goal**：每週重掃 main image，發現新 CVE 自動開 issue。
**Independent Test**：`gh workflow run scheduled-scan.yml` → 跑完依結果開 issue（或 clean）。

- [ ] T007 [US2] 建立 `.github/workflows/scheduled-scan.yml`：
   - `on: schedule: cron '0 6 * * MON'` + `workflow_dispatch`
   - 步驟：登入 ghcr → `gh run list --workflow=image.yml --status=success --limit=1` 取最新 commit short SHA → 組 image ref `ghcr.io/timcsy/ai-api:sha-<short>`
   - 跑 trivy-action（同 image.yml 的 pinned SHA + version）對該 image
   - 若 exit-code=1：用 trivy `--format json` 取 CVE list；對每個 CVE id 跑去重邏輯（research.md §3）並開 issue
- [ ] T008 [US2] 確認 workflow 通過 yaml-pinning 測試（T003 已涵蓋）
- [ ] T009 [US2] 文件：在 PR 描述附「手動觸發驗證」步驟（依 quickstart §3）

**Checkpoint**：US2 完成。可手動觸發；首次跑會視 image 狀態決定是否開 issue。

---

## Phase 5: US3 — fs scan fail-fast (P2)

**Goal**：build 之前先掃 lockfile，省迭代時間。

- [ ] T010 [US3] 修改 `.github/workflows/image.yml`：在 `docker/build-push-action` 之前插入一個 trivy-action step，`scan-type: fs`、`scan-ref: .`、`severity: HIGH,CRITICAL`、`exit-code: '1'`、`ignore-unfixed: true`、`trivyignores: .trivyignore`

---

## Phase 6: US4 — SBOM (P2)

**Goal**：每個 image build 附 CycloneDX SBOM artifact。

- [ ] T011 [US4] 修改 `.github/workflows/image.yml`：在 image scan step 之後加 trivy-action step，`format: cyclonedx`、`output: sbom.cdx.json`
- [ ] T012 [US4] 加 `actions/upload-artifact` step（pinned SHA），upload `sbom.cdx.json`，`retention-days: 90`

---

## Phase 7: Polish

- [ ] T013 [P] 修改 `.github/PULL_REQUEST_TEMPLATE.md`：加 Supply chain 章節（research.md §6）
- [ ] T014 [P] 建立 `docs/supply-chain.md`：寫升級 pinned SHA 的 SOP + issue 處理流程 + Trivy 版本升級 checklist
- [ ] T015 跑 `uv run pytest -q` 確認既有 134 tests + 新 workflow-pinning test 全綠
- [ ] T016 將本 PR 描述附上 quickstart §1 拿到的所有 pinned SHA 列表（透明審查）
- [ ] T017 PR 合進 main 後手動 `gh workflow run scheduled-scan.yml` 驗 SC-003；結果寫入 `specs/005-supply-chain/quickstart-run-notes.md`
- [ ] T018 在 `knowledge/vision.md` 將階段 2.6 各 checkbox 由 `[ ]` → `[x]`

---

## Dependencies

```
T001 (find SHAs)
   │
   ▼
T002 (decide Trivy version)
   │
   ▼
T003 (write pinning test, RED)
   │
   ▼
Phase 3 (US1 — pin refs + version)  ← test goes GREEN
   │
   ├─→ Phase 4 (US2 scheduled-scan) — 獨立，可並行
   ├─→ Phase 5 (US3 fs scan)
   └─→ Phase 6 (US4 SBOM)
       │
       ▼
   Phase 7 Polish
```

**Story dependencies**：
- **US1** 是基礎；T003 寫了測試後 US1 必先做（否則其他改動會違反 pinning 測試）
- **US2/US3/US4** 互相獨立，可並行
- T014~T018 polish 步驟需所有 user story 完成

---

## Parallel Execution Opportunities

- **Phase 1**：T001 / T002 並行（不同查詢）
- **Phase 2**：T003 單一檔
- **Phase 3 (US1)**：T004 / T005 同檔須循序（避免衝突）；T006 驗證
- **Phase 4-6 (US2/US3/US4)**：彼此並行；都動 image.yml 與 scheduled-scan.yml 須循序提交以免 merge conflict
- **Phase 7**：T013 / T014 並行

---

## Implementation Strategy

### MVP 建議

**Phase 1+2+3** 即達 MVP（US1）— 消除 mutable ref 是最高 CP 值。可分兩個 PR：
- PR A：T001~T006（pinning + test）
- PR B：US2+US3+US4 + polish

但本階段範圍小，**單一 PR 完成 18 tasks** 更實際。

### TDD 紀律

T003 先寫並 commit（fail）→ T004~T005 改 yaml → 測試轉綠 commit。SC-007
延續 git 歷史「test < impl」順序。

### Risk Hot Spots

1. **gh api 查 release SHA 拿到的是 tag object SHA 而非 commit SHA**：研究文已記載；用 `commits/<tag>` 端點才對。實作時若拿到不是 40 字 hex 即報錯。
2. **scheduled-scan 第一次跑可能因為 `.trivyignore` 未涵蓋而開很多 issue**：可接受，視為 baseline；逐一審查決定加 ignore 或修。
3. **trivy CLI v0.58.1 與舊 v0.50.x 行為差異**：版本升級時可能誤判某些 CVE；首次 pin 後跑一次完整 image scan 觀察輸出。
4. **PR 內 yaml 改動撞 PR #4（004-usage-billing）merge**：本階段建議在 PR #4 合進 main 後再開 PR；避免 yaml 衝突。

---

## Format Validation

✅ 全部 18 任務符合 `- [ ] T### [P?] [USx?] 描述 + 檔案路徑`
✅ Setup / Foundational / Polish 無 [US] 標籤
✅ Phase 3-6 任務皆帶對應 [USx] 標籤
✅ 所有任務含明確檔案路徑
