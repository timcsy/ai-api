"""Install-script endpoints (Phase 19).

Serve the Codex one-line installer per OS as plain text, injecting this
platform's base_url so the member never has to know or type it. The scripts
themselves run device-flow (no token copy-paste).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

import ai_api
from ai_api.config import get_settings

router = APIRouter()

_TEMPLATE_DIR = Path(ai_api.__file__).resolve().parent / "install"


def _render(template_name: str) -> str:
    text = (_TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    base_url = get_settings().base_url.rstrip("/")
    return text.replace("__BASE_URL__", base_url)


@router.get("/install/codex.sh", response_class=PlainTextResponse)
async def install_codex_sh() -> str:
    """macOS / Linux installer: `curl -fsSL <base>/install/codex.sh | sh`."""
    return _render("codex.sh.tmpl")


@router.get("/install/codex.ps1", response_class=PlainTextResponse)
async def install_codex_ps1() -> str:
    """Windows installer: `irm <base>/install/codex.ps1 | iex`."""
    return _render("codex.ps1.tmpl")


@router.get("/install/codex-restore.sh", response_class=PlainTextResponse)
async def restore_codex_sh() -> str:
    """macOS / Linux restore: `curl -fsSL <base>/install/codex-restore.sh | sh`.

    Puts back the most recent installer backup (*.bak-<ts>) of config.toml /
    auth.json — switch Codex back to the settings you had before installing."""
    return _render("codex-restore.sh.tmpl")


@router.get("/install/codex-restore.ps1", response_class=PlainTextResponse)
async def restore_codex_ps1() -> str:
    """Windows restore: `irm <base>/install/codex-restore.ps1 | iex`."""
    return _render("codex-restore.ps1.tmpl")
