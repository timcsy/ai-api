# Summary

<!-- 1-3 bullets on what and why -->

# Test plan

- [ ] `uv run ruff check .`
- [ ] `uv run mypy src/ai_api`
- [ ] `uv run pytest -q`
- [ ] Other manual verification (describe)

# Security checklist

- [ ] No secrets in code / config files
- [ ] If `.trivyignore` was modified, every entry has a one-line reason here:
   - `CVE-YYYY-NNNNN` — _reason and links_

# Supply chain (Phase 2.6)

- [ ] No mutable refs (`@master`/`@main`) added; new action `uses:` lines pin a 40-char commit SHA + semver tag comment
- [ ] If `aquasecurity/trivy-action` or Trivy CLI version was bumped, attach:
   - link to release notes
   - command used to derive the new commit SHA (e.g. `gh api repos/<repo>/commits/<tag>`)
- [ ] `uv run pytest tests/unit/test_workflow_pinning.py` is green
