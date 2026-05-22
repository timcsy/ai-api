# Implementation Plan: 階段 2.6 — Supply Chain / Scanner Hardening

**Branch**: `005-supply-chain` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-supply-chain/spec.md`

## Summary

純 GitHub Actions / workflow 變更，無新 source code、無新依賴、無新 DB。

- **image.yml** 改寫：把所有 `uses:` 改 commit SHA；Trivy CLI 版本 pin；
  在 docker build 之前先跑 `scan-type: fs`；build 後產 CycloneDX SBOM。
- **scheduled-scan.yml** 新增：每週一 06:00 UTC + workflow_dispatch；拉
  「最新成功 build 的 image」掃描；HIGH/CRITICAL 自動開 issue（去重）。
- 文件：`docs/supply-chain.md` 簡述 pinned 升級 SOP 與 issue 處理流程。

## Technical Context

**Language/Version**: GitHub Actions workflow YAML（無 source code 變更）
**Primary Dependencies**：
- `aquasecurity/trivy-action` （已有，改 ref）
- `actions/upload-artifact`（既有）
- `actions/github-script` 或 `gh` CLI（issue 去重）
- Trivy CLI（透過 action）— 用 `with.version` pin
**Storage**: 無
**Testing**:
- `tests/contract/test_workflow_pinning.py`：parse workflow YAML，斷言所有
  `uses:` 為 SHA 形式 + Trivy 版本 pin
- 純 workflow 結構測試（無需 runtime）；既有 134 tests 不變
**Target Platform**: GitHub Actions Linux runner
**Project Type**: CI/CD config（沿用既有 web-service 倉庫）
**Performance Goals**：
- fs scan ≤ 30 秒（已測 lockfile 不大）
- scheduled-scan 一輪 ≤ 5 分鐘
**Constraints**：
- 不引入新工具鏈（CycloneDX 由 Trivy 內建生成；issue 操作走 `gh` CLI）
- 不改變 Phase 2.5 既有 Trivy 行為（fail on HIGH/CRITICAL + `.trivyignore`）
**Scale/Scope**：≤ 5 workflows、≤ 10 個 `uses:` ref 需 pin

## Constitution Check

| 原則 | 對應證據 | 通過？ |
|---|---|---|
| I. Test-First | 新增 workflow yaml 結構測試（pinned-ref regex）先寫 | ✅ |
| II. Contract-First | 本階段無 API；workflow 的「契約」是 yaml schema + spec FR | ✅ |
| III. 整合測試覆蓋外部依賴 | Trivy CLI 由 action 跑；scheduled-scan workflow 可手動觸發驗證 | ✅ |
| IV. 可觀測性 | 失敗自動開 GitHub issue（FR-006）；issue 即 audit 紀錄 | ✅ |
| V. YAGNI | 不引入 cosign / KMS / 自架 trivy server / Slack；全部 NON-GOAL | ✅ |

**符合 experience.md 教訓**：
- 「mutable tag」教訓首次以「Action ref」面向兌現（先前只應用於 image tag）
- 「拒絕路徑先 bind context」：scheduled-scan 開 issue 帶 CVE id + 日期 +
  reporting commit，未來看 issue 有完整上下文

**初次評估通過**，無 Complexity Tracking。

## Project Structure

### Documentation

```text
specs/005-supply-chain/
├── plan.md
├── research.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── tasks.md            # /speckit.tasks 產出
```

### Files Changed / Added

```text
.github/
├── workflows/
│   ├── image.yml                 # 既有；改：pin refs + version、加 fs scan、加 SBOM
│   └── scheduled-scan.yml        # 新增
└── PULL_REQUEST_TEMPLATE.md      # 修：加「pinned ref 升級」checkbox

docs/
└── supply-chain.md               # 新增：pinned ref 升級 SOP + issue 處理流程

tests/
└── unit/
    └── test_workflow_pinning.py  # 新：解 yaml 驗 ref 格式
```

**Structure Decision**：不新增 src/ 程式碼；測試以 yaml structure 驗證為
主，與既有 `tests/integration/test_us4_helm_template.py`（helm template
結構測試）為同類做法。

## Complexity Tracking

無待說明的偏離。

## Post-Design Re-check

| 原則 | 重評 |
|---|---|
| Test-First | workflow-pinning test 先於 image.yml 改動 → ✅ |
| Contract-First | spec FR-001~FR-010 即此階段的契約；皆有對應驗證 → ✅ |
| 整合測試覆蓋外部依賴 | `gh workflow run scheduled-scan.yml` 手動驗即可，無 CI 內 self-test 必要 → ✅ |
| 可觀測性 | issue dedup 邏輯走 `gh issue list --search`，issue 即 audit log → ✅ |
| YAGNI | 無新 service、無新元件、無新工具 → ✅ |

通過，可進入 `/speckit.tasks`。
