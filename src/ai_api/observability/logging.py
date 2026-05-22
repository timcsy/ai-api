"""Structured JSON logging with redaction filter for secrets."""
from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from ai_api.config import get_settings

_REDACTION_PLACEHOLDER = "***"

# Token-shaped patterns we know we issue: redact if leaked into logs/responses.
# `aiapi_<32+>` (Phase 1 allocation token), `sess_<32+>` (Phase 2 session token),
# `invite_<32+>` (Phase 2 invitation token).
_TOKEN_PATTERN = re.compile(r"(?:aiapi|sess|invite)_[A-Za-z0-9_\-]{16,}")


def _current_secrets() -> list[str]:
    s = get_settings()
    return [v for v in (s.azure_openai_api_key, s.google_oauth_client_secret) if v]


class RedactionFilter(logging.Filter):
    """Replace any occurrence of configured secrets with ``***``.

    Defence-in-depth: even if LiteLLM, the SDK, or accidental logging includes
    a secret, this filter scrubs it before it reaches stdout / files.
    """

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        # Allow tests to inject extra secrets; production reads at filter time.
        self._extra_secrets = [s for s in (secrets or []) if s]

    def _all_secrets(self) -> list[str]:
        return [*self._extra_secrets, *_current_secrets()]

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = self._all_secrets()
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg, secrets)
        if record.args:
            record.args = tuple(_redact(arg, secrets) for arg in record.args)
        return True


def _scrub(value: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and s in value:
            value = value.replace(s, _REDACTION_PLACEHOLDER)
    value = _TOKEN_PATTERN.sub(_REDACTION_PLACEHOLDER, value)
    return value


def _redact(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        return _scrub(value, secrets)
    return value


def redact_string(value: str) -> str:
    """Apply current redaction secrets to an arbitrary string (e.g. error messages)."""
    if not value:
        return value
    return _scrub(value, _current_secrets())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        allocation_id = getattr(record, "allocation_id", None)
        if allocation_id:
            payload["allocation_id"] = allocation_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str | None = None) -> None:
    settings = get_settings()
    effective_level = (level or settings.log_level).upper()

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter(secrets=[settings.azure_openai_api_key]))
    root.addHandler(handler)
    root.setLevel(effective_level)
