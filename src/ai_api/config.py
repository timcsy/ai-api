"""Application settings loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Well-known dev default for ADMIN_BOOTSTRAP_TOKEN. Shared with the startup
# guard (main.create_app) and its tests so the "is this still the insecure
# default?" check has a single source of truth.
DEFAULT_ADMIN_BOOTSTRAP_TOKEN = "local-dev-admin-only"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_api.db",
        alias="DATABASE_URL",
    )
    admin_bootstrap_token: str = Field(
        default=DEFAULT_ADMIN_BOOTSTRAP_TOKEN,
        alias="ADMIN_BOOTSTRAP_TOKEN",
    )

    azure_openai_api_base: str = Field(default="", alias="AZURE_OPENAI_API_BASE")
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field(
        default="2024-06-01", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_test_model: str = Field(
        default="gpt-4o-mini", alias="AZURE_OPENAI_TEST_MODEL"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Phase 2: auth
    base_url: str = Field(default="http://localhost:8000", alias="BASE_URL")
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    cookie_domain: str = Field(default="", alias="COOKIE_DOMAIN")
    google_oauth_client_id: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str = Field(default="", alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_discovery_url: str = Field(
        default="https://accounts.google.com/.well-known/openid-configuration",
        alias="GOOGLE_DISCOVERY_URL",
    )

    # Phase 2.5: hardening
    allowed_providers: list[str] = Field(
        default=["azure", "openai", "anthropic", "gemini"],
        alias="ALLOWED_PROVIDERS",
    )
    anomaly_check_interval_min: int = Field(default=5, alias="ANOMALY_CHECK_INTERVAL_MIN")
    anomaly_threshold_multiplier: float = Field(
        default=10.0, alias="ANOMALY_THRESHOLD_MULTIPLIER"
    )
    anomaly_absolute_cold_start: int = Field(
        default=10000, alias="ANOMALY_ABSOLUTE_COLD_START"
    )
    anomaly_min_calls: int = Field(default=100, alias="ANOMALY_MIN_CALLS")
    perip_lockout_threshold: int = Field(default=10, alias="PERIP_LOCKOUT_THRESHOLD")

    # Phase 3a: usage & billing
    cors_origins: list[str] = Field(default=[], alias="CORS_ORIGINS")

    # Phase 3c: adaptive quota pool
    pool_total_tokens_per_month: int = Field(default=0, alias="POOL_TOTAL_TOKENS_PER_MONTH")
    pool_floor_per_allocation: int = Field(default=1000, alias="POOL_FLOOR_PER_ALLOCATION")

    # Phase 13: subscription override for which audit event types trigger emails.
    # Empty list = use built-in default (allocation_quarantined / responses_upstream_error_burst
    # / provider_credential_auth_failed). Operator can override at deploy time via
    # NOTIFY_EVENT_TYPES_OVERRIDE="type_a,type_b".
    notify_event_types_override: list[str] = Field(
        default=[], alias="NOTIFY_EVENT_TYPES_OVERRIDE"
    )
    # Phase 13 US3: upstream error-burst detector thresholds.
    upstream_burst_threshold: int = Field(default=10, alias="UPSTREAM_BURST_THRESHOLD")
    upstream_burst_window_minutes: int = Field(
        default=5, alias="UPSTREAM_BURST_WINDOW_MINUTES"
    )

    # Phase 12: edge request body limit (informational, mirrors the value baked
    # into the frontend nginx pod via Helm — admin UI shows it so users know
    # how big a payload is accepted before they hit 413). Single source of
    # truth is the Helm value `requestBodyLimitMB`.
    request_body_limit_mb: int = Field(default=100, alias="REQUEST_BODY_LIMIT_MB")

    # Phase 5: provider credential encryption
    # 32-byte url-safe base64 Fernet key (e.g., Fernet.generate_key()).
    # In production this MUST come from a K8s Secret; empty value triggers
    # startup failure when ProviderCredential code paths run.
    provider_key_enc_key: str = Field(default="", alias="PROVIDER_KEY_ENC_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
