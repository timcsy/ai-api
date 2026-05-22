"""Phase 2.6: assert every `uses:` ref is a 40-char commit SHA, not a mutable tag.

Tracks experience.md lesson: "快速迭代不要用 mutable tag" — applied to Action refs.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"

# action ref shape: owner/repo[/path]@<40-char-sha>
SHA_REF = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+@[0-9a-f]{40}$")
SEMVER = re.compile(r"^v\d+\.\d+\.\d+$")


def _collect_uses(doc: dict) -> list[str]:
    """Walk a workflow doc and yield every `uses:` value found."""
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "uses" and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return out


@pytest.mark.parametrize("path", sorted(WORKFLOWS_DIR.glob("*.yml")))
def test_all_uses_refs_are_pinned_to_commit_sha(path: Path) -> None:
    doc = yaml.safe_load(path.read_text())
    refs = _collect_uses(doc)
    bad = [r for r in refs if not SHA_REF.match(r)]
    assert not bad, (
        f"{path.name}: the following action refs are NOT pinned to a 40-char "
        f"commit SHA (Phase 2.6 FR-001):\n  " + "\n  ".join(bad)
    )


def test_no_mutable_refs() -> None:
    """Hard fail on @master / @main — these are the worst offenders."""
    pattern = re.compile(r"@(master|main)\b")
    offenders: list[str] = []
    for path in WORKFLOWS_DIR.glob("*.yml"):
        for line in path.read_text().splitlines():
            if "uses:" in line and pattern.search(line):
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, (
        "mutable branch refs found:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "path", [WORKFLOWS_DIR / "image.yml", WORKFLOWS_DIR / "scheduled-scan.yml"]
)
def test_trivy_cli_version_pinned(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path.name} not yet created")
    doc = yaml.safe_load(path.read_text())

    found_trivy_step = False
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses = step.get("uses") or ""
            if "aquasecurity/trivy-action" in uses:
                found_trivy_step = True
                version = (step.get("with") or {}).get("version")
                assert version, f"{path.name}: trivy-action step missing `with.version` (FR-002)"
                assert SEMVER.match(str(version)), (
                    f"{path.name}: Trivy CLI version `{version}` is not pinned semver"
                )
    assert found_trivy_step, f"{path.name}: no trivy-action step found"
