"""Unit tests for provider parsing + allowlist."""
from __future__ import annotations

from ai_api.proxy.allowlist import check_allowed, parse_provider


def test_parse_with_slash():
    assert parse_provider("azure/gpt-4o-mini") == ("azure", "gpt-4o-mini")
    assert parse_provider("anthropic/claude-3-opus") == ("anthropic", "claude-3-opus")


def test_parse_default_when_no_slash():
    assert parse_provider("gpt-4o") == ("azure", "gpt-4o")
    assert parse_provider("gpt-4o", default="openai") == ("openai", "gpt-4o")


def test_parse_case_insensitive():
    prov, _ = parse_provider("Azure/whatever")
    assert prov == "azure"


def test_check_allowed():
    assert check_allowed("azure", ["azure"])
    assert check_allowed("Azure", ["azure"])
    assert check_allowed("azure", ["AZURE", "Anthropic"])
    assert not check_allowed("anthropic", ["azure"])
    assert not check_allowed("anthropic", [])
