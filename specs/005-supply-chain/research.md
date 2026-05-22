# Phase 0 Research: 階段 2.6 — Supply Chain Hardening

---

## 1. 如何找 action 的 commit SHA

**決策**：用 `gh api` 從 release tag 反查 commit SHA：

```bash
# 找最新 release tag
LATEST=$(gh api repos/aquasecurity/trivy-action/releases/latest --jq .tag_name)
# 反查該 tag 指向的 commit
gh api repos/aquasecurity/trivy-action/git/refs/tags/$LATEST --jq .object.sha
# 若 object 是 tag object，需再解一層
gh api repos/aquasecurity/trivy-action/git/tags/<sha> --jq .object.sha
```

實務做法：直接 `gh api repos/<repo>/commits/<tag>` 拿 `.sha` 最簡。

**理由**：避免人為手寫錯字；可寫成 PR 模板的指令。

**已評估**：
- 從 GitHub UI 複製：易出錯
- 直接信任 `@vX.Y.Z` semver tag：tag 可被 force-push（雖然 GitHub 不鼓勵，
  但理論上可能）— pin commit SHA 才是真的 immutable

---

## 2. Trivy CLI 版本選擇

**決策**：本階段 pin 到 `v0.58.1`（撰寫時最新穩定版）。

**理由**：
- v0.58.x 系列出來 6 個月以上，CVE DB schema 穩定
- pin 後跨團隊跑出來的結果一致
- 升級走 PR + 過 CI gate

**已評估**：
- `latest`：Phase 2.5 已知會冒出新 CVE 然後 fail；我們已踩過
- v0.50.x（舊）：可能漏掉新 vuln schema

**升級 SOP**（寫進 `docs/supply-chain.md`）：
1. 看 trivy-action 與 trivy 各自的 release notes
2. PR 改 yaml；等 CI 跑（會用新版重新掃 image）
3. 若新版抓出新 CVE：合理就修，不合理就加 `.trivyignore` 並寫理由

---

## 3. Issue 去重策略

**決策**：title 含 `[CVE-YYYY-NNNNN]` 模式 + GitHub label `cve` + 直接用
`gh issue list --search 'is:open in:title "[CVE-XXXX]"'` 比對。

**workflow 片段**：

```bash
# 對每個 HIGH/CRITICAL CVE id
existing=$(gh issue list --state open --search "[$cve] in:title" --json number --jq '.[0].number')
if [ -z "$existing" ]; then
  gh issue create --title "[$cve] $summary" --label cve,security --body "$report"
fi
```

**理由**：
- 不需 sqlite / 外部 store；GitHub issues 本身即去重來源
- label 讓 issue 可被批次查詢／關閉

**已評估**：
- 用 `peter-evans/create-issue-from-file`：需多裝 action；標準 `gh` CLI 已
  夠用
- 不去重：噪音太大；維運者會習慣性忽略

---

## 4. SBOM 生成方式

**決策**：用 Trivy 內建 `--format cyclonedx` 直接生成：

```yaml
- name: Generate SBOM
  uses: aquasecurity/trivy-action@<sha>
  with:
    scan-type: image
    image-ref: ${{ steps.build.outputs.imageid }}
    format: cyclonedx
    output: sbom.cdx.json
- uses: actions/upload-artifact@<sha>
  with:
    name: sbom
    path: sbom.cdx.json
    retention-days: 90
```

**理由**：
- 一個工具兩用（scan + SBOM），少一個 action 要 pin
- CycloneDX 是業界主流（vs SPDX）；JSON 格式可被 jq 處理

**已評估**：
- `anchore/sbom-action`：等效；多裝一個 action
- 自寫 script 解 site-packages：手工活、易漏

---

## 5. 「最新成功 build 的 image」如何取得（scheduled-scan）

**決策**：用 `gh api` 查最新 image build workflow 的成功 run，取對應 commit
short SHA，組合成 `ghcr.io/timcsy/ai-api:sha-<short>`：

```bash
SHA=$(gh run list --workflow=image.yml --status=success --limit=1 \
      --json headSha --jq '.[0].headSha[0:7]')
IMAGE="ghcr.io/timcsy/ai-api:sha-$SHA"
```

**理由**：
- 寫死 `:main` 有 race（剛 push 但 image 還沒 build）
- `sha-<short>` tag 由現有 metadata-action 已自動產生（Phase 2.5）

**已評估**：
- 取 `:latest` tag：我們的 metadata-action 沒設這個 tag
- 取 OCI digest（`@sha256:...`）：更精準但多一步 query

---

## 6. PR 模板的擴充

**決策**：在既有 `.github/PULL_REQUEST_TEMPLATE.md` 加一節「Supply chain」：

```markdown
## Supply chain
- [ ] 我沒有用 mutable ref（`@master`/`@main`）；新 action 已 pin commit SHA
- [ ] 若改了 Trivy 版本或 trivy-action ref，附上 release notes 連結與
      pinned SHA 來源指令
- [ ] 若加了 `.trivyignore` 條目：見既有「Security checklist」一節
```

---

## 7. NEEDS CLARIFICATION

無未決。
