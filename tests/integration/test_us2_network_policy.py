"""US2: validate Helm chart renders NetworkPolicy with expected rules."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

CHART_DIR = Path(__file__).resolve().parents[2] / "deploy" / "helm" / "ai-api"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("helm") is None, reason="helm CLI not available"),
]


def _render() -> list[dict]:
    result = subprocess.run(
        [
            "helm", "template", "test", str(CHART_DIR),
            "--set", "adminBootstrapToken=tok",
            "--set", "azureOpenAI.apiBase=https://example.openai.azure.com",
            "--set", "azureOpenAI.apiKey=test-key",
            "--set", "database.url=postgresql+asyncpg://u:p@h:5432/db",
        ],
        capture_output=True, text=True, check=True,
    )
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def test_renders_networkpolicy() -> None:
    docs = _render()
    nps = [d for d in docs if d["kind"] == "NetworkPolicy"]
    assert len(nps) == 1
    np = nps[0]
    assert "Egress" in np["spec"]["policyTypes"]
    assert "Ingress" in np["spec"]["policyTypes"]


def test_networkpolicy_blocks_metadata_ip() -> None:
    np = next(d for d in _render() if d["kind"] == "NetworkPolicy")
    # Find the 443 egress rule
    rule_with_443 = next(
        r for r in np["spec"]["egress"]
        if any(p.get("port") == 443 for p in r.get("ports", []))
    )
    cidr_spec = rule_with_443["to"][0]["ipBlock"]
    assert "169.254.0.0/16" in cidr_spec.get("except", []), (
        "NetworkPolicy must explicitly exclude cloud metadata 169.254.0.0/16"
    )


def test_networkpolicy_allows_postgres_pod() -> None:
    np = next(d for d in _render() if d["kind"] == "NetworkPolicy")
    pg_rule = next(
        r for r in np["spec"]["egress"]
        if any(p.get("port") == 5432 for p in r.get("ports", []))
    )
    assert "podSelector" in pg_rule["to"][0]


def test_renders_cronjob_anomaly_detector() -> None:
    docs = _render()
    cjs = [d for d in docs if d["kind"] == "CronJob" and "anomaly" in d["metadata"]["name"]]
    assert len(cjs) == 1
    cj = cjs[0]
    assert cj["spec"]["schedule"]
    cmd = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["command"]
    assert "ai_api.cli.run_anomaly_detector" in " ".join(cmd)


def test_deployment_has_security_hardening() -> None:
    docs = _render()
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    sc = container.get("securityContext", {})
    assert sc.get("readOnlyRootFilesystem") is True
    assert sc.get("allowPrivilegeEscalation") is False
    assert "ALL" in (sc.get("capabilities") or {}).get("drop", [])
    # emptyDir volumes for tmp/cache
    vols = {v["name"] for v in deploy["spec"]["template"]["spec"].get("volumes", [])}
    assert {"tmp", "cache"} <= vols
