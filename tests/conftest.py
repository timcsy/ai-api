"""Top-level pytest configuration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is on path even if package not installed in editable mode.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Provide deterministic defaults for tests if env not set.
os.environ.setdefault("ADMIN_BOOTSTRAP_TOKEN", "test-admin-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AZURE_OPENAI_API_BASE", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-key-DO-NOT-LEAK")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-06-01")
os.environ.setdefault("AZURE_OPENAI_TEST_MODEL", "gpt-test")
# Phase 5: deterministic Fernet key for ProviderCredential encryption tests.
os.environ.setdefault(
    "PROVIDER_KEY_ENC_KEY", "wG4iqV3qxGqQfp_8ARDqVU93G8YzxBOFnHTL98_3l9I="
)
