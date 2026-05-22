"""Provider allowlist: parse provider prefix from model string + check against config."""
from __future__ import annotations

DEFAULT_PROVIDER = "azure"


def parse_provider(model: str, default: str = DEFAULT_PROVIDER) -> tuple[str, str]:
    """Split `<provider>/<model>` → (provider, model). Falls back to default if no `/`."""
    if "/" in model:
        prov, _, rest = model.partition("/")
        return prov.lower(), rest
    return default, model


def check_allowed(provider: str, allowed: list[str]) -> bool:
    """Return True if provider is in the configured allowlist (case-insensitive)."""
    return provider.lower() in {p.lower() for p in allowed}
