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
