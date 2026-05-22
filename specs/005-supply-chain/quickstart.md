# Quickstart: 階段 2.6 — Supply Chain Hardening

## 0. 先決條件

- `gh` CLI 已安裝且登入 (`gh auth status`)
- 對 repo 有 write 權限（觸發 workflow + 開 issue）
- Phase 2.5 既有 image build workflow 仍運作

## 1. 找正確的 commit SHA 來 pin（US1）

```bash
# trivy-action
LATEST=$(gh api repos/aquasecurity/trivy-action/releases/latest --jq .tag_name)
echo "Latest trivy-action release: $LATEST"
SHA=$(gh api "repos/aquasecurity/trivy-action/commits/$LATEST" --jq .sha)
echo "Commit SHA: $SHA"

# 其他 action 同樣手法
for action in actions/checkout actions/upload-artifact docker/setup-buildx-action \
              docker/login-action docker/metadata-action docker/build-push-action; do
  LATEST=$(gh api repos/$action/releases/latest --jq .tag_name)
  SHA=$(gh api "repos/$action/commits/$LATEST" --jq .sha)
  echo "$action @ $SHA  # $LATEST"
done
```

把 output 寫進 `image.yml` 與 `scheduled-scan.yml`，並在註解標示 semver tag。

## 2. 驗 pinned 結構（US1）

```bash
# 應該 0 命中
grep -rnE '@(master|main)$' .github/workflows/

# 應該全部 40-char hex
grep -hnE 'uses: ' .github/workflows/ | grep -vE '@[0-9a-f]{40}'
# 任何 output 都是 missed pin

# Trivy version 已 pin
grep -A1 'trivy-action' .github/workflows/image.yml | grep version:
```

跑 `uv run pytest tests/unit/test_workflow_pinning.py` 應該全綠。

## 3. 手動觸發 scheduled-scan（US2）

```bash
gh workflow run scheduled-scan.yml
gh run watch
```

預期：若 main 上的 image 含 HIGH/CRITICAL CVE（不在 `.trivyignore`）→ 自動
開 issue（label `cve`）；無則 workflow summary 顯示 `clean`，不開 issue。

去重驗證：再跑一次，同 CVE 不應重複開新 issue。

## 4. fs scan fail-fast 驗證（US3）

```bash
# 暫時把 pyproject.toml 釘到舊版含 HIGH CVE 的套件
# 例：cryptography==41.0.0 (假設含 CVE)
# 開 PR → CI 應該在 docker build 之前就 fail（fs scan step）

# 還原後重跑
```

## 5. SBOM 驗證（US4）

PR 合進 main 後：

```bash
RUN_ID=$(gh run list --workflow=image.yml --status=success --limit=1 --json databaseId --jq '.[0].databaseId')
gh run download $RUN_ID --name sbom
ls -lh sbom.cdx.json
jq '.components | length' sbom.cdx.json
# 應該 ≥ 50（合理規模）
```

## 6. 既有功能不回歸

```bash
uv run pytest -q          # 134 tests + 新的 workflow-pinning test 應全綠
helm lint deploy/helm/ai-api --set ...   # Phase 2.5 既有檢查
```

## 7. SC 檢核

| SC | 對應步驟 |
|---|---|
| SC-001 | §2 grep `@master` = 0 |
| SC-002 | §2 全部 ref 40-char SHA |
| SC-003 | §3 scheduled-scan ≤ 5 分鐘 + 去重正確 |
| SC-004 | §4 fs scan ≤ 30s fail-fast |
| SC-005 | §5 SBOM components ≥ 50 |
| SC-006 | §6 既有 134 tests 全綠 |
| SC-007 | `git log -- tests/ .github/` test commit 早於 impl commit |
