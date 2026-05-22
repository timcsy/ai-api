# Supply Chain Operations (Phase 2.6+)

How to upgrade pinned GitHub Action refs and Trivy CLI versions safely, and
how to handle CVE issues opened by the scheduled rescan.

## TL;DR

- **Every `uses:` line in `.github/workflows/*.yml` MUST pin a 40-char commit SHA.**
- **Trivy CLI version is pinned in `with.version:`** of every trivy-action step.
- **`.trivyignore` is governed**: each entry must have a reason in the PR
  description that added it (see PR template).
- **`scheduled-scan.yml`** runs weekly; new CVEs open a deduplicated GitHub issue.

## Upgrading a pinned action SHA

When you want to bump (say) `aquasecurity/trivy-action` to the latest:

```bash
# 1. Find the tag and resolve its commit SHA
TAG=$(gh api repos/aquasecurity/trivy-action/releases/latest --jq .tag_name)
SHA=$(gh api "repos/aquasecurity/trivy-action/commits/$TAG" --jq .sha)
echo "$SHA  # $TAG"

# 2. In .github/workflows/*.yml replace the old SHA with the new one;
#    update the `# v<tag>` comment too.

# 3. Run the pinning test to catch typos
uv run pytest tests/unit/test_workflow_pinning.py
```

Open the PR with:
- Link to the release notes
- The full command used (so reviewers can verify the SHA)
- A note on what changed (e.g. "trivy-action 0.36.0 → 0.37.0 — minor bug fixes,
  no breaking changes per release notes")

## Upgrading Trivy CLI version

```bash
gh api repos/aquasecurity/trivy/releases/latest --jq .tag_name
```

In each trivy-action step, bump `with.version: 'v0.XX.X'`. Trivy semver bumps
can change CVE detection — expect new HIGH/CRITICAL to surface. Either fix or
add to `.trivyignore` with reason.

## When `scheduled-scan` opens an issue

The scheduled rescan opens an issue per HIGH/CRITICAL CVE not in `.trivyignore`.
Issue title: `[CVE-XXXX-NNNNN] new HIGH/CRITICAL in image (YYYY-MM-DD)`.

Triage:
1. **Real and exploitable**: open a PR that bumps the affected dependency.
   Close the issue when the next image build is clean.
2. **Real but not reachable in our code**: add the CVE id to `.trivyignore`
   with a one-line reason that links to this issue. Close the issue.
3. **False positive**: same as (2) but reason should say "false positive:
   <evidence>". Consider opening upstream Trivy issue.

## When something blocks the gate

- **Trivy DB download fails** in CI: usually transient. Re-run the workflow.
  Persistent failure → check GitHub status + `aquasecurity/trivy-db` repo.
- **PR is blocked by a CVE you can't fix immediately**: legitimate use of
  `.trivyignore` is fine — but the **reason must be honest**. Future you reads
  these.

## Non-goals (deferred, documented in vision.md)

- Self-hosted Trivy server / private vuln DB mirror
- Second scanner (OSV / Grype) in CI — currently a manual quarterly check
- `cosign` image signing + admission control
- Slack / email notifications (GitHub issues are sufficient v1)
