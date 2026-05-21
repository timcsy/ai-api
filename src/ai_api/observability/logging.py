"""Structured JSON logging with redaction filter for Azure OpenAI key."""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from ai_api.config import get_settings

_REDACTION_PLACEHOLDER = "***"


class RedactionFilter(logging.Filter):
    """Replace any occurrence of the configured Azure OpenAI key with ``***``.

    Defence-in-depth: even if LiteLLM or the SDK accidentally logs the key, this
    filter scrubs it before it reaches stdout / files.
    """

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        for secret in self._secrets:
            if not secret:
                continue
            if isinstance(record.msg, str) and secret in record.msg:
                record.msg = record.msg.replace(secret, _REDACTION_PLACEHOLDER)
            if record.args:
                record.args = tuple(_redact(arg, secret) for arg in record.args)
        return True


def _redact(value: Any, secret: str) -> Any:
    if isinstance(value, str) and secret in value:
        return value.replace(secret, _REDACTION_PLACEHOLDER)
    return value


def redact_string(value: str) -> str:
    """Apply current redaction secrets to an arbitrary string (e.g. error messages)."""
    settings = get_settings()
    for secret in (settings.azure_openai_api_key,):
        if secret and secret in value:
            value = value.replace(secret, _REDACTION_PLACEHOLDER)
    return value


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
