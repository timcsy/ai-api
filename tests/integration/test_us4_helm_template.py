"""US4 Helm chart structure validation via `helm template`."""
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
            "helm",
            "template",
            "test",
            str(CHART_DIR),
            "--set",
            "adminBootstrapToken=tok",
            "--set",
            "azureOpenAI.apiBase=https://example.openai.azure.com",
            "--set",
            "azureOpenAI.apiKey=test-key-DO-NOT-LEAK",
            "--set",
            "database.url=postgresql+asyncpg://u:p@h:5432/db",
            "--set",
            "providerKeyEncKey=wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I=",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    docs = [d for d in yaml.safe_load_all(result.stdout) if d]
    return docs


_BASE_SETS = [
    "adminBootstrapToken=tok",
    "azureOpenAI.apiBase=https://example.openai.azure.com",
    "azureOpenAI.apiKey=test-key-DO-NOT-LEAK",
    "database.url=postgresql+asyncpg://u:p@h:5432/db",
    "providerKeyEncKey=wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I=",
]


def _render_with(extra_sets: list[str]) -> list[dict]:
    args = ["helm", "template", "test", str(CHART_DIR)]
    for s in [*_BASE_SETS, *extra_sets]:
        args += ["--set", s]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def _jobs_by_label(docs: list[dict], value: str) -> list[dict]:
    out = []
    for d in docs:
        if d.get("kind") != "Job":
            continue
        labels = d["spec"]["template"]["metadata"].get("labels", {})
        if labels.get("job") == value:
            out.append(d)
    return out


# Phase 017 US3 — first-admin bootstrap Job
def test_bootstrap_admin_job_absent_by_default() -> None:
    docs = _render()  # default values: bootstrapAdmin not enabled
    assert _jobs_by_label(docs, "bootstrap-admin") == []


def test_bootstrap_admin_job_rendered_when_enabled() -> None:
    docs = _render_with(
        ["bootstrapAdmin.enabled=true", "bootstrapAdmin.email=admin@org.edu"]
    )
    jobs = _jobs_by_label(docs, "bootstrap-admin")
    assert len(jobs) == 1
    job = jobs[0]
    ann = job["metadata"]["annotations"]
    assert "pre-install" in ann["helm.sh/hook"]
    assert "pre-upgrade" in ann["helm.sh/hook"]
    # must run AFTER the migrate job (weight 0)
    assert int(ann["helm.sh/hook-weight"]) > 0
    container = job["spec"]["template"]["spec"]["containers"][0]
    assert any("secretRef" in e for e in container.get("envFrom", []))
    cmd = " ".join(container["command"] + container.get("args", []))
    assert "create_admin" in cmd
    assert "admin@org.edu" in cmd


def test_bootstrap_admin_job_absent_when_email_empty() -> None:
    docs = _render_with(["bootstrapAdmin.enabled=true"])  # email left empty
    assert _jobs_by_label(docs, "bootstrap-admin") == []


def test_renders_required_resources() -> None:
    docs = _render()
    kinds = {d["kind"] for d in docs}
    assert {"Deployment", "Service", "Secret"} <= kinds
    # Migration job exists by default
    assert "Job" in kinds


def test_deployment_uses_secret_env() -> None:
    docs = _render()
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    env_from = container.get("envFrom", [])
    assert any("secretRef" in e for e in env_from), "Deployment must reference secret via envFrom"


def test_secret_contains_required_keys() -> None:
    docs = _render()
    secret = next(d for d in docs if d["kind"] == "Secret")
    keys = set(secret.get("stringData", {}).keys())
    required = {
        "ADMIN_BOOTSTRAP_TOKEN",
        "AZURE_OPENAI_API_BASE",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_VERSION",
        "DATABASE_URL",
    }
    assert required <= keys


def test_deployment_has_health_probes() -> None:
    docs = _render()
    deploy = next(d for d in docs if d["kind"] == "Deployment")
    container = deploy["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == "/healthz"
    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"


def test_rendered_secret_value_does_not_leak_into_other_resources() -> None:
    """Defence-in-depth: the test key must only appear in the Secret manifest."""
    docs = _render()
    leaky = "test-key-DO-NOT-LEAK"
    for d in docs:
        if d["kind"] == "Secret":
            continue
        assert leaky not in yaml.safe_dump(d), f"key leaked into {d['kind']}"


def test_phase5_missing_provider_key_enc_key_fails_template() -> None:
    """Phase 5 T064: helm template MUST fail when providerKeyEncKey is empty."""
    result = subprocess.run(
        [
            "helm", "template", "test", str(CHART_DIR),
            "--set", "adminBootstrapToken=tok",
            "--set", "azureOpenAI.apiBase=https://example.openai.azure.com",
            "--set", "azureOpenAI.apiKey=test-key",
            "--set", "database.url=postgresql+asyncpg://u:p@h:5432/db",
            # providerKeyEncKey deliberately omitted
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "providerKeyEncKey" in result.stderr or "providerKeyEncKey" in result.stdout


def test_phase5_secret_contains_provider_key_enc_key() -> None:
    """Phase 5: rendered Secret MUST expose PROVIDER_KEY_ENC_KEY."""
    docs = _render()
    secret = next(d for d in docs if d["kind"] == "Secret")
    assert "PROVIDER_KEY_ENC_KEY" in secret["stringData"]
    assert secret["stringData"]["PROVIDER_KEY_ENC_KEY"]
